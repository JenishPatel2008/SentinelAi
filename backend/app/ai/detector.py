from pathlib import Path

SUPPORTED_CLASSES = {"person", "car", "truck", "motorcycle", "bus", "bicycle"}

class YOLODetector:
    """Lazy YOLO adapter; importing the backend does not require model.pt."""
    def __init__(self, model_path: str | Path = "ai_models/yolo/model.pt", confidence: float = .45, min_width=12, min_height=20, class_confidences=None):
        self.model_path = Path(model_path)
        self.confidence = confidence
        self.model = None
        self.min_width = min_width
        self.min_height = min_height
        self.class_confidences = class_confidences or {}

    def load(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO model not found: {self.model_path}")
        from ultralytics import YOLO
        self.model = YOLO(str(self.model_path))

    def detect(self, frame):
        if self.model is None:
            self.load()
        inference_confidence = min([self.confidence, *self.class_confidences.values()])
        results = self.model(frame, conf=inference_confidence, verbose=False)[0]
        names = results.names
        detections = []
        for box in results.boxes:
            coords = box.xyxy[0].tolist()
            class_id = int(box.cls[0])
            object_class = names[class_id]
            width, height = coords[2] - coords[0], coords[3] - coords[1]
            threshold = self.class_confidences.get(object_class, self.confidence)
            if object_class not in SUPPORTED_CLASSES or float(box.conf[0]) < threshold or width < self.min_width or height < self.min_height:
                continue
            if object_class == "person" and not .15 <= width / max(height, 1) <= 1.25:
                continue
            detections.append({"class": object_class, "confidence": float(box.conf[0]), "bbox": coords})
        return detections
