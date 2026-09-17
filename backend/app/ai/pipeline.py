from .detector import YOLODetector
from .tracker import CentroidTracker
from .zone_detector import zones_for_frame, point_in_zone
from .threat_engine import calculate_threat
from .vehicle_classifier import VehicleClassifier

class DetectionPipeline:
    def __init__(self, model_path="ai_models/yolo/model.pt", confidence=.45, zones=None, persistence_frames=1, class_confidences=None, movement_threshold=12, vehicle_class_confidence=.5, vehicle_class_history_size=5, vehicle_class_change_confirmation_frames=3):
        self.detector = YOLODetector(model_path, confidence, class_confidences=class_confidences)
        self.tracker = CentroidTracker(movement_threshold=movement_threshold)
        self.vehicle_classifier = VehicleClassifier(vehicle_class_confidence, vehicle_class_history_size, vehicle_class_change_confirmation_frames)
        self.zones = zones or []
        self.persistence_frames = persistence_frames

    def process(self, frame):
        tracked = self.tracker.update(self.detector.detect(frame))
        tracked = self.vehicle_classifier.classify(tracked)
        zones = zones_for_frame(self.zones, frame.shape[1], frame.shape[0])
        for item in tracked:
            item["zone_matches"] = [zone for zone in zones if point_in_zone(item["center"], zone)]
            item["intrusion"] = bool(item["zone_matches"] and item["hits"] >= self.persistence_frames)
        return tracked, calculate_threat(tracked)

    def reset(self):
        self.tracker.reset()
        self.vehicle_classifier.reset()
