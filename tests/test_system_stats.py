import os

from system_stats import SystemStats


def _w(root, rel, text):
    p = os.path.join(str(root), rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)


def test_reads_fake_jetson_root(tmp_path):
    _w(tmp_path, "sys/devices/virtual/thermal/thermal_zone0/type", "CPU-therm\n")
    _w(tmp_path, "sys/devices/virtual/thermal/thermal_zone0/temp", "48500\n")
    _w(tmp_path, "sys/devices/virtual/thermal/thermal_zone1/type", "GPU-therm\n")
    _w(tmp_path, "sys/devices/virtual/thermal/thermal_zone1/temp", "46000\n")
    _w(tmp_path, "sys/devices/gpu.0/load", "710\n")
    _w(tmp_path, "proc/meminfo", "MemTotal:        4050944 kB\nMemFree:  100 kB\nMemAvailable:    1081344 kB\n")
    _w(tmp_path, "proc/stat", "cpu  100 0 100 800 0 0 0\ncpu0 1 1 1 1\n")
    s = SystemStats(root=str(tmp_path))
    first = s.read()
    assert first["cpu_temp_c"] == 48.5
    assert first["gpu_temp_c"] == 46.0
    assert first["gpu_load_pct"] == 71.0
    assert first["ram_total_mb"] == 3956
    assert first["ram_used_mb"] == 2900
    _w(tmp_path, "proc/stat", "cpu  160 0 140 900 0 0 0\n")
    assert s.read()["cpu_load_pct"] == 50.0


def test_missing_everything_returns_nones(tmp_path):
    d = SystemStats(root=str(tmp_path)).read()
    assert set(d) == {"power_mw", "cpu_temp_c", "gpu_temp_c", "cpu_load_pct",
                      "gpu_load_pct", "ram_used_mb", "ram_total_mb"}
    assert all(v is None for v in d.values())
