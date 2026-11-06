import csv
import math
import threading

import config

MAX_MANUAL_SPEED = 15.0        # m/s, simulator remote cap


class GPSSim:
    """Simulated GPS: position along a waypoint path, given seconds since start.

    Simulator remote (ground station → telemetry reply → control()):
      auto    follow the path (patrol when loop=True)
      manual  fly a commanded heading/speed from wherever the drone is (speed 0 = hover)
      return  after "auto" is chosen again: fly straight back to the nearest point of the
              path, then carry on patrolling from there, so the track never jumps.
    Only the simulation is steered; real GPS sources have no control() at all.
    """

    def __init__(self, path_csv=None, speed=None, loop=None):
        path_csv = config.FLIGHT_PATH_CSV if path_csv is None else path_csv
        with open(path_csv) as f:
            self.pts = [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)]
        if len(self.pts) < 2:
            raise ValueError("flight path needs at least 2 waypoints")
        self.speed = config.DRONE_SPEED_MPS if speed is None else speed
        # loop: patrol forever, flying back to the first waypoint after the last one
        self.loop = config.SIM_LOOP if loop is None else loop
        if self.loop and self.pts[-1] != self.pts[0]:
            self.pts.append(self.pts[0])
        self.cum = [0.0]                      # cumulative distance at each waypoint
        for a, b in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + self._dist(a, b))
        self.total = self.cum[-1]
        self._seg = 1                         # segment index of the last position()
        self._lock = threading.RLock()        # main loop and link thread both ask
        self._mode = "auto"
        self._offset = 0.0                    # route distance shift after a manual detour
        self._last_id = None
        self._pos = None                      # manual / return: current position ...
        self._t = 0.0                         # ... at this time
        self._heading = 0.0
        self._mspeed = 0.0
        self._target = None                   # return: point on the route ...
        self._target_d = 0.0                  # ... and its route distance

    @staticmethod
    def _dist(a, b):
        dlat = (b[0] - a[0]) * 111320.0
        dlon = (b[1] - a[1]) * 111320.0 * math.cos(math.radians((a[0] + b[0]) / 2))
        return math.hypot(dlat, dlon)

    @staticmethod
    def _bearing_between(a, b):
        dlat = b[0] - a[0]
        dlon = (b[1] - a[1]) * math.cos(math.radians((a[0] + b[0]) / 2))
        return math.degrees(math.atan2(dlon, dlat)) % 360.0

    @staticmethod
    def _move(p, heading, metres):
        h = math.radians(heading)
        return (p[0] + metres * math.cos(h) / 111320.0,
                p[1] + metres * math.sin(h) / (111320.0 * math.cos(math.radians(p[0]))))

    # ---- following the path
    def _route_d(self, t_sec):
        d = max(t_sec, 0.0) * self.speed + self._offset
        if self.loop and self.total > 0:
            return d % self.total
        return min(max(d, 0.0), self.total)   # hold at the last point

    def _route_point(self, d):
        for i in range(1, len(self.cum)):
            if d <= self.cum[i]:
                seg = self.cum[i] - self.cum[i - 1]
                f = 0.0 if seg == 0 else (d - self.cum[i - 1]) / seg
                a, b = self.pts[i - 1], self.pts[i]
                self._seg = i
                return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f
        self._seg = len(self.pts) - 1
        return self.pts[-1]

    def _nearest_route_d(self, p):
        best, best_d = None, 0.0
        for i in range(1, len(self.pts)):
            a, b = self.pts[i - 1], self.pts[i]
            seg = self.cum[i] - self.cum[i - 1]
            if seg == 0:
                continue
            k = math.cos(math.radians(a[0]))      # local metres
            ax, ay, bx, by = a[1] * k, a[0], b[1] * k, b[0]
            px, py = p[1] * k, p[0]
            dx, dy = bx - ax, by - ay
            f = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
            q = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            dist = self._dist(p, q)
            if best is None or dist < best:
                best, best_d = dist, self.cum[i - 1] + f * seg
        return best_d

    # ---- time steps
    def _advance(self, t):
        """Move a manual / returning drone up to time t (no-op for t in the past)."""
        dt = t - self._t
        if dt <= 0:
            return
        self._t = t
        if self._mode == "manual":
            if self._mspeed > 0:
                self._pos = self._move(self._pos, self._heading, self._mspeed * dt)
        elif self._mode == "return":
            left = self._dist(self._pos, self._target)
            step = self.speed * dt
            if step >= left:                      # back on the route: carry on patrolling
                spare = (step - left) / self.speed if self.speed else 0.0
                self._pos = self._target
                self._mode = "auto"
                self._offset = self._target_d - (t - spare) * self.speed
            else:
                self._pos = self._move(self._pos, self._bearing_between(self._pos, self._target), step)

    def _position(self, t_sec):
        if self._mode != "auto":
            self._advance(t_sec)
            if self._mode != "auto":
                return self._pos
        return self._route_point(self._route_d(t_sec))

    def position(self, t_sec):
        with self._lock:
            return self._position(t_sec)

    # ---- simulator remote
    def control(self, cmd, t_sec):
        """Apply a remote command (each command id once; replies repeat the latest one)."""
        if not isinstance(cmd, dict):
            return
        with self._lock:
            cid = cmd.get("id")
            if cid is None or cid == self._last_id:
                return
            self._last_id = cid
            mode = cmd.get("mode")
            if mode == "manual":
                here = self._position(t_sec)
                try:
                    heading = float(cmd.get("heading", self._course(t_sec))) % 360.0
                    speed = min(MAX_MANUAL_SPEED, max(0.0, float(cmd.get("speed", self.speed))))
                except (TypeError, ValueError):
                    return
                self._mode, self._pos, self._t = "manual", here, t_sec
                self._heading, self._mspeed = heading, speed
            elif mode == "auto" and self._mode != "auto":
                here = self._position(t_sec)
                self._target_d = self._nearest_route_d(here)
                self._target = self._route_point(self._target_d)
                self._mode, self._pos, self._t = "return", here, t_sec
                self._advance(t_sec)

    # ---- telemetry
    def _bearing(self, i):
        return self._bearing_between(self.pts[i - 1], self.pts[i])

    def _course(self, t_sec):
        if self._mode == "manual":
            return self._heading
        if self._mode == "return":
            return self._bearing_between(self._pos, self._target)
        return self._bearing(self._seg)

    def status(self, t_sec):
        """Telemetry 'gps' block (see link protocol); the sim always has a fix."""
        with self._lock:
            lat, lon = self._position(t_sec)
            if self._mode == "manual":
                speed = self._mspeed
            elif self._mode == "return":
                speed = self.speed
            else:
                moving = self.loop or 0 <= self._route_d(t_sec) < self.total
                speed = self.speed if moving else 0.0
            return {"mode": "sim", "fix": True, "lat": lat, "lon": lon, "alt_m": None,
                    "sats": None, "hdop": None, "speed_mps": speed,
                    "course_deg": round(self._course(t_sec), 1), "age_s": 0.0,
                    "control": self._mode}
