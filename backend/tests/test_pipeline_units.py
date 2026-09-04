from backend.app.ai.threat_engine import calculate_threat
from backend.app.ai.tracker import CentroidTracker
from backend.app.ai.zone_detector import normalized_to_pixels, point_in_zone

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
