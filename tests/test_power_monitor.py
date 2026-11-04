from power_monitor import PowerMonitor, parse_tegrastats_line

JP4 = ("RAM 2008/3956MB (lfb 4x4MB) SWAP 0/1978MB CPU [12%@1479,4%@1479] EMC_FREQ 0% "
       "GR3D_FREQ 0% PLL@27C CPU@29.5C GPU@27.5C POM_5V_IN 2087/2087 POM_5V_GPU 0/0 POM_5V_CPU 368/368")
JP5 = "RAM 3000/7000MB CPU [1%@729] GR3D_FREQ 0% VDD_IN 5012mW/5012mW VDD_CPU_GPU_CV 600mW/600mW"


def test_parse_jp4():
    assert parse_tegrastats_line(JP4) == 2087


def test_parse_jp5():
    assert parse_tegrastats_line(JP5) == 5012


def test_parse_garbage():
    assert parse_tegrastats_line("hello") is None


def test_measure_without_sensor_still_times():
    pm = PowerMonitor()
    pm.source, pm._read = None, None              # force "not a Jetson"
    with pm.measure() as m:
        sum(range(10000))
    assert m.duration_s > 0 and m.avg_mw is None and m.energy_j is None


def test_measure_with_fake_sysfs():
    pm = PowerMonitor(interval=0.01)
    pm.source, pm._read = "fake", lambda: 2000.0
    import time
    with pm.measure() as m:
        time.sleep(0.1)
    assert m.avg_mw == 2000.0
    assert 0.15 < m.energy_j < 0.3                # 2 W * ~0.1 s
