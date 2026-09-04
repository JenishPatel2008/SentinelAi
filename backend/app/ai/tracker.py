def _iou(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area_a = max(1, a[2] - a[0]) * max(1, a[3] - a[1])
    area_b = max(1, b[2] - b[0]) * max(1, b[3] - b[1])
    return intersection / (area_a + area_b - intersection)

class CentroidTracker:
    """Small dependency-free tracker suitable for the local MVP."""
    def __init__(self, iou_threshold=.25):
        self.iou_threshold = iou_threshold
        self.next_id = 1
        self.tracks = {}

    def update(self, detections):
        updated, used = [], set()
        for detection in detections:
            best_id, best_iou = None, 0
            for track_id, previous in self.tracks.items():
                if track_id in used or previous["class"] != detection["class"]:
                    continue
                overlap = _iou(previous["bbox"], detection["bbox"])
                if overlap > best_iou:
                    best_id, best_iou = track_id, overlap
            track_id = best_id if best_iou >= self.iou_threshold else self.next_id
            if track_id == self.next_id:
                self.next_id += 1
            x1, y1, x2, y2 = detection["bbox"]
            tracked = {**detection, "track_id": track_id, "center": ((x1+x2)/2, (y1+y2)/2)}
            self.tracks[track_id] = tracked
            used.add(track_id)
            updated.append(tracked)
        self.tracks = {x["track_id"]: x for x in updated}
        return updated
