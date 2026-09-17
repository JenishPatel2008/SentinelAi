from datetime import datetime, timedelta

from backend.app.ai.behavior_engine import BehaviorEngine
from backend.app.ai.threat_engine import calculate_threat


ZONE = {"name": "Restricted", "zone_type": "restricted"}


def track(track_id=1, zones=None, moving=False, object_type="person", category=None):
    return {
        "track_id": track_id,
        "class": object_type,
        "category": category,
        "confidence": 0.9,
        "center": (100, 100),
        "movement_distance": 0,
        "moving": moving,
        "zone_matches": zones or [],
    }


def test_extended_presence_and_loitering_are_temporal_and_explainable():
    engine = BehaviorEngine(restricted_zone_dwell_seconds=10, loitering_time_seconds=45)
    start = datetime(2026, 1, 1)

    _, first = engine.update([track(zones=[ZONE])], timestamp=start)
    _, second = engine.update([track(zones=[ZONE])], timestamp=start + timedelta(seconds=10))
    _, third = engine.update([track(zones=[ZONE])], timestamp=start + timedelta(seconds=45))

    assert first == []
    assert second[0]["behavior_type"] == "EXTENDED_RESTRICTED_PRESENCE"
    assert third[0]["behavior_type"] == "LOITERING"
    assert "Present in zone for 45 seconds" in third[0]["behavior_reason"]


def test_repeated_crossing_requires_multiple_zone_interactions():
    engine = BehaviorEngine(fence_crossing_count_threshold=3)
    start = datetime(2026, 1, 1)

    engine.update([track()], timestamp=start)
    engine.update([track(zones=[ZONE])], timestamp=start + timedelta(seconds=1))
    engine.update([track()], timestamp=start + timedelta(seconds=2))
    _, observations = engine.update([track(zones=[ZONE])], timestamp=start + timedelta(seconds=3))

    assert observations[0]["behavior_type"] == "REPEATED_FENCE_CROSSING"
    assert observations[0]["fence_crossings"] == 3


def test_stationary_behavior_and_person_vehicle_proximity():
    engine = BehaviorEngine(stationary_time_seconds=60, proximity_time_seconds=20)
    start = datetime(2026, 1, 1)
    person = track()
    vehicle = track(2, object_type="car", category="vehicle")
    vehicle["center"] = (140, 100)

    engine.update([person, vehicle], timestamp=start)
    _, observations = engine.update([person, vehicle], timestamp=start + timedelta(seconds=20))
    assert observations[0]["behavior_type"] == "PERSON_VEHICLE_PROXIMITY"

    _, observations = engine.update([person, vehicle], timestamp=start + timedelta(seconds=60))
    assert observations == []
    assert engine.states[1]["stationary_started"] == start


def test_behavior_contributes_an_explainable_threat_score():
    behavior = {
        "behavior_type": "REPEATED_FENCE_CROSSING",
        "behavior_reason": "3 fence interactions in the configured window",
    }

    threat = calculate_threat([], behaviors=[behavior])

    assert threat["score"] == 25
    assert threat["behaviors"] == ["REPEATED_FENCE_CROSSING"]
    assert "fence interactions" in threat["reason"]
