import os
from pathlib import Path

import cv2


VEHICLE_CLASSES = {"car", "truck", "motorcycle", "bus", "bicycle"}


class PlateDetector:
    """Detect plates inside vehicle crops using an optional YOLO model or CV fallback."""

    def __init__(self, model_path=None, confidence=0.35):
        self.model_path = Path(model_path or os.getenv("PLATE_MODEL_PATH", "ai_models/anpr/plate_model.pt"))
        if not self.model_path.is_absolute():
            project_root = Path(__file__).resolve().parents[3]
            self.model_path = project_root / self.model_path
        self.confidence = confidence
        self.model = None
        self.model_error = None

    @property
    def available(self):
        return self.model_path.exists() or self.model_error is None

    def _load_model(self):
        if self.model is not None or self.model_error is not None:
            return
        if not self.model_path.exists():
            return
        try:
            from ultralytics import YOLO

            self.model = YOLO(str(self.model_path))
        except Exception as error:  # Keep the general detector usable if ANPR setup is incomplete.
            self.model_error = str(error)

    def detect(self, vehicle_crop):
        """Return local plate boxes as {bbox, confidence}."""
        self._load_model()
        if self.model is not None:
            results = self.model(vehicle_crop, conf=self.confidence, verbose=False)[0]
            return [
                {"bbox": box.xyxy[0].tolist(), "confidence": float(box.conf[0])}
                for box in results.boxes
            ]
        return self._detect_with_contours(vehicle_crop)

    @staticmethod
    def _detect_with_contours(image):
        if image is None or image.size == 0:
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bilateralFilter(gray, 7, 45, 45)
        edges = cv2.Canny(gray, 80, 180)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        height, width = gray.shape[:2]
        candidates = []
        for contour in contours:
            x, y, box_width, box_height = cv2.boundingRect(contour)
            ratio = box_width / max(box_height, 1)
            area = box_width * box_height
            if not 2.0 <= ratio <= 7.0 or area < max(80, width * height * 0.002):
                continue
            if box_width < 30 or box_height < 8 or box_width > width * 0.95 or box_height > height * 0.35:
                continue
            center_y = (y + box_height / 2) / max(height, 1)
            width_ratio = box_width / max(width, 1)
            # Vehicle plates are usually low in the vehicle crop. Penalize
            # full-width bumper/hood contours that otherwise win by area.
            lower_region_score = min(1.0, max(0.0, (center_y - 0.35) / 0.5))
            size_score = 1.0 - min(1.0, abs(width_ratio - 0.48) / 0.48)
            ratio_score = 1.0 - min(1.0, abs(ratio - 4.0) / 4.0)
            confidence = round(0.2 + 0.25 * lower_region_score + 0.25 * size_score + 0.3 * ratio_score, 3)
            candidates.append({
                "bbox": [x, y, x + box_width, y + box_height],
                "confidence": confidence,
            })
        return sorted(candidates, key=lambda item: item["confidence"], reverse=True)[:5]

    def detect_for_vehicle(self, frame, track):
        if track.get("class") not in VEHICLE_CLASSES:
            return []
        frame_height, frame_width = frame.shape[:2]
        x1, y1, x2, y2 = [int(value) for value in track["bbox"]]
        # Detector boxes can stop at the bumper while the plate extends below
        # them. Include a small context margin before searching for the plate.
        vehicle_width, vehicle_height = max(1, x2 - x1), max(1, y2 - y1)
        x1 -= int(vehicle_width * 0.08)
        y1 -= int(vehicle_height * 0.05)
        x2 += int(vehicle_width * 0.08)
        y2 += int(vehicle_height * 0.2)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame_width, x2), min(frame_height, y2)
        if x2 <= x1 or y2 <= y1:
            return []
        vehicle_crop = frame[y1:y2, x1:x2]
        results = []
        for candidate in self.detect(vehicle_crop):
            px1, py1, px2, py2 = candidate["bbox"]
            # Detector coordinates are local to vehicle_crop, so translate
            # them back into full-frame coordinates before slicing the image.
            gx1, gy1 = max(x1, x1 + int(px1)), max(y1, y1 + int(py1))
            gx2, gy2 = min(x2, x1 + int(px2)), min(y2, y1 + int(py2))
            if gx2 <= gx1 or gy2 <= gy1:
                continue
            results.append({
                "bbox": [gx1, gy1, gx2, gy2],
                "confidence": float(candidate.get("confidence", 0)),
                "crop": frame[gy1:gy2, gx1:gx2].copy(),
            })
        return results
