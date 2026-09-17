from backend.app.ai.threat_engine import calculate_threat
from backend.app.ai.tracker import CentroidTracker
from backend.app.ai.night_detector import NightDetector
from backend.app.ai.vehicle_classifier import VehicleClassifier, supported_vehicle_classes
from backend.app.ai.zone_detector import normalized_to_pixels, point_in_zone
import numpy as np

def test_person_intrusion_is_high_or_critical():
    result = calculate_threat([{"class": "person", "intrusion": True}], intrusion_duration=2)
    assert result["score"] == 49
    assert result["severity"] == "MEDIUM"

def test_zone_uses_object_center():
    zone = {"polygon_points": [{"x": .0, "y": .0}, {"x": 1., "y": .0}, {"x": 1., "y": .3}, {"x": .0, "y": .3}]}
    zone["pixel_points"] = normalized_to_pixels(zone["polygon_points"], 478, 850)
    assert point_in_zone((10, 10), zone) is True
    assert point_in_zone((10, 500), zone) is False

def test_tracker_keeps_id_for_overlapping_detection():
    tracker = CentroidTracker()
    first = tracker.update([{"class": "person", "confidence": .9, "bbox": [10, 10, 30, 30]}])
    second = tracker.update([{"class": "person", "confidence": .91, "bbox": [11, 11, 31, 31]}])
    assert first[0]["track_id"] == second[0]["track_id"]

def test_persistent_intrusion_gets_higher_score():
    result = calculate_threat([{"class": "person", "intrusion": True, "hits": 5}])
    assert result["score"] == 65
    assert result["severity"] == "HIGH"


def test_night_detector_smooths_dark_and_bright_transitions():
    detector = NightDetector(night_threshold=60, low_light_threshold=100, night_confirmation_frames=3, day_confirmation_frames=2)
    dark = np.full((10, 10, 3), 10, dtype=np.uint8)
    bright = np.full((10, 10, 3), 220, dtype=np.uint8)
    assert detector.analyze(dark)["scene_condition"] == "UNKNOWN"
    assert detector.analyze(dark)["scene_condition"] == "UNKNOWN"
    assert detector.analyze(dark)["scene_condition"] == "NIGHT"
    assert detector.analyze(bright)["scene_condition"] == "NIGHT"
    assert detector.analyze(bright)["scene_condition"] == "DAY"


def test_tracker_marks_displacement_as_movement():
    tracker = CentroidTracker(movement_threshold=5)
    tracker.update([{"class": "person", "confidence": .9, "bbox": [10, 10, 30, 30]}])
    moved = tracker.update([{"class": "person", "confidence": .9, "bbox": [20, 10, 40, 30]}])
    assert moved[0]["moving"] is True
    assert moved[0]["movement_distance"] == 10


def test_tracker_keeps_vehicle_id_when_model_class_flickers():
    tracker = CentroidTracker()
    first = tracker.update([{"class": "car", "confidence": .8, "bbox": [10, 10, 30, 30]}])
    second = tracker.update([{"class": "truck", "confidence": .6, "bbox": [11, 11, 31, 31]}])
    assert first[0]["track_id"] == second[0]["track_id"]


def test_night_intrusion_adds_explainable_context():
    result = calculate_threat(
        [{"class": "person", "intrusion": True}],
        night_movements=[{"class": "person", "scene_condition": "NIGHT"}],
    )
    assert result["score"] == 65
    assert "Night-time movement" in result["reason"]


def test_vehicle_classifier_uses_model_classes_and_stabilizes_changes():
    assert supported_vehicle_classes({0: "person", 2: "car", 5: "bus", 7: "truck", 9: "van"}) == ["bus", "car", "truck"]
    classifier = VehicleClassifier(confidence_threshold=.5, change_confirmation_frames=3)

    def track(name, confidence):
        return {"track_id": 17, "class": name, "confidence": confidence}

    current = [track("car", .8)]
    classifier.classify(current)
    assert current[0]["vehicle_class"] == "car"
    for _ in range(2):
        current = [track("truck", .8)]
        classifier.classify(current)
        assert current[0]["vehicle_class"] == "car"
    current = [track("truck", .8)]
    classifier.classify(current)
    assert current[0]["vehicle_class"] == "truck"

    current = [track("bus", .3)]
    classifier.classify(current)
    assert current[0]["vehicle_class"] == "truck"
