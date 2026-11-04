#!/usr/bin/env python3
"""CSI camera -> MJPEG over HTTP, run on the Jetson HOST (not in Docker).

Why: the CSI camera needs OpenCV built with GStreamer. JetPack's system OpenCV
has it; the pip OpenCV inside the Ultralytics container usually does not.
This bridge uses the system OpenCV (Python 3.6 on JetPack 4) to read the camera
and serves frames that the container can open as a normal URL:

    host:       python3 jetson/camera_bridge.py
    container:  EDGE_SOURCE=http://127.0.0.1:8090/stream.mjpg python3 run_pipeline.py

Also accepts --source <video file or camera index> for testing without a CSI camera.
Keep this file Python 3.6 compatible (JetPack 4 host Python).
"""
import argparse
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2


def csi_pipeline(sensor_id, width, height, fps, flip, out_w, out_h):
    return ("nvarguscamerasrc sensor-id=%d ! video/x-raw(memory:NVMM), width=%d, height=%d, "
            "format=NV12, framerate=%d/1 ! nvvidconv flip-method=%d ! "
            "video/x-raw, width=%d, height=%d, format=BGRx ! videoconvert ! "
            "video/x-raw, format=BGR ! appsink drop=true max-buffers=1"
            % (sensor_id, width, height, fps, flip, out_w, out_h))


class Camera(object):
    """Reads continuously in a thread and keeps only the newest JPEG."""

    def __init__(self, source, out_fps, quality, loop_file):
        self.source, self.loop_file = source, loop_file
        self.period = 1.0 / out_fps
        self.quality = quality
        self.jpeg = None
        self.seq = 0
        self.cond = threading.Condition()
        self.cap = self._open()
        threading.Thread(target=self._run, daemon=True).start()

    def _open(self):
        if isinstance(self.source, str) and "!" in self.source:
            cap = cv2.VideoCapture(self.source, cv2.CAP_GSTREAMER)
        else:
            cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            sys.exit("camera_bridge: cannot open %r" % (self.source,))
        return cap

    def _run(self):
        last = 0.0
        while True:
            ok, frame = self.cap.read()
            if not ok:
                if self.loop_file:
                    self.cap.release()
                    self.cap = self._open()
                    continue
                time.sleep(0.05)
                continue
            now = time.time()
            if now - last < self.period:
                if self.loop_file:            # files read instantly: pace them like a camera
                    time.sleep(self.period - (now - last))
                else:
                    continue
            last = time.time()
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
            if ok:
                with self.cond:
                    self.jpeg = buf.tobytes()
                    self.seq += 1
                    self.cond.notify_all()

    def wait_frame(self, after_seq, timeout=5.0):
        with self.cond:
            if self.seq == after_seq:
                self.cond.wait(timeout)
            return self.seq, self.jpeg


def make_handler(cam):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/snapshot.jpg"):
                _, jpg = cam.wait_frame(-1)
                if jpg is None:
                    self.send_error(503)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(jpg)))
                self.end_headers()
                self.wfile.write(jpg)
                return
            if not self.path.startswith("/stream.mjpg"):
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            seq = 0
            try:
                while True:
                    seq, jpg = cam.wait_frame(seq)
                    if jpg is None:
                        continue
                    self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n")
                    self.wfile.write(("Content-Length: %d\r\n\r\n" % len(jpg)).encode())
                    self.wfile.write(jpg)
                    self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
    return Handler


class ThreadingServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", default="csi",
                    help="'csi' (default), a camera index, a video file, or a GStreamer pipeline")
    ap.add_argument("--sensor-id", type=int, default=0)
    ap.add_argument("--capture", default="1280x720", help="CSI capture size")
    ap.add_argument("--capture-fps", type=int, default=30)
    ap.add_argument("--flip", type=int, default=0, help="nvvidconv flip-method (2 = 180 deg)")
    ap.add_argument("--size", default="640x360", help="output size (match config.FRAME_*)")
    ap.add_argument("--fps", type=float, default=4.0,
                    help="frames served per second; keep >= 1/SAMPLE_INTERVAL_SEC, low to avoid lag")
    ap.add_argument("--quality", type=int, default=85)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    a = ap.parse_args()

    out_w, out_h = [int(v) for v in a.size.split("x")]
    loop_file = False
    if a.source == "csi":
        cw, ch = [int(v) for v in a.capture.split("x")]
        source = csi_pipeline(a.sensor_id, cw, ch, a.capture_fps, a.flip, out_w, out_h)
    elif a.source.isdigit():
        source = int(a.source)
    else:
        source = a.source
        loop_file = "!" not in source
    cam = Camera(source, a.fps, a.quality, loop_file)
    srv = ThreadingServer((a.host, a.port), make_handler(cam))
    print("camera_bridge: http://%s:%d/stream.mjpg  (snapshot: /snapshot.jpg)" % (a.host, a.port))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
