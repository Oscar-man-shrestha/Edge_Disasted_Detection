import json
import socket
import time

from discovery import Beacon, beacon_payload
from events import EventBus, format_sse


def test_publish_reaches_all_subscribers():
    bus = EventBus()
    q1, q2 = bus.subscribe(), bus.subscribe()
    bus.publish("alert", {"id": 1})
    for q in (q1, q2):
        ev, data = q.get_nowait()
        assert ev == "alert" and data["id"] == 1 and "server_time" in data


def test_slow_subscriber_dropped_others_keep_receiving():
    bus = EventBus(max_queue=2)
    slow, fast = bus.subscribe(), bus.subscribe()
    got = []
    for i in range(5):
        bus.publish("telemetry", {"i": i})
        got.append(fast.get_nowait()[1]["i"])
    assert got == [0, 1, 2, 3, 4]
    assert slow not in bus._subs and fast in bus._subs


def test_format_sse():
    s = format_sse("link", {"state": "live"})
    assert s.startswith("event: link\ndata: ") and s.endswith("\n\n")
    assert json.loads(s.split("data: ", 1)[1]) == {"state": "live"}


def test_stream_heartbeat_when_idle():
    bus = EventBus()
    q = bus.subscribe()
    gen = bus.stream(q, heartbeat=0.05)
    assert next(gen) == ": hb\n\n"
    bus.publish("mission", {"id": 2})
    assert next(gen).startswith("event: mission")


def _free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_beacon_received_on_localhost():
    port = _free_udp_port()
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", port))
    rx.settimeout(2)
    b = Beacon(5000, ["127.0.0.1", "10.255.255.255"], beacon_port=port, interval=0.1)
    b.start()
    try:
        data, _ = rx.recvfrom(1024)
    finally:
        b.stop()
        rx.close()
    msg = json.loads(data)
    assert msg["service"] == "edge-gs" and msg["port"] == 5000 and msg["v"] == 1
    assert json.loads(beacon_payload(5000))["service"] == "edge-gs"
