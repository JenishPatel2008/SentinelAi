import re
import os

import cv2


def normalize_plate_text(value):
    """Clean OCR output and apply character fixes only at known plate positions."""
    text = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
    if len(text) == 10:
        chars = list(text)
        letter_positions = {0, 1, 4, 5}
        digit_positions = {2, 3, 6, 7, 8, 9}
        for index in letter_positions:
            chars[index] = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"}.get(chars[index], chars[index])
        for index in digit_positions:
            chars[index] = {"O": "0", "I": "1", "Z": "2", "S": "5", "B": "8"}.get(chars[index], chars[index])
        text = "".join(chars)
    return text


def is_plausible_plate(value):
    # Accept common international formats while rejecting short OCR noise.
    return bool(re.fullmatch(r"(?=.*[A-Z])(?=.*[0-9])[A-Z0-9]{5,10}", value or ""))


def preprocess_plate_crop(crop):
    if crop is None or crop.size == 0:
        return None
    enlarged = cv2.resize(crop, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
    contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.GaussianBlur(contrast, (3, 3), 0)


class OCRReader:
    """Optional Tesseract adapter; no OCR result is returned when it is unavailable."""

    def __init__(self):
        self._pytesseract = None
        self.error = None
        try:
            import pytesseract

            if os.getenv("TESSERACT_CMD"):
                pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
            pytesseract.get_tesseract_version()
            self._pytesseract = pytesseract
        except Exception as error:
            self.error = str(error)

    @property
    def available(self):
        return self._pytesseract is not None

    def read(self, crop):
        processed = preprocess_plate_crop(crop)
        if processed is None or not self.available:
            return {"text": None, "confidence": 0.0, "processed": processed}
        best = {"text": None, "confidence": 0.0, "processed": processed}
        variants = [processed, cv2.threshold(processed, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]]
        for variant in variants:
            for psm in (6, 7, 8, 13):
                data = self._pytesseract.image_to_data(
                    variant,
                    config=f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
                    output_type=self._pytesseract.Output.DICT,
                )
                tokens = []
                confidences = []
                for text, confidence in zip(data.get("text", []), data.get("conf", [])):
                    if text.strip():
                        tokens.append(text)
                        try:
                            score = float(confidence)
                            if score >= 0:
                                confidences.append(score / 100)
                        except (TypeError, ValueError):
                            pass
                candidate = "".join(tokens) or None
                confidence = sum(confidences) / len(confidences) if confidences else 0.0
                if candidate and confidence > best["confidence"]:
                    best = {"text": candidate, "confidence": confidence, "processed": processed}
        return best
