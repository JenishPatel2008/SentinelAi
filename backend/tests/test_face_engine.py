from datetime import datetime, timedelta

import numpy as np

from backend.app.ai.face_engine import FaceIntelligence
from backend.app.ai.face_quality import assess_face_quality


class FakeDetector:
    def __init__(self, face=True):
        self.face = face

    def detect(self, frame, bbox):
        if not self.face:
            return []
        x1, y1, _, _ = bbox
        return [{"face_bbox": [x1 + 10, y1 + 10, x1 + 70, y1 + 70], "face_confidence": 0.9, "raw_detection": None, "backend": "test"}]


class FakeEncoder:
    available = True
    metric = "cosine_similarity"

    def encode(self, frame, face):
        return np.ones(4, dtype=np.float32) if face["face_bbox"][0] <= 10 else np.zeros(4, dtype=np.float32)

    def similarity(self, left, right):
        return 0.91 if np.array_equal(left, right) else 0.1


def frame():
    image = np.zeros((120, 120, 3), dtype=np.uint8)
    image[:] = 120
    image[20:80:2, 20:80:2] = 220
    return image


def track(track_id):
    return {"track_id": track_id, "class": "person", "bbox": [(track_id - 1) * 2, 0, 100, 100], "zone_matches": []}


def test_quality_rejects_tiny_face_without_forcing_identity():
    result = assess_face_quality(np.zeros((8, 8, 3), dtype=np.uint8))
    assert result["usable"] is False
    assert result["reason"] == "face too small"


def test_identity_requires_multi_frame_confirmation():
    engine = FaceIntelligence(FakeDetector(), FakeEncoder(), enabled=True, confirmation_frames=3, sample_interval=1)
    subjects = [{"id": 1, "label": "Synthetic Authorized", "category": "authorized", "enabled": True, "embedding": np.ones(4, dtype=np.float32)}]
    start = datetime(2026, 1, 1)

    tracks, _, events = engine.update(frame(), [track(1)], subjects, start)
    assert tracks[0]["identity_status"] == "unknown"
    assert not any(event["event_type"] == "IDENTITY_RECOGNIZED" for event in events)
    engine.update(frame(), [track(1)], subjects, start + timedelta(seconds=1))
    tracks, _, events = engine.update(frame(), [track(1)], subjects, start + timedelta(seconds=2))

    assert tracks[0]["identity_status"] == "trusted"
    assert tracks[0]["subject_id"] == 1
    assert any(event["event_type"] == "IDENTITY_RECOGNIZED" for event in events)


def test_two_tracks_keep_independent_identity_state():
    engine = FaceIntelligence(FakeDetector(), FakeEncoder(), enabled=True, confirmation_frames=1, sample_interval=1)
    subjects = [
        {"id": 1, "label": "Synthetic One", "category": "authorized", "enabled": True, "embedding": np.ones(4, dtype=np.float32)},
        {"id": 2, "label": "Synthetic Two", "category": "authorized", "enabled": True, "embedding": np.zeros(4, dtype=np.float32)},
    ]
    tracks, _, _ = engine.update(frame(), [track(1), track(2)], subjects, datetime(2026, 1, 1))

    assert tracks[0]["subject_id"] == 1
    assert tracks[1]["subject_id"] == 2
    assert engine.states[1]["confirmed_subject_id"] == 1
    assert engine.states[2]["confirmed_subject_id"] == 2


def test_missing_face_is_unverified_not_malicious():
    engine = FaceIntelligence(FakeDetector(face=False), FakeEncoder(), enabled=True, sample_interval=1)
    tracks, _, events = engine.update(frame(), [track(7)], [], datetime(2026, 1, 1))

    assert tracks[0]["face_status"] == "unavailable"
    assert tracks[0]["identity_status"] == "unverified"
    assert not any(event["event_type"] == "IDENTITY_RECOGNIZED" for event in events)
