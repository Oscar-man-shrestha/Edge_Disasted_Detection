"""Push buffered alerts to the ground station now (finds it automatically by default)."""
import time

import config
from alert_store import AlertStore
from link import DroneLink, StationFinder

finder = StationFinder(fixed_url=None if config.SERVER_URL == "auto" else config.SERVER_URL).start()
deadline = time.time() + 5
while finder.url() is None and time.time() < deadline:
    time.sleep(0.2)
url = finder.url()
finder.stop()
if url is None:
    raise SystemExit("no ground station found (no beacon on UDP %d within 5 s)" % config.DISCOVERY_PORT)
sent, left = AlertStore().forward_pending(url, DroneLink._headers())
print(f"station {url}: sent {sent}, still buffered {left}")
