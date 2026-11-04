"""GPS for alerts: simulated path, a NMEA GPS module (e.g. u-blox NEO-M8N) on a
serial port, or a flight controller over MAVLink.

All expose position(t_sec) -> (lat, lon); (nan, nan) means no valid fix.
Pick with config.GPS_MODE / EDGE_GPS. Quick check on the board:

    python3 gps_source.py            # prints fixes from the configured mode
"""
import math
import threading
import time

import config
from gps_sim import GPSSim

NAN = (float("nan"), float("nan"))


# ---------------------------------------------------------------- NMEA parsing
def nmea_checksum_ok(line):
    """'$GNRMC,...*6A' -> True if the XOR checksum matches."""
    if not line.startswith("$") or "*" not in line:
        return False
    body, _, cs = line[1:].partition("*")
    calc = 0
    for ch in body:
        calc ^= ord(ch)
    try:
        return calc == int(cs[:2], 16)
    except ValueError:
        return False


def _coord(value, hemi):
    """NMEA ddmm.mmmm / dddmm.mmmm + N/S/E/W -> signed decimal degrees."""
    if not value or not hemi:
        return None
    dot = value.index(".") if "." in value else len(value)
    deg = float(value[:dot - 2])
    minutes = float(value[dot - 2:])
    d = deg + minutes / 60.0
    return -d if hemi in ("S", "W") else d


def parse_nmea(line):
    """Parse RMC and GGA sentences from any talker (GP, GN, GL, ...).

    Returns a dict or None. RMC: {kind, valid, lat, lon, speed_mps, course}.
    GGA: {kind, quality, sats, hdop, alt_m, lat, lon}. quality 0 = no fix.
    """
    line = line.strip()
    if not nmea_checksum_ok(line):
        return None
    f = line[1:line.index("*")].split(",")
    kind = f[0][2:]
    try:
        if kind == "RMC" and len(f) >= 9:
            return {"kind": "RMC", "valid": f[2] == "A",
                    "lat": _coord(f[3], f[4]), "lon": _coord(f[5], f[6]),
                    "speed_mps": float(f[7]) * 0.514444 if f[7] else None,
                    "course": float(f[8]) if f[8] else None}
        if kind == "GGA" and len(f) >= 10:
            return {"kind": "GGA", "quality": int(f[6] or 0), "sats": int(f[7] or 0),
                    "hdop": float(f[8]) if f[8] else None,
                    "alt_m": float(f[9]) if f[9] else None,
                    "lat": _coord(f[2], f[3]), "lon": _coord(f[4], f[5])}
    except (ValueError, IndexError):
        return None
    return None


class NmeaGPS:
    """Reads a NMEA GPS (u-blox NEO-M8N and similar) on a serial port.

    Nano B01 wiring (3.3 V logic UART /dev/ttyTHS1, 40-pin header):
        GPS TX -> pin 10 (UART RX)     GPS RX -> pin 8 (UART TX)
        GPS VCC -> pin 2 or 4 (5 V)    GPS GND -> pin 6
    or plug the GPS into a USB-serial adapter -> /dev/ttyUSB0.
    The compass (I2C, the separate 4-pin plug) is not used.
    """

    BAUDS = (9600, 38400, 115200, 57600)      # M8N factory default is 9600

    def __init__(self, port=None, baud=None, max_fix_age=None):
        import serial                          # pip install pyserial
        self._serial = serial
        self.port = port or config.GPS_PORT
        self.baud = baud or config.GPS_BAUD     # 0 = auto-detect
        self.max_fix_age = max_fix_age if max_fix_age is not None else config.GPS_MAX_FIX_AGE_SEC
        self.fix = None
        self.fix_time = None
        self.sats = 0
        self.hdop = None
        self.alt_m = None
        self.speed_mps = None
        self.course_deg = None
        self.sentences = 0
        self._stop = threading.Event()
        self.ser = self._open()
        threading.Thread(target=self._loop, daemon=True).start()

    def _open(self):
        if self.baud:
            return self._serial.Serial(self.port, self.baud, timeout=1)
        for b in self.BAUDS:                    # auto-baud: first rate giving valid NMEA
            ser = self._serial.Serial(self.port, b, timeout=1)
            deadline = time.time() + 2.5
            while time.time() < deadline:
                line = ser.readline().decode("ascii", "ignore")
                if nmea_checksum_ok(line.strip()):
                    self.baud = b
                    return ser
            ser.close()
        raise RuntimeError("no NMEA data on %s at %s baud (check wiring TX->RX, power, "
                           "and that the serial console is disabled)" % (self.port, self.BAUDS))

    def _loop(self):
        while not self._stop.is_set():
            try:
                line = self.ser.readline().decode("ascii", "ignore")
            except Exception:                   # unplugged: keep last fix, retry
                time.sleep(1)
                continue
            msg = parse_nmea(line)
            if not msg:
                continue
            self.sentences += 1
            if msg["kind"] == "GGA":
                self.sats, self.hdop, self.alt_m = msg["sats"], msg["hdop"], msg["alt_m"]
                good = msg["quality"] > 0
            else:
                good = msg["valid"]
                if good:
                    self.speed_mps, self.course_deg = msg["speed_mps"], msg["course"]
            if good and msg["lat"] is not None and msg["lon"] is not None:
                self.fix = (msg["lat"], msg["lon"])
                self.fix_time = time.time()

    def age_sec(self):
        return None if self.fix_time is None else time.time() - self.fix_time

    def position(self, t_sec=None):
        """Latest fix, or (nan, nan) if none / older than GPS_MAX_FIX_AGE_SEC."""
        age = self.age_sec()
        if self.fix is None or age is None or age > self.max_fix_age:
            return NAN
        return self.fix

    def status(self):
        lat, lon = self.position()
        fix = not math.isnan(lat)
        age = self.age_sec()
        return {"mode": "nmea", "fix": fix,
                "lat": lat if fix else None, "lon": lon if fix else None,
                "alt_m": self.alt_m, "sats": self.sats, "hdop": self.hdop,
                "speed_mps": self.speed_mps if fix else None,
                "course_deg": self.course_deg if fix else None,
                "age_s": None if age is None else round(age, 2)}

    def close(self):
        self._stop.set()


class MavlinkGPS:
    """Latest GLOBAL_POSITION_INT from an ArduPilot/PX4 flight controller.

    Wiring on the Nano B01: flight-controller TELEM TX -> pin 10 (UART RX),
    TELEM RX -> pin 8 (UART TX), GND -> pin 6. Device /dev/ttyTHS1, 3.3 V logic.
    Disable the serial console on ttyTHS1 first (see README).
    """

    def __init__(self, url=None, wait_fix_sec=0):
        from pymavlink import mavutil         # optional dependency: pip install pymavlink
        url = url or config.MAVLINK_URL
        if "," in url and not url.startswith(("udp", "tcp")):
            dev, baud = url.split(",", 1)
            self.conn = mavutil.mavlink_connection(dev, baud=int(baud))
        else:
            self.conn = mavutil.mavlink_connection(url)
        self.fix = None                         # (lat, lon)
        self.fix_time = None
        self.alt_m = self.speed_mps = self.course_deg = None
        self._stop = threading.Event()
        threading.Thread(target=self._loop, daemon=True).start()
        deadline = time.time() + wait_fix_sec
        while self.fix is None and time.time() < deadline:
            time.sleep(0.1)

    def _loop(self):
        while not self._stop.is_set():
            msg = self.conn.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=1)
            if msg is None:
                continue
            if msg.lat == 0 and msg.lon == 0:    # no fix yet
                continue
            self.fix = (msg.lat / 1e7, msg.lon / 1e7)
            self.fix_time = time.time()
            self.alt_m = msg.alt / 1000.0
            self.speed_mps = math.hypot(msg.vx, msg.vy) / 100.0
            self.course_deg = None if msg.hdg == 65535 else msg.hdg / 100.0

    def position(self, t_sec=None):
        """Latest fix; (nan, nan) if none yet. t_sec is ignored (real time)."""
        return self.fix if self.fix is not None else NAN

    def age_sec(self):
        return None if self.fix_time is None else time.time() - self.fix_time

    def status(self):
        fix = self.fix is not None
        age = self.age_sec()
        return {"mode": "mavlink", "fix": fix,
                "lat": self.fix[0] if fix else None, "lon": self.fix[1] if fix else None,
                "alt_m": self.alt_m, "sats": None, "hdop": None,
                "speed_mps": self.speed_mps, "course_deg": self.course_deg,
                "age_s": None if age is None else round(age, 2)}

    def close(self):
        self._stop.set()


def make_gps(mode=None):
    mode = (mode or config.GPS_MODE).lower()
    if mode == "sim":
        return GPSSim()
    if mode == "nmea":
        gps = NmeaGPS()
        print("[gps] nmea %s @ %s baud (fix comes later if the sky view is poor)" % (gps.port, gps.baud))
        return gps
    if mode == "mavlink":
        gps = MavlinkGPS(wait_fix_sec=10)
        print("[gps] mavlink", config.MAVLINK_URL, "fix:", gps.fix or "none yet")
        return gps
    raise ValueError("unknown GPS mode %r (use 'sim', 'nmea' or 'mavlink')" % mode)


if __name__ == "__main__":
    g = make_gps()
    print("Ctrl+C to stop")
    try:
        while True:
            lat, lon = g.position(0)
            extra = ""
            if isinstance(g, NmeaGPS):
                extra = "  sats=%d hdop=%s sentences=%d" % (g.sats, g.hdop, g.sentences)
            print(("no fix" if math.isnan(lat) else "%.6f, %.6f" % (lat, lon)) + extra)
            time.sleep(1)
    except KeyboardInterrupt:
        pass
