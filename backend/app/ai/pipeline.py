from .detector import YOLODetector
from .tracker import CentroidTracker
from .zone_detector import zones_for_frame, point_in_zone
from .threat_engine import calculate_threat

class DetectionPipeline:
    def __init__(self, model_path="ai_models/yolo/model.pt", confidence=.45, zones=None, persistence_frames=5):
        self.detector = YOLODetector(model_path, confidence)
        self.tracker = CentroidTracker()
        self.zones = zones or []
        self.persistence_frames = persistence_frames

    def process(self, frame):
        tracked = self.tracker.update(self.detector.detect(frame))
        zones = zones_for_frame(self.zones, frame.shape[1], frame.shape[0])
        for item in tracked:
            item["zone_matches"] = [zone for zone in zones if point_in_zone(item["center"], zone)]
            item["intrusion"] = bool(item["zone_matches"] and item["hits"] >= self.persistence_frames)
        return tracked, calculate_threat(tracked)
