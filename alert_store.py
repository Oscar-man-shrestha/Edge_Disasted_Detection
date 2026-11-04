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
        self.db.commit()
        self.last_alert = {}          # type -> time of last alert

    def maybe_add(self, det, frame, t_sec, lat, lon):
        """Save an alert unless it is below threshold or inside the cooldown."""
        typ = det["type"]
        if typ == "person" and det["conf"] < config.PERSON_ALERT_CONF:
            return None
        last = self.last_alert.get(typ)
        if last is not None and t_sec - last < config.ALERT_COOLDOWN_SEC:
            return None
        self.last_alert[typ] = t_sec

        snap = os.path.join(config.SNAPSHOT_DIR, f"{typ}_{t_sec:.1f}s.jpg")
        img = frame.copy()
        x1, y1, x2, y2 = [int(v) for v in det["box"]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.imwrite(snap, img)

        cur = self.db.execute(
            "INSERT INTO alerts (video_time, wall_time, type, conf, lat, lon, snapshot, priority) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (t_sec, time.strftime("%Y-%m-%d %H:%M:%S"), typ, det["conf"],
             lat, lon, snap, PRIORITY.get(typ, 9)))
        self.db.commit()
        return cur.lastrowid

    def forward_pending(self):
        """Try to POST unsent alerts, most important first. Stops at the first failure.

        alert_id + wall_time let the ground station drop a resend whose first copy
        arrived but whose reply was lost. A missing snapshot does not block the alert.
        """
        import requests
        rows = self.db.execute(
            "SELECT id, video_time, wall_time, type, conf, lat, lon, snapshot "
            "FROM alerts WHERE sent=0 ORDER BY priority, id").fetchall()
        sent = 0
        for id_, vt, wt, typ, conf, lat, lon, snap in rows:
            data = {"alert_id": id_, "type": typ, "conf": conf, "lat": lat, "lon": lon,
                    "video_time": vt, "wall_time": wt}
            f = None
            try:
                if snap and os.path.isfile(snap):
                    f = open(snap, "rb")
                else:
                    print(f"[link] snapshot missing for alert #{id_}, sending without image")
                r = requests.post(config.SERVER_URL, data=data,
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
