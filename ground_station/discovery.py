"""UDP beacon so drones can find this ground station without a configured IP."""
import json
import socket
import threading

SERVICE = "edge-gs"
DEFAULT_BEACON_PORT = 5005


def beacon_payload(http_port):
    return json.dumps({"service": SERVICE, "v": 1, "port": int(http_port),
                       "name": socket.gethostname()}).encode()


class Beacon:
    def __init__(self, http_port, targets, beacon_port=DEFAULT_BEACON_PORT, interval=2.0):
        self.payload = beacon_payload(http_port)
        self.targets = [t.strip() for t in targets if t.strip()]
        self.beacon_port = beacon_port
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            while not self._stop.is_set():
                for t in self.targets:
                    try:
                        sock.sendto(self.payload, (t, self.beacon_port))
                    except OSError:              # no route to this subnet: try the others
                        pass
                self._stop.wait(self.interval)
        finally:
            sock.close()
