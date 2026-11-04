"""Server-Sent Events fan-out: one bounded queue per browser connection."""
import json
import queue
import threading
import time


def format_sse(event, data):
    return "event: %s\ndata: %s\n\n" % (event, json.dumps(data, separators=(",", ":")))


class EventBus:
    def __init__(self, max_queue=100):
        self.max_queue = max_queue
        self._subs = []
        self._lock = threading.Lock()

    def subscribe(self):
        q = queue.Queue(maxsize=self.max_queue)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def publish(self, event, data):
        data = dict(data)
        data["server_time"] = time.time()
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait((event, data))
            except queue.Full:                  # a stalled tab: drop it, it reconnects
                self.unsubscribe(q)

    def stream(self, q, heartbeat=15):
        """Generator of SSE text for one subscriber; a comment line keeps idle links open."""
        try:
            while True:
                try:
                    event, data = q.get(timeout=heartbeat)
                except queue.Empty:
                    yield ": hb\n\n"
                    continue
                yield format_sse(event, data)
        finally:
            self.unsubscribe(q)
