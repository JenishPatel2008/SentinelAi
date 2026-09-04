from threading import Lock
import cv2

class StreamManager:
    def __init__(self):
        self.captures, self.lock = {}, Lock()

    def start(self, camera):
        source = camera.stream_url
        if not source:
            raise ValueError("Camera has no video source configured")
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            capture.release()
            raise ValueError(f"Unable to open video source: {source}")
        with self.lock:
            self.captures[camera.id] = capture

    def stop(self, camera_id):
        with self.lock:
            capture = self.captures.pop(camera_id, None)
        if capture:
            capture.release()

    def read(self, camera_id):
        capture = self.captures.get(camera_id)
        if capture is None:
            return None
        ok, frame = capture.read()
        if not ok:
            self.stop(camera_id)
            return None
        return frame

stream_manager = StreamManager()
