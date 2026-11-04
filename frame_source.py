import os
import time
import cv2
import config


def csi_pipeline(sensor_id=config.CSI_SENSOR_ID, width=config.CSI_CAPTURE_WIDTH,
                 height=config.CSI_CAPTURE_HEIGHT, fps=config.CSI_CAPTURE_FPS,
                 flip=config.CSI_FLIP):
    """GStreamer pipeline for a Jetson CSI camera (e.g. Raspberry Pi cam v2 / IMX219).
    Scales to FRAME_WIDTH x FRAME_HEIGHT on the hardware converter, not on the CPU."""
    return (
        f"nvarguscamerasrc sensor-id={sensor_id} ! "
        f"video/x-raw(memory:NVMM), width={width}, height={height}, "
        f"format=NV12, framerate={fps}/1 ! "
        f"nvvidconv flip-method={flip} ! "
        f"video/x-raw, width={config.FRAME_WIDTH}, height={config.FRAME_HEIGHT}, format=BGRx ! "
        f"videoconvert ! video/x-raw, format=BGR ! "
        f"appsink drop=true max-buffers=1"
    )


class FrameSource:
    """Yields (frame_index, timestamp, frame) at SAMPLE_INTERVAL_SEC spacing.

    source can be a video file path, an int camera index, "csi" for the Jetson
    CSI camera, or a raw GStreamer pipeline string (anything containing "!").
    """

    def __init__(self, source=config.SOURCE, interval=config.SAMPLE_INTERVAL_SEC):
        if source == "csi":
            source = csi_pipeline()
        is_gst = isinstance(source, str) and "!" in source
        if is_gst:
            self.cap = cv2.VideoCapture(source, cv2.CAP_GSTREAMER)
        else:
            self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            hint = " (is OpenCV built with GStreamer? check cv2.getBuildInformation())" if is_gst else ""
            raise RuntimeError(f"Could not open source: {source}{hint}")
        # Only real files use video time; cameras and pipelines use the wall clock.
        self.is_file = isinstance(source, str) and not is_gst and os.path.isfile(source)
        self.interval = interval
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        # For video files, skip frames to match the interval; for cameras, use the clock.
        self.skip = max(1, int(self.fps * interval))
        self.frame_index = 0
        self._last_time = 0.0

    def frames(self):
        while True:
            ok, frame = self.cap.read()
            if not ok:
                break
            self.frame_index += 1

            if self.is_file:
                if (self.frame_index - 1) % self.skip != 0:
                    continue
                ts = (self.frame_index - 1) / self.fps   # video time in seconds
            else:
                now = time.time()
                if now - self._last_time < self.interval:
                    continue
                self._last_time = now
                ts = now

            if frame.shape[1] != config.FRAME_WIDTH or frame.shape[0] != config.FRAME_HEIGHT:
                frame = cv2.resize(frame, (config.FRAME_WIDTH, config.FRAME_HEIGHT))
            yield self.frame_index, ts, frame

        self.cap.release()
