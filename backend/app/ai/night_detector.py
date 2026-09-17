from collections import deque

import cv2


class NightDetector:
    """Estimate scene lighting and smooth transitions to avoid frame-level flicker."""

    def __init__(self, night_threshold=60, low_light_threshold=100, night_confirmation_frames=5, day_confirmation_frames=5):
        self.night_threshold = night_threshold
        self.low_light_threshold = max(night_threshold, low_light_threshold)
        self.night_confirmation_frames = max(1, night_confirmation_frames)
        self.day_confirmation_frames = max(1, day_confirmation_frames)
        self.condition = "UNKNOWN"
        self._candidate = None
        self._candidate_count = 0
        self.history = deque(maxlen=max(self.night_confirmation_frames, self.day_confirmation_frames))

    def reset(self):
        self.condition = "UNKNOWN"
        self._candidate = None
        self._candidate_count = 0
        self.history.clear()

    def analyze(self, frame):
        if frame is None or getattr(frame, "size", 0) == 0:
            return {"scene_condition": "UNKNOWN", "brightness": None, "night_confidence": 0.0}
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = float(gray.mean())
            dark_pixels = float((gray < self.night_threshold).mean())
            raw = self._classify(brightness)
            self._smooth(raw)
            confidence = max(0.0, min(1.0, (self.night_threshold - brightness) / max(self.night_threshold, 1)))
            if self.condition == "LOW_LIGHT":
                confidence = max(confidence, .5)
            return {
                "scene_condition": self.condition,
                "raw_condition": raw,
                "brightness": round(brightness, 2),
                "dark_pixel_ratio": round(dark_pixels, 3),
                "night_confidence": round(confidence, 3),
            }
        except (cv2.error, TypeError, ValueError):
            return {"scene_condition": "UNKNOWN", "brightness": None, "night_confidence": 0.0}

    def _classify(self, brightness):
        if brightness <= self.night_threshold:
            return "NIGHT"
        if brightness <= self.low_light_threshold:
            return "LOW_LIGHT"
        return "DAY"

    def _smooth(self, raw):
        self.history.append(raw)
        if raw == self.condition:
            self._candidate = None
            self._candidate_count = 0
            return
        if raw == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = raw
            self._candidate_count = 1
        required = self.day_confirmation_frames if raw == "DAY" else self.night_confirmation_frames
        if self._candidate_count >= required:
            self.condition = raw
            self._candidate = None
            self._candidate_count = 0
