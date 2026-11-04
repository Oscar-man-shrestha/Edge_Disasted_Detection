import math
import os
import time

import pytest

from gps_source import NmeaGPS, nmea_checksum_ok, parse_nmea


def sentence(body):
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    return "$%s*%02X" % (body, cs)


RMC = sentence("GNRMC,123519.00,A,1258.2900,N,07735.4300,E,0.5,84.4,051126,,,A")
RMC_VOID = sentence("GNRMC,123519.00,V,,,,,,,051126,,,N")
GGA = sentence("GPGGA,123519.00,1258.2900,N,07735.4300,E,1,09,0.9,920.4,M,-86.0,M,,")
GGA_NOFIX = sentence("GPGGA,123519.00,,,,,0,00,99.99,,,,,,")
SOUTH_WEST = sentence("GPRMC,000000,A,3352.1280,S,15112.5580,W,0,0,010120,,,A")


def test_checksum():
    assert nmea_checksum_ok(RMC)
    assert not nmea_checksum_ok(RMC[:-2] + "00")
    assert not nmea_checksum_ok("garbage")


def test_rmc_valid():
    m = parse_nmea(RMC)
    assert m["kind"] == "RMC" and m["valid"]
    assert m["lat"] == pytest.approx(12 + 58.29 / 60)
    assert m["lon"] == pytest.approx(77 + 35.43 / 60)
    assert m["speed_mps"] == pytest.approx(0.257, abs=1e-3)


def test_rmc_void_and_gga_nofix():
    assert parse_nmea(RMC_VOID)["valid"] is False
    g = parse_nmea(GGA_NOFIX)
    assert g["quality"] == 0 and g["lat"] is None


def test_gga_fields():
    g = parse_nmea(GGA)
    assert (g["quality"], g["sats"], g["hdop"], g["alt_m"]) == (1, 9, 0.9, 920.4)


def test_south_west_negative():
    m = parse_nmea(SOUTH_WEST)
    assert m["lat"] < 0 and m["lon"] < 0
    assert m["lat"] == pytest.approx(-(33 + 52.128 / 60))


def test_reader_over_pseudo_serial_port():
    """End to end: a fake GPS streams NMEA into a pty (like a real module, 10 Hz)."""
    pytest.importorskip("serial")
    import threading
    master, slave = os.openpty()
    port = os.ttyname(slave)
    state = {"lines": [GGA_NOFIX, RMC_VOID], "stop": False}

    def stream():
        while not state["stop"]:
            os.write(master, ("\r\n".join(state["lines"]) + "\r\n").encode())
            time.sleep(0.1)

    threading.Thread(target=stream, daemon=True).start()
    gps = NmeaGPS(port=port, baud=0, max_fix_age=0.5)
    try:
        assert gps.baud == 9600
        time.sleep(0.3)
        assert math.isnan(gps.position()[0])  # streaming, but no fix yet
        state["lines"] = [GGA, RMC]
        for _ in range(40):
            if gps.fix:
                break
            time.sleep(0.05)
        lat, lon = gps.position()
        assert lat == pytest.approx(12.9715) and lon == pytest.approx(77.5905)
        assert gps.sats == 9
        state["lines"] = [GGA_NOFIX]           # lost fix: old one goes stale
        time.sleep(0.9)
        assert math.isnan(gps.position()[0])
    finally:
        state["stop"] = True
        gps.close()
        time.sleep(0.15)
        os.close(master)
        os.close(slave)
