import csv
import math
import config


class GPSSim:
    """Simulated GPS: position along a waypoint path, given seconds since start."""

    def __init__(self, path_csv=config.FLIGHT_PATH_CSV, speed=config.DRONE_SPEED_MPS):
        with open(path_csv) as f:
            self.pts = [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)]
        if len(self.pts) < 2:
            raise ValueError("flight path needs at least 2 waypoints")
        self.speed = speed
        self.cum = [0.0]                      # cumulative distance at each waypoint
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + self._dist(a, b))
        self.total = self.cum[-1]
        self._seg = 1                         # segment index of the last position()

    @staticmethod
    def _dist(a, b):
        dlat = (b[0] - a[0]) * 111320.0
        dlon = (b[1] - a[1]) * 111320.0 * math.cos(math.radians((a[0] + b[0]) / 2))
        return math.hypot(dlat, dlon)

    def position(self, t_sec):
        d = min(max(t_sec, 0.0) * self.speed, self.total)   # hold at the last point
        for i in range(1, len(self.cum)):
            if d <= self.cum[i]:
                seg = self.cum[i] - self.cum[i - 1]
                f = 0.0 if seg == 0 else (d - self.cum[i - 1]) / seg
                a, b = self.pts[i - 1], self.pts[i]
                self._seg = i
                return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        self._seg = len(self.pts) - 1
        return self.pts[-1]

    def _bearing(self, i):
        a, b = self.pts[i - 1], self.pts[i]
        dlat = b[0] - a[0]
        dlon = (b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
        return math.degrees(math.atan2(dlon, dlat)) % 360.0

    def status(self, t_sec):
        """Telemetry 'gps' block (see link protocol); the sim always has a fix."""
        lat, lon = self.position(t_sec)
        moving = 0 <= t_sec * self.speed < self.total
        return {"mode": "sim", "fix": True, "lat": lat, "lon": lon, "alt_m": None,
                "sats": None, "hdop": None,
                "speed_mps": self.speed if moving else 0.0,
                "course_deg": round(self._bearing(self._seg), 1), "age_s": 0.0}