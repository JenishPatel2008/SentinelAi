"""
ANPR module: reads license plate text from a vehicle crop.

Design goals (matches the rest of app/ai/*):
- Lazy-loads heavy deps (ultralytics, easyocr) so importing this file never
  requires GPU/model files to be present.
- Works WITHOUT a dedicated plate-detector model: falls back to a heuristic
  crop of the vehicle's lower-center region, which is where a plate almost
  always sits on front/rear-facing footage (toll booths, gates, barriers).
- If you later train/download a plate-detector .pt, point PLATE_MODEL_PATH
  at it and detection becomes pixel-accurate instead of heuristic.
- Validates OCR output against Indian plate formats and rejects junk before
  it ever reaches the dashboard.
- Aggregates readings per track_id across frames, since a single frame's
  OCR is unreliable but a vehicle is visible for many frames.
"""

import re
from pathlib import Path
from collections import Counter

import numpy as np

# Standard Indian format: SS NN LL NNNN  (e.g. GJ01AB1234)
_STANDARD_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$")
# Bharat series format: NN BH NNNN LL  (e.g. 22BH1234AB)
_BH_RE = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")

# Characters EasyOCR commonly confuses on Indian plates -> canonical fix.
# Applied only as a last-resort pass if the raw string fails validation,
# so we don't silently mangle already-correct reads.
_CONFUSION_MAP = str.maketrans({"O": "0", "I": "1", "S": "5", "B": "8"})


def clean_text(raw: str) -> str:
    """Strip everything but A-Z0-9, uppercase it."""
    return re.sub(r"[^A-Z0-9]", "", raw.upper())


def validate_plate(text: str) -> bool:
    return bool(_STANDARD_RE.match(text) or _BH_RE.match(text))


def normalize_plate(raw: str):
    """
    Try to turn a raw OCR string into a validated Indian plate.
    Returns the cleaned string if valid, else None.
    """
    text = clean_text(raw)
    if validate_plate(text):
        return text
    # Indian plates alternate letter/digit blocks in a fixed pattern, so a
    # character-confusion fix only makes sense applied position-wise, not
    # globally. This is deliberately conservative: it only helps common
    # digit<->letter confusions in the numeric blocks.
    if len(text) in (9, 10):
        fixed = _positional_fix(text)
        if fixed and validate_plate(fixed):
            return fixed
    return None


def _positional_fix(text: str) -> str | None:
    """Best-effort fix assuming standard SS-NN-LL-NNNN layout."""
    if len(text) not in (9, 10):
        return None
    chars = list(text)
    # crude layout guess: 2 letters, 2 digits, 1-2 letters, 4 digits
    letter_zone = {0, 1}
    digit_zones = set(range(len(chars) - 6, len(chars) - 4)) | set(range(len(chars) - 4, len(chars)))
    digit_to_letter = {"0": "O", "1": "I", "5": "S", "8": "B"}
    letter_to_digit = {"O": "0", "I": "1", "S": "5", "B": "8"}
    for i, ch in enumerate(chars):
        if i in letter_zone and ch.isdigit():
            chars[i] = digit_to_letter.get(ch, ch)
        elif i in digit_zones and ch.isalpha():
            chars[i] = letter_to_digit.get(ch, ch)
    return "".join(chars)


class PlateRecognizer:
    """Lazy OCR + optional plate-detector adapter."""

    def __init__(self, plate_model_path: str | Path | None = None, ocr_langs=("en",), min_ocr_confidence=0.35):
        self.plate_model_path = Path(plate_model_path) if plate_model_path else None
        self.ocr_langs = list(ocr_langs)
        self.min_ocr_confidence = min_ocr_confidence
        self._plate_model = None
        self._reader = None

    def _load_plate_model(self):
        if self._plate_model is not None or not self.plate_model_path:
            return
        if not self.plate_model_path.exists():
            # No dedicated model -> silently stay in heuristic-crop mode.
            self.plate_model_path = None
            return
        from ultralytics import YOLO
        self._plate_model = YOLO(str(self.plate_model_path))

    def _load_ocr(self):
        if self._reader is not None:
            return
        import easyocr
        self._reader = easyocr.Reader(self.ocr_langs, gpu=False)

    def _locate_plate_crop(self, frame, vehicle_bbox):
        """Return the sub-image most likely to contain the plate."""
        x1, y1, x2, y2 = map(int, vehicle_bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        vehicle_crop = frame[y1:y2, x1:x2]
        if vehicle_crop.size == 0:
            return None

        self._load_plate_model()
        if self._plate_model is not None:
            results = self._plate_model(vehicle_crop, verbose=False)[0]
            if len(results.boxes):
                # pick highest-confidence plate box
                best = max(results.boxes, key=lambda b: float(b.conf[0]))
                px1, py1, px2, py2 = map(int, best.xyxy[0].tolist())
                plate_crop = vehicle_crop[py1:py2, px1:px2]
                if plate_crop.size > 0:
                    return plate_crop
            return None  # model loaded but found nothing -> don't guess

        # Heuristic fallback: plates on front/rear-facing shots sit in the
        # lower-center ~45% width / ~35% height of the vehicle box.
        h, w = vehicle_crop.shape[:2]
        cx0, cx1 = int(w * 0.20), int(w * 0.80)
        cy0, cy1 = int(h * 0.55), int(h * 0.95)
        return vehicle_crop[cy0:cy1, cx0:cx1]

    def read_plate(self, frame, vehicle_bbox):
        """
        Returns {"text": str, "confidence": float, "raw": str} if a valid
        Indian plate was read, else None.
        """
        plate_crop = self._locate_plate_crop(frame, vehicle_bbox)
        if plate_crop is None or plate_crop.size == 0:
            return None

        # Upscale small crops; EasyOCR struggles under ~100px wide.
        h, w = plate_crop.shape[:2]
        if w < 200:
            scale = 200 / max(w, 1)
            plate_crop = _resize(plate_crop, scale)

        self._load_ocr()
        results = self._reader.readtext(plate_crop)
        if not results:
            return None

        best_text, best_conf = None, 0.0
        for _, raw_text, conf in results:
            if conf < self.min_ocr_confidence:
                continue
            normalized = normalize_plate(raw_text)
            if normalized and conf > best_conf:
                best_text, best_conf = normalized, conf

        if best_text is None:
            return None
        return {"text": best_text, "confidence": float(best_conf)}


def _resize(image, scale):
    import cv2
    h, w = image.shape[:2]
    return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


class PlateAggregator:
    """
    Per-track_id vote-counter. A single frame's OCR is noisy; across the
    ~30-150 frames a vehicle is visible, the correct plate is usually the
    most frequent valid reading. Call add() every frame you get a reading,
    call best() whenever you need the current answer (e.g. for the
    dashboard or when the track disappears).
    """

    def __init__(self):
        self._votes: dict[int, Counter] = {}
        self._best_conf: dict[int, dict[str, float]] = {}

    def add(self, track_id: int, reading: dict | None):
        if reading is None:
            return
        votes = self._votes.setdefault(track_id, Counter())
        votes[reading["text"]] += 1
        confs = self._best_conf.setdefault(track_id, {})
        confs[reading["text"]] = max(confs.get(reading["text"], 0.0), reading["confidence"])

    def best(self, track_id: int):
        votes = self._votes.get(track_id)
        if not votes:
            return None
        text, count = votes.most_common(1)[0]
        return {"text": text, "votes": count, "confidence": self._best_conf[track_id][text]}

    def forget(self, track_id: int):
        self._votes.pop(track_id, None)
        self._best_conf.pop(track_id, None)
