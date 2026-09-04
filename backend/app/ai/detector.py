from pathlib import Path

class YOLODetector:
    """Lazy YOLO adapter; importing the backend does not require model.pt."""
    def __init__(self, model_path: str | Path = "ai_models/yolo/model.pt", confidence: float = .45):
        self.model_path = Path(model_path)
        self.confidence = confidence
        self.model = None

    def load(self):
        if not self.model_path.exists():
            raise FileNotFoundError(f"YOLO model not found: {self.model_path}")
        from ultralytics import YOLO
        self.model = YOLO(str(self.model_path))

    def detect(self, frame):
        if self.model is None:
            self.load()
        results = self.model(frame, conf=self.confidence, verbose=False)[0]
        names = results.names
        detections = []
        for box in results.boxes:
            coords = box.xyxy[0].tolist()
            class_id = int(box.cls[0])
            detections.append({"class": names[class_id], "confidence": float(box.conf[0]), "bbox": coords})
        return detections
