from pathlib import Path

import cv2


class FaceDetector:
    """Detect faces inside existing person regions; YuNet is optional, Haar is the local fallback."""

    def __init__(self, model_path=None, min_size=24, confidence_threshold=0.5):
        self.model_path = Path(model_path) if model_path else None
        self.min_size = int(min_size)
        self.confidence_threshold = float(confidence_threshold)
        self._yunet = None
        self._cascade = None

    def _load(self):
        if self.model_path and self.model_path.exists() and hasattr(cv2, "FaceDetectorYN"):
            try:
                self._yunet = cv2.FaceDetectorYN.create(
                    str(self.model_path), "", (320, 320), self.confidence_threshold, 0.3, 5000
                )
                return
            except (cv2.error, OSError):
                self._yunet = None
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(str(cascade_path))
        if self._cascade.empty():
            raise RuntimeError("OpenCV face detector could not be loaded")

    def detect(self, frame, person_bbox=None):
        if self._yunet is None and self._cascade is None:
            self._load()
        height, width = frame.shape[:2]
        offset_x, offset_y = 0, 0
        region = frame
        if person_bbox is not None:
            x1, y1, x2, y2 = [max(0, int(value)) for value in person_bbox]
            x2, y2 = min(width, x2), min(height, y2)
            if x2 <= x1 or y2 <= y1:
                return []
            region = frame[y1:y2, x1:x2]
            offset_x, offset_y = x1, y1
        if region.size == 0:
            return []

        if self._yunet is not None:
            self._yunet.setInputSize((region.shape[1], region.shape[0]))
            _, detections = self._yunet.detect(region)
            result = []
            for detection in detections if detections is not None else []:
                x, y, face_width, face_height = detection[:4]
                confidence = float(detection[14])
                if confidence < self.confidence_threshold or face_width < self.min_size or face_height < self.min_size:
                    continue
                raw_detection = detection.astype("float32").copy()
                raw_detection[0] += offset_x
                raw_detection[1] += offset_y
                for x_index, y_index in ((4, 5), (6, 7), (8, 9), (10, 11), (12, 13)):
                    raw_detection[x_index] += offset_x
                    raw_detection[y_index] += offset_y
                result.append({
                    "face_bbox": [x + offset_x, y + offset_y, x + face_width + offset_x, y + face_height + offset_y],
                    "face_confidence": confidence,
                    "raw_detection": raw_detection.tolist(),
                    "backend": "yunet",
                })
            return result

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        detections = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(self.min_size, self.min_size))
        return [
            {
                "face_bbox": [x + offset_x, y + offset_y, x + face_width + offset_x, y + face_height + offset_y],
                "face_confidence": None,
                "raw_detection": None,
                "backend": "opencv_haar",
            }
            for x, y, face_width, face_height in detections
        ]


def crop_face(frame, face_bbox):
    height, width = frame.shape[:2]
    x1, y1, x2, y2 = [int(value) for value in face_bbox]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(width, x2), min(height, y2)
    return frame[y1:y2, x1:x2]
