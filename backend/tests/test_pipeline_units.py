from backend.app.ai.threat_engine import calculate_threat
from backend.app.ai.tracker import CentroidTracker
from backend.app.ai.zone_detector import point_in_zone

def test_person_intrusion_is_high_or_critical():
    result = calculate_threat([{"class": "person", "intrusion": True}], intrusion_duration=2)
    assert result["score"] == 64
    assert result["severity"] == "HIGH"

def test_zone_uses_object_center():
    assert point_in_zone((10, 10)) is True
    assert point_in_zone((10, 500)) is False

def test_tracker_keeps_id_for_overlapping_detection():
    tracker = CentroidTracker()
    first = tracker.update([{"class": "person", "confidence": .9, "bbox": [10, 10, 30, 30]}])
    second = tracker.update([{"class": "person", "confidence": .91, "bbox": [11, 11, 31, 31]}])
    assert first[0]["track_id"] == second[0]["track_id"]
