from collections import defaultdict, deque
from datetime import datetime

from .ocr import OCRReader, is_plausible_plate, normalize_plate_text
from .plate_detector import PlateDetector, VEHICLE_CLASSES


class ANPREngine:
    """Sample tracked vehicles and aggregate valid OCR results per track."""

    def __init__(self, plate_detector=None, ocr_reader=None, sample_interval=5, consensus_window=8, min_confidence=.55):
        self.plate_detector = plate_detector or PlateDetector()
        self.ocr_reader = ocr_reader or OCRReader()
        self.sample_interval = max(1, int(sample_interval))
        self.consensus_window = max(1, int(consensus_window))
        self.min_confidence = min_confidence
        self._observations = defaultdict(lambda: deque(maxlen=self.consensus_window))

    def reset(self):
        self._observations.clear()

    def observe(self, frame, tracks, camera_id, frame_index=0, timestamp=None, watchlist=None):
        timestamp = timestamp or datetime.utcnow()
        watchlist = watchlist or {}
        observations = []
        enriched = []
        should_sample = frame_index % self.sample_interval == 0

        for track in tracks:
            result = dict(track)
            track_id = track["track_id"]
            if track.get("class") in VEHICLE_CLASSES and should_sample:
                candidates = self.plate_detector.detect_for_vehicle(frame, track)
                if candidates:
                    candidate = max(candidates, key=lambda item: item["confidence"])
                    ocr = self.ocr_reader.read(candidate["crop"])
                    normalized = normalize_plate_text(ocr.get("text"))
                    valid = is_plausible_plate(normalized) and ocr.get("confidence", 0) >= self.min_confidence
                    plate_number = normalized if valid else "UNKNOWN"
                    if valid:
                        self._observations[track_id].append({"plate_number": plate_number, "confidence": ocr["confidence"]})
                    consensus = self._consensus(track_id)
                    plate_confidence = consensus["plate_confidence"] if consensus else 0.0
                    match = watchlist.get(consensus["plate_number"]) if consensus else None
                    observation = {
                        "camera_id": camera_id,
                        "track_id": track_id,
                        "vehicle_type": track["class"],
                        "vehicle_confidence": track["confidence"],
                        "plate_bbox": candidate["bbox"],
                        "plate_number": consensus["plate_number"] if consensus else plate_number,
                        "plate_confidence": plate_confidence if consensus else round((candidate["confidence"] + ocr.get("confidence", 0)) / 2, 3),
                        "detection_confidence": candidate["confidence"],
                        "ocr_confidence": ocr.get("confidence", 0.0),
                        "original_crop": candidate["crop"],
                        "processed_crop": ocr.get("processed"),
                        "watchlist_match": bool(match),
                        "watchlist_id": match.id if match else None,
                        "watchlist_label": match.label if match else None,
                        "timestamp": timestamp,
                        "ocr_available": self.ocr_reader.available,
                    }
                    observations.append(observation)

            consensus = self._consensus(track_id)
            if consensus:
                result.update(consensus)
                match = watchlist.get(consensus["plate_number"])
                result["watchlist_match"] = bool(match)
                result["watchlist_label"] = match.label if match else None
            result.setdefault("plate_number", "UNKNOWN")
            result.setdefault("plate_confidence", 0.0)
            result.setdefault("watchlist_match", False)
            enriched.append(result)
        return enriched, observations

    def _consensus(self, track_id):
        values = list(self._observations.get(track_id, []))
        if not values:
            return None
        totals = defaultdict(float)
        for item in values:
            totals[item["plate_number"]] += item["confidence"]
        plate_number = max(totals, key=totals.get)
        matching = [item for item in values if item["plate_number"] == plate_number]
        average = sum(item["confidence"] for item in matching) / len(matching)
        agreement = len(matching) / len(values)
        return {"plate_number": plate_number, "plate_confidence": round(.7 * average + .3 * agreement, 3)}
