import math
import os
import sqlite3
import time
import cv2
import config

PRIORITY = {"person": 1, "fire": 2, "smoke": 3}     # lower number is sent first


class AlertStore:
    def __init__(self):
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)
        self.db = sqlite3.connect(config.DB_PATH)
        self.db.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_time REAL, wall_time TEXT, type TEXT, conf REAL,
            lat REAL, lon REAL, snapshot TEXT, priority INTEGER,
            sent INTEGER DEFAULT 0)""")
        have = {r[1] for r in self.db.execute("PRAGMA table_info(alerts)")}
        for col, decl in [("clip", "TEXT"), ("clip_frames", "INTEGER"), ("clip_fps", "REAL"),
                          ("clip_sent", "INTEGER DEFAULT 0")]:
            if col not in have:                       # older databases: add the clip columns
                self.db.execute("ALTER TABLE alerts ADD COLUMN %s %s" % (col, decl))
        self.db.commit()
        self.last_alert = {}          # type -> time of the last alert made
        self.last_seen = {}           # type -> time it was last seen (above threshold)

    def maybe_add(self, det, frame, t_sec, lat, lon):
        """Save an alert unless it is below threshold or part of an ongoing event."""
        typ = det["type"]
        if typ == "person" and det["conf"] < config.PERSON_ALERT_CONF:
            return None
        seen, last = self.last_seen.get(typ), self.last_alert.get(typ)
        self.last_seen[typ] = t_sec
        if (seen is not None and last is not None and t_sec - seen < config.EVENT_GAP_SEC
                and t_sec - last < config.ALERT_REPEAT_SEC):
            return None                       # same event, still going
        self.last_alert[typ] = t_sec

        if lat is not None and math.isnan(lat):    # no GPS fix: store NULL, not NaN
            lat = lon = None
        # wall_time carries the UTC offset: the container clock may be UTC while the
        # ground station shows local time.
        cur = self.db.execute(
            "INSERT INTO alerts (video_time, wall_time, type, conf, lat, lon, snapshot, priority) "
            "VALUES (?,?,?,?,?,?,NULL,?)",
            (t_sec, time.strftime("%Y-%m-%d %H:%M:%S %z"), typ, det["conf"],
             lat, lon, PRIORITY.get(typ, 9)))
        aid = cur.lastrowid
        # The row id makes the name unique: t_sec restarts at 0 on every run, so
        # "<type>_<t>s.jpg" alone could overwrite an older, still unsent alert's photo.
        snap = os.path.join(config.SNAPSHOT_DIR, f"{aid}_{typ}_{t_sec:.1f}s.jpg")
        img = frame.copy()
        x1, y1, x2, y2 = [int(v) for v in det["box"]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        if cv2.imwrite(snap, img):
            self.db.execute("UPDATE alerts SET snapshot=? WHERE id=?", (snap, aid))
        self.db.commit()
        return aid

    def counts(self):
        r = self.db.execute("SELECT COALESCE(SUM(sent=0),0), COALESCE(SUM(sent=1),0) "
                            "FROM alerts").fetchone()
        return {"buffered": int(r[0]), "sent": int(r[1])}

    def forward_pending(self, base_url, headers=None):
        """POST unsent alerts to <base_url>/alert, most important first; stop at the first failure.

        alert_id + wall_time let the ground station drop a resend whose first copy
        arrived but whose reply was lost. A missing snapshot does not block the alert.
        """
        import requests
        base_url = base_url.rstrip("/")
        if base_url.endswith("/alert"):
            base_url = base_url[:-len("/alert")]
        rows = self.db.execute(
            "SELECT id, video_time, wall_time, type, conf, lat, lon, snapshot "
            "FROM alerts WHERE sent=0 ORDER BY priority, id").fetchall()
        sent = 0
        for id_, vt, wt, typ, conf, lat, lon, snap in rows:
            data = {"alert_id": id_, "drone_id": config.DRONE_ID, "type": typ, "conf": conf,
                    "lat": "" if lat is None else lat, "lon": "" if lon is None else lon,
                    "video_time": vt, "wall_time": wt}
            f = None
            try:
                if snap and os.path.isfile(snap):
                    f = open(snap, "rb")
                else:
                    print(f"[link] snapshot missing for alert #{id_}, sending without image")
                r = requests.post(base_url + "/alert", data=data, headers=headers or {},
                                  files={"snapshot": f} if f else None,
                                  timeout=(config.FORWARD_CONNECT_TIMEOUT, 3))
                if r.status_code != 200:
                    break
            except requests.RequestException:
                break                 # no connection: keep buffering
            finally:
                if f:
                    f.close()
            self.db.execute("UPDATE alerts SET sent=1 WHERE id=?", (id_,))
            self.db.commit()
            sent += 1
        return sent, len(rows) - sent

    def set_clip(self, alert_id, path, frames, fps):
        self.db.execute("UPDATE alerts SET clip=?, clip_frames=?, clip_fps=?, clip_sent=0 WHERE id=?",
                        (path, frames, fps, alert_id))
        self.db.commit()

    def forward_clips(self, base_url, headers=None, max_clips=1, requests=None):
        """POST finished clips of already-delivered alerts to <base_url>/api/clip.

        One clip per call by default, so a slow radio link keeps room for telemetry
        and new alerts. 404 (the station does not know the alert) or a missing folder
        marks the clip as given up (clip_sent=2) instead of retrying forever.
        """
        if requests is None:
            import requests
        base_url = base_url.rstrip("/")
        if base_url.endswith("/alert"):
            base_url = base_url[:-len("/alert")]
        rows = self.db.execute(
            "SELECT id, wall_time, clip, clip_fps FROM alerts WHERE sent=1 AND clip IS NOT NULL "
            "AND clip_sent=0 ORDER BY priority, id").fetchall()
        sent = 0
        for id_, wt, path, fps in rows[:max_clips]:
            names = sorted(n for n in os.listdir(path) if n.endswith(".jpg")) if os.path.isdir(path) else []
            if not names:
                self.db.execute("UPDATE alerts SET clip_sent=2 WHERE id=?", (id_,))
                self.db.commit()
                continue
            files = []
            try:
                for n in names:
                    files.append(("frames", (n, open(os.path.join(path, n), "rb"), "image/jpeg")))
                data = {"alert_id": id_, "drone_id": config.DRONE_ID, "wall_time": wt, "fps": fps}
                r = requests.post(base_url + "/api/clip", data=data, files=files,
                                  headers=headers or {}, timeout=(config.FORWARD_CONNECT_TIMEOUT, 15))
            except Exception:
                break                                  # no connection: try again later
            finally:
                for _, (_, f, _) in files:
                    f.close()
            if r.status_code == 200:
                self.db.execute("UPDATE alerts SET clip_sent=1 WHERE id=?", (id_,))
            elif r.status_code == 404:
                self.db.execute("UPDATE alerts SET clip_sent=2 WHERE id=?", (id_,))
            else:
                break
            self.db.commit()
            sent += r.status_code == 200
        left = self.db.execute("SELECT COUNT(*) FROM alerts WHERE clip IS NOT NULL "
                               "AND clip_sent=0").fetchone()[0]
        return sent, left

