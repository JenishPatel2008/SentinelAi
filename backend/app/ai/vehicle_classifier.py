from collections import Counter, defaultdict, deque


MODEL_VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "bus", "truck"}
VEHICLE_CLASS_ALIASES = {name: name for name in MODEL_VEHICLE_CLASSES}


class VehicleClassifier:
    """Canonicalize and stabilize the vehicle class already produced by YOLO."""

    def __init__(self, confidence_threshold=.5, history_size=5, change_confirmation_frames=3):
        self.confidence_threshold = confidence_threshold
        self.history_size = max(1, history_size)
        self.change_confirmation_frames = max(1, change_confirmation_frames)
        self.history = defaultdict(lambda: deque(maxlen=self.history_size))
        self.confirmed = {}
        self.candidates = {}

    def reset(self):
        self.history.clear()
        self.confirmed.clear()
        self.candidates.clear()

    def classify(self, tracks):
        for track in tracks:
            if track.get("class") not in MODEL_VEHICLE_CLASSES:
                track["category"] = "person" if track.get("class") == "person" else "other"
                continue
            detected_class = VEHICLE_CLASS_ALIASES.get(track.get("class"))
            confidence = float(track.get("confidence", 0))
            track["category"] = "vehicle"
            if not detected_class or confidence < self.confidence_threshold:
                track["vehicle_class"] = self.confirmed.get(track["track_id"], "unknown")
                track["vehicle_class_confidence"] = confidence
                continue

            track_id = track["track_id"]
            self.history[track_id].append((detected_class, confidence))
            current = self.confirmed.get(track_id)
            if current is None:
                self.confirmed[track_id] = detected_class
                self.candidates.pop(track_id, None)
            elif detected_class != current:
                candidate, count = self.candidates.get(track_id, (None, 0))
                count = count + 1 if candidate == detected_class else 1
                self.candidates[track_id] = (detected_class, count)
                if count >= self.change_confirmation_frames:
                    self.confirmed[track_id] = detected_class
                    self.candidates.pop(track_id, None)
            else:
                self.candidates.pop(track_id, None)

            confirmed_class = self.confirmed.get(track_id, "unknown")
            matching = [confidence for name, confidence in self.history[track_id] if name == confirmed_class]
            track["vehicle_class"] = confirmed_class
            track["vehicle_class_confidence"] = round(sum(matching) / len(matching), 3) if matching else confidence
        return tracks


def supported_vehicle_classes(model_names):
    """Return only canonical vehicle classes actually present in model metadata."""
    names = set(model_names.values()) if isinstance(model_names, dict) else set(model_names)
    return sorted(names.intersection(MODEL_VEHICLE_CLASSES))
