from pathlib import Path

import cv2
import numpy as np

from .face_detector import crop_face


class SFaceEncoder:
    """Optional OpenCV SFace embedding adapter using cosine similarity."""

    metric = "cosine_similarity"

    def __init__(self, model_path):
        self.model_path = Path(model_path) if model_path else None
        self._recognizer = None

    @property
    def available(self):
        return bool(self.model_path and self.model_path.exists() and hasattr(cv2, "FaceRecognizerSF"))

    def _load(self):
        if not self.available:
            return False
        if self._recognizer is None:
            self._recognizer = cv2.FaceRecognizerSF.create(str(self.model_path), "")
        return True

    def encode(self, frame, face):
        if not self._load():
            return None
        aligned = None
        raw_detection = face.get("raw_detection")
        if raw_detection is not None:
            aligned = self._recognizer.alignCrop(frame, np.asarray(raw_detection, dtype=np.float32))
        if aligned is None or getattr(aligned, "size", 0) == 0:
            aligned = crop_face(frame, face["face_bbox"])
        if aligned is None or aligned.size == 0:
            return None
        aligned = cv2.resize(aligned, (112, 112), interpolation=cv2.INTER_AREA)
        return self._recognizer.feature(aligned).astype(np.float32).reshape(-1)

    def similarity(self, left, right):
        if not self._load():
            return None
        return float(self._recognizer.match(
            np.asarray(left, dtype=np.float32).reshape(1, -1),
            np.asarray(right, dtype=np.float32).reshape(1, -1),
            cv2.FaceRecognizerSF_FR_COSINE,
        ))


def embedding_bytes(embedding):
    return np.asarray(embedding, dtype=np.float32).reshape(-1).tobytes()


def embedding_from_bytes(value, dimension):
    return np.frombuffer(value, dtype=np.float32, count=dimension)
