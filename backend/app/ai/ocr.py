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
    return bool(re.fullmatch(r"[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{3,4}", value or ""))


def preprocess_plate_crop(crop):
    if crop is None or crop.size == 0:
        return None
    enlarged = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
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
        data = self._pytesseract.image_to_data(
            processed,
            config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            output_type=self._pytesseract.Output.DICT,
        )
        tokens = []
        confidences = []
        for text, confidence in zip(data.get("text", []), data.get("conf", [])):
            if text.strip():
                tokens.append(text)
                try:
                    if float(confidence) >= 0:
                        confidences.append(float(confidence) / 100)
                except (TypeError, ValueError):
                    pass
        return {
            "text": "".join(tokens) or None,
            "confidence": sum(confidences) / len(confidences) if confidences else 0.0,
            "processed": processed,
        }
