"""Ground-station SQLite: missions, alerts (with operator workflow), drone track."""
import math
import sqlite3
import threading
import time

STATUSES = ("new", "acknowledged", "resolved")
ALERT_COLS = ["id", "mission_id", "drone_id", "drone_alert_id", "type", "conf", "lat", "lon",
              "video_time", "wall_time", "received", "snapshot", "status", "note",
              "acked_at", "resolved_at"]
TRACK_MIN_MOVE_M = 2.0
TRACK_MIN_DT_S = 5.0


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _dist_m(lat1, lon1, lat2, lon2):
    dlat = (lat2 - lat1) * 111320.0
    dlon = (lon2 - lon1) * 111320.0 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dlat, dlon)


class Store:
    def __init__(self, db_path):
        self.lock = threading.Lock()
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self._last_track = {}                 # drone_id -> (t, lat, lon)
        with self.lock:
            self._schema()

    # ------------------------------------------------------------ schema
    def _schema(self):
        db = self.db
        db.execute("""CREATE TABLE IF NOT EXISTS missions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT,
            started_at TEXT, ended_at TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drone_alert_id TEXT, type TEXT, conf REAL, lat REAL, lon REAL,
            video_time REAL, wall_time TEXT, received TEXT, snapshot TEXT)""")
        # v1 (single-file app.py) databases have only the columns above: add the rest.
        have = {r["name"] for r in db.execute("PRAGMA table_info(alerts)")}
        for col, decl in [("mission_id", "INTEGER"), ("drone_id", "TEXT"),
                          ("status", "TEXT DEFAULT 'new'"), ("note", "TEXT"),
                          ("acked_at", "TEXT"), ("resolved_at", "TEXT")]:
            if col not in have:
                db.execute("ALTER TABLE alerts ADD COLUMN %s %s" % (col, decl))
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS dedupe ON alerts(drone_alert_id, wall_time)")
        db.execute("""CREATE TABLE IF NOT EXISTS track (
            id INTEGER PRIMARY KEY AUTOINCREMENT, mission_id INTEGER, drone_id TEXT,
            t REAL, lat REAL, lon REAL, alt_m REAL)""")
        db.execute("UPDATE alerts SET status='new' WHERE status IS NULL")
        orphans = db.execute("SELECT COUNT(*) FROM alerts WHERE mission_id IS NULL").fetchone()[0]
        if orphans:
            mid = self._current_mission_id()
            db.execute("UPDATE alerts SET mission_id=? WHERE mission_id IS NULL", (mid,))
        db.commit()

    # ------------------------------------------------------------ missions
    def _current_mission_id(self):
        row = self.db.execute(
            "SELECT id FROM missions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            return row["id"]
        cur = self.db.execute("INSERT INTO missions (name, started_at) VALUES (?, ?)",
                              (None, _now()))
        mid = cur.lastrowid
        self.db.execute("UPDATE missions SET name=? WHERE id=?", ("Mission %d" % mid, mid))
        self.db.commit()
        return mid

    def _mission(self, mid):
        r = self.db.execute("SELECT * FROM missions WHERE id=?", (mid,)).fetchone()
        return dict(r) if r else None

    def current_mission(self):
        with self.lock:
            return self._mission(self._current_mission_id())

    def mission(self, mid):
        with self.lock:
            return self._mission(mid)

    def new_mission(self, name=None):
        with self.lock:
            self.db.execute("UPDATE missions SET ended_at=? WHERE ended_at IS NULL", (_now(),))
            cur = self.db.execute("INSERT INTO missions (name, started_at) VALUES (?, ?)",
                                  (name, _now()))
            mid = cur.lastrowid
            if not name:
                self.db.execute("UPDATE missions SET name=? WHERE id=?", ("Mission %d" % mid, mid))
            self.db.commit()
            self._last_track.clear()
            return self._mission(mid)

    def missions(self):
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM missions ORDER BY id")]

    # ------------------------------------------------------------ alerts
    def _alert(self, aid):
        r = self.db.execute("SELECT * FROM alerts WHERE id=?", (aid,)).fetchone()
        return {k: r[k] for k in ALERT_COLS} if r else None

    def add_alert(self, f):
        """Insert an alert; a resend of (drone_alert_id, wall_time) returns the stored row."""
        with self.lock:
            if f.get("drone_alert_id") is not None:
                r = self.db.execute("SELECT id FROM alerts WHERE drone_alert_id=? AND wall_time=?",
                                    (f["drone_alert_id"], f.get("wall_time"))).fetchone()
                if r:
                    return self._alert(r["id"]), False
            mid = self._current_mission_id()
            cur = self.db.execute(
                "INSERT INTO alerts (mission_id, drone_id, drone_alert_id, type, conf, lat, lon, "
                "video_time, wall_time, received, status) VALUES (?,?,?,?,?,?,?,?,?,?, 'new')",
                (mid, f.get("drone_id"), f.get("drone_alert_id"), f["type"], f["conf"],
                 f.get("lat"), f.get("lon"), f.get("video_time"), f.get("wall_time"),
                 time.strftime("%H:%M:%S")))
            self.db.commit()
            return self._alert(cur.lastrowid), True

    def set_snapshot(self, aid, name):
        with self.lock:
            self.db.execute("UPDATE alerts SET snapshot=? WHERE id=?", (name, aid))
            self.db.commit()

    def update_alert(self, aid, status=None, note=None):
        if status is not None and status not in STATUSES:
            raise ValueError("bad status %r" % (status,))
        with self.lock:
            if self._alert(aid) is None:
                return None
            if status is not None:
                self.db.execute("UPDATE alerts SET status=? WHERE id=?", (status, aid))
                if status == "acknowledged":
                    self.db.execute("UPDATE alerts SET acked_at=? WHERE id=?", (_now(), aid))
                elif status == "resolved":
                    self.db.execute("UPDATE alerts SET resolved_at=?, "
                                    "acked_at=COALESCE(acked_at, ?) WHERE id=?",
                                    (_now(), _now(), aid))
            if note is not None:
                self.db.execute("UPDATE alerts SET note=? WHERE id=?", (note[:500], aid))
            self.db.commit()
            return self._alert(aid)

    def alert(self, aid):
        with self.lock:
            return self._alert(aid)

    def alerts(self, mission_id=None):
        with self.lock:
            if mission_id is None:
                rows = self.db.execute("SELECT * FROM alerts ORDER BY id")
            else:
                rows = self.db.execute("SELECT * FROM alerts WHERE mission_id=? ORDER BY id",
                                       (mission_id,))
            return [{k: r[k] for k in ALERT_COLS} for r in rows]

    # ------------------------------------------------------------ track
    def add_track_point(self, drone_id, t, lat, lon, alt_m):
        """Store a point if the drone moved >= 2 m or 5 s passed since the last one kept."""
        with self.lock:
            last = self._last_track.get(drone_id)
            if last is not None:
                lt, llat, llon = last
                if (t - lt) < TRACK_MIN_DT_S and _dist_m(llat, llon, lat, lon) < TRACK_MIN_MOVE_M:
                    return False
            mid = self._current_mission_id()
            self.db.execute("INSERT INTO track (mission_id, drone_id, t, lat, lon, alt_m) "
                            "VALUES (?,?,?,?,?,?)", (mid, drone_id, t, lat, lon, alt_m))
            self.db.commit()
            self._last_track[drone_id] = (t, lat, lon)
            return True

    def track(self, mission_id):
        with self.lock:
            return [dict(r) for r in self.db.execute(
                "SELECT t, lat, lon, alt_m, drone_id FROM track WHERE mission_id=? ORDER BY id",
                (mission_id,))]
