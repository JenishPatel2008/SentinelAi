from .detector import YOLODetector
from .tracker import CentroidTracker
from .zone_detector import point_in_zone
from .threat_engine import calculate_threat

class DetectionPipeline:
    def __init__(self, model_path="ai_models/yolo/model.pt", confidence=.45, zone=None):
        self.detector = YOLODetector(model_path, confidence)
        self.tracker = CentroidTracker()
        self.zone = zone

    def process(self, frame):
        tracked = self.tracker.update(self.detector.detect(frame))
        for item in tracked:
            item["intrusion"] = point_in_zone(item["center"], self.zone) if self.zone else False
        return tracked, calculate_threat(tracked)
