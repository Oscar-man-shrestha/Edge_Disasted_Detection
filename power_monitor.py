"""Board power measurement for the Jetson Nano, so benchmarks can report energy.

Reads the on-board INA3221 power monitor straight from sysfs (works inside the
Docker container, /sys is visible read-only). Falls back to parsing `tegrastats`
if sysfs is not found. On a laptop neither exists and the monitor reports
available=False, so callers just skip the energy numbers.

Usage:
    pm = PowerMonitor()
    with pm.measure() as m:
        ... work ...
    print(m.avg_mw, m.energy_j)
"""
import glob
import os
import re
import shutil
import subprocess
import threading
import time
from contextlib import contextmanager

import config

# JetPack 4 (Nano): /sys/bus/i2c/drivers/ina3221x/6-0040/iio:device0/in_power0_input
_IIO_GLOB = "/sys/bus/i2c/drivers/ina3221x/*/iio:device*"
# JetPack 5+ style: /sys/bus/i2c/drivers/ina3221/*/hwmon/hwmon*/in1_label, curr1_input, in1_input
_HWMON_GLOB = "/sys/bus/i2c/drivers/ina3221/*/hwmon/hwmon*"

# tegrastats: "POM_5V_IN 2087/2087" (JP4, mW) or "VDD_IN 5000mW/5000mW" (JP5)
_TEGRA_RE = re.compile(r"\b(POM_5V_IN|VDD_IN)\s+(\d+)(?:mW)?/(\d+)")


def parse_tegrastats_line(line):
    """Return total board input power in mW from one tegrastats line, or None."""
    m = _TEGRA_RE.search(line)
    return int(m.group(2)) if m else None


def _find_sysfs_reader():
    """Return (description, fn() -> mW) for the board input rail, or None."""
    for dev in sorted(glob.glob(_IIO_GLOB)):
        for ch in range(3):
            name_f = os.path.join(dev, "rail_name_%d" % ch)
            pow_f = os.path.join(dev, "in_power%d_input" % ch)
            try:
                with open(name_f) as f:
                    name = f.read().strip()
            except OSError:
                continue
            if name in ("POM_5V_IN", "VDD_IN") and os.path.exists(pow_f):
                return name, lambda p=pow_f: float(open(p).read())
    for dev in sorted(glob.glob(_HWMON_GLOB)):
        for ch in range(1, 4):
            try:
                with open(os.path.join(dev, "in%d_label" % ch)) as f:
                    name = f.read().strip()
            except OSError:
                continue
            if name in ("VDD_IN", "POM_5V_IN"):
                cur = os.path.join(dev, "curr%d_input" % ch)    # mA
                volt = os.path.join(dev, "in%d_input" % ch)     # mV
                return name, lambda c=cur, v=volt: (
                    float(open(c).read()) * float(open(v).read()) / 1000.0)
    return None


class Measurement:
    def __init__(self):
        self.samples = []          # (t, mW)
        self.duration_s = 0.0

    @property
    def avg_mw(self):
        return sum(p for _, p in self.samples) / len(self.samples) if self.samples else None

    @property
    def energy_j(self):
        a = self.avg_mw
        return None if a is None else a / 1000.0 * self.duration_s


class PowerMonitor:
    def __init__(self, interval=None):
        self.interval = interval or config.POWER_SAMPLE_SEC
        self.source = None
        self._read = None
        found = _find_sysfs_reader()
        if found:
            self.source = "sysfs:" + found[0]
            self._read = found[1]
        elif shutil.which("tegrastats"):
            self.source = "tegrastats"

    @property
    def available(self):
        return self.source is not None

    @contextmanager
    def measure(self):
        m = Measurement()
        if not self.available:
            t0 = time.perf_counter()
            yield m
            m.duration_s = time.perf_counter() - t0
            return
        stop = threading.Event()
        if self._read:
            th = threading.Thread(target=self._poll_sysfs, args=(m, stop), daemon=True)
            proc = None
        else:
            ms = max(100, int(self.interval * 1000))
            proc = subprocess.Popen(["tegrastats", "--interval", str(ms)],
                                    stdout=subprocess.PIPE, universal_newlines=True)
            th = threading.Thread(target=self._poll_tegrastats, args=(m, proc), daemon=True)
        th.start()
        t0 = time.perf_counter()
        try:
            yield m
        finally:
            m.duration_s = time.perf_counter() - t0
            stop.set()
            if proc:
                proc.terminate()
            th.join(timeout=2)

    def _poll_sysfs(self, m, stop):
        while not stop.is_set():
            try:
                m.samples.append((time.time(), self._read()))
            except (OSError, ValueError):
                pass
            stop.wait(self.interval)

    @staticmethod
    def _poll_tegrastats(m, proc):
        for line in proc.stdout:
            p = parse_tegrastats_line(line)
            if p is not None:
                m.samples.append((time.time(), float(p)))


if __name__ == "__main__":
    pm = PowerMonitor()
    print("power source:", pm.source or "none (not a Jetson?)")
    if pm.available:
        with pm.measure() as m:
            time.sleep(3)
        print("idle: %.0f mW avg over %.1f s (%d samples)" % (m.avg_mw or 0, m.duration_s, len(m.samples)))
