from pathlib import Path

import numpy as np

from backend.app.ai.anpr import ANPREngine
from backend.app.ai.ocr import is_plausible_plate
from backend.app.ai.plate_detector import PlateDetector


def test_plate_model_relative_path_is_resolved_from_repository_root():
    detector = PlateDetector("ai_models/anpr/plate_model.pt")

    assert detector.model_path.is_absolute()
    assert detector.model_path.parent.name == "anpr"


def test_plate_detector_includes_context_below_vehicle_box():
    detector = PlateDetector()
    seen_shapes = []

    def fake_detect(crop):
        seen_shapes.append(crop.shape[:2])
        return [{"bbox": [10, 10, 40, 20], "confidence": .8}]

    detector.detect = fake_detect
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    result = detector.detect_for_vehicle(frame, {"class": "car", "bbox": [20, 20, 60, 60]})

    assert seen_shapes == [(50, 46)]
    assert result[0]["bbox"] == [27, 28, 57, 38]


def test_plate_validation_accepts_common_international_alphanumeric_format():
    assert is_plausible_plate("NAI3NRU") is True
    assert is_plausible_plate("GJ01AB1234") is True
    assert is_plausible_plate("SR") is False


def test_anpr_prefers_valid_ocr_over_larger_contour():
    class FakePlateDetector:
        def detect_for_vehicle(self, frame, track):
            return [
                {"bbox": [1, 1, 20, 8], "confidence": .9, "crop": frame[:7, :19]},
                {"bbox": [2, 2, 18, 8], "confidence": .5, "crop": frame[:6, :16]},
            ]

    class FakeOCR:
        available = True

        def __init__(self):
            self.calls = 0

        def read(self, crop):
            self.calls += 1
            if self.calls == 1:
                return {"text": "NOISE", "confidence": .99, "processed": crop}
            return {"text": "NAI3NRU", "confidence": .8, "processed": crop}

    engine = ANPREngine(FakePlateDetector(), FakeOCR(), sample_interval=1, min_confidence=.55)
    tracks, observations = engine.observe(
        np.zeros((20, 20, 3), dtype=np.uint8),
        [{"track_id": 1, "class": "car", "confidence": .9, "bbox": [0, 0, 20, 20]}],
        camera_id=1,
        frame_index=1,
    )

    assert observations[0]["plate_number"] == "NAI3NRU"
    assert tracks[0]["plate_number"] == "NAI3NRU"
