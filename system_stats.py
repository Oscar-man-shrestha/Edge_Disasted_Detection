"""Jetson board health for drone telemetry: temperatures, loads, RAM, power.

Reads sysfs/procfs under `root` (default "/"); every value is None when the
file is missing, so this runs harmlessly on a laptop.
"""
import glob
import os


class SystemStats:
    def __init__(self, root="/"):
        self.root = root
        self._prev_cpu = None          # (busy, total) from the previous /proc/stat read
        self._power = None
        if root == "/":
            try:
                from power_monitor import PowerMonitor
                self._power = PowerMonitor()._read   # None off-Jetson
            except Exception:
                self._power = None

    def _p(self, rel):
        return os.path.join(self.root, rel)

    @staticmethod
    def _read_text(path):
        try:
            with open(path) as f:
                return f.read().strip()
        except OSError:
            return None

    def _temps(self):
        cpu = gpu = None
        for zone in sorted(glob.glob(self._p("sys/devices/virtual/thermal/thermal_zone*"))):
            kind = self._read_text(os.path.join(zone, "type"))
            raw = self._read_text(os.path.join(zone, "temp"))
            if kind is None or raw is None:
                continue
            try:
                c = int(raw) / 1000.0
            except ValueError:
                continue
            if kind.startswith("CPU") and cpu is None:
                cpu = c
            elif kind.startswith("GPU") and gpu is None:
                gpu = c
        return cpu, gpu

    def _gpu_load(self):
        raw = self._read_text(self._p("sys/devices/gpu.0/load"))
        try:
            return int(raw) / 10.0 if raw is not None else None
        except ValueError:
            return None

    def _cpu_load(self):
        raw = self._read_text(self._p("proc/stat"))
        if not raw or not raw.startswith("cpu "):
            return None
        vals = [int(v) for v in raw.splitlines()[0].split()[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)       # idle + iowait
        total = sum(vals)
        busy = total - idle
        prev, self._prev_cpu = self._prev_cpu, (busy, total)
        if prev is None or total == prev[1]:
            return None
        return round(100.0 * (busy - prev[0]) / (total - prev[1]), 1)

    def _ram(self):
        raw = self._read_text(self._p("proc/meminfo"))
        if not raw:
            return None, None
        info = {}
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                info[parts[0].rstrip(":")] = int(parts[1])
        if "MemTotal" not in info or "MemAvailable" not in info:
            return None, None
        total = info["MemTotal"] // 1024
        used = (info["MemTotal"] - info["MemAvailable"]) // 1024
        return used, total

    def read(self):
        cpu_t, gpu_t = self._temps()
        used, total = self._ram()
        power = None
        if self._power:
            try:
                power = round(self._power())
            except (OSError, ValueError):
                power = None
        return {
            "power_mw": power,
            "cpu_temp_c": cpu_t,
            "gpu_temp_c": gpu_t,
            "cpu_load_pct": self._cpu_load(),
            "gpu_load_pct": self._gpu_load(),
            "ram_used_mb": used,
            "ram_total_mb": total,
        }


def read_stats(root="/"):
    return SystemStats(root).read()
