import numpy as np

from backend.app.ai.anpr import ANPREngine
from backend.app.ai.ocr import is_plausible_plate, normalize_plate_text


class FakeDetector:
    def detect_for_vehicle(self, frame, track):
        if track["class"] == "car":
            return [{"bbox": [10, 10, 80, 30], "confidence": .9, "crop": frame[10:30, 10:80]}]
        return []


class FakeOCR:
    available = True

    def __init__(self):
        self.calls = 0

    def read(self, crop):
        self.calls += 1
        return {"text": "GJ 01 AB 1234", "confidence": .9, "processed": crop}


def test_plate_normalization_is_context_aware():
    assert normalize_plate_text(" GJ 01 AB 1234 ") == "GJ01AB1234"
    assert is_plausible_plate("GJ01AB1234")
    assert normalize_plate_text("not a plate") == "NOTAPLATE"
    assert not is_plausible_plate("NOTAPLATE")


def test_anpr_associates_only_vehicle_tracks_and_consensus():
    engine = ANPREngine(plate_detector=FakeDetector(), ocr_reader=FakeOCR(), sample_interval=1)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    tracks = [
        {"track_id": 7, "class": "car", "confidence": .93, "bbox": [0, 0, 99, 99]},
        {"track_id": 8, "class": "person", "confidence": .91, "bbox": [0, 0, 99, 99]},
    ]

    enriched, observations = engine.observe(frame, tracks, camera_id=3, frame_index=0)
    assert len(observations) == 1
    assert enriched[0]["plate_number"] == "GJ01AB1234"
    assert enriched[1]["plate_number"] == "UNKNOWN"

    enriched, _ = engine.observe(frame, tracks[:1], camera_id=3, frame_index=1)
    assert enriched[0]["plate_number"] == "GJ01AB1234"
    assert enriched[0]["plate_confidence"] > .8
