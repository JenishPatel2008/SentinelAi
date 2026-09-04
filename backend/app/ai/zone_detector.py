import cv2
import numpy as np

DEFAULT_ZONE = {"id": 1, "name": "Restricted Zone A", "zone_type": "restricted", "points": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": .3}], "enabled": True}

def normalized_to_pixels(points, width, height):
    return [[round(point["x"] * width), round(point["y"] * height)] for point in points]

def zones_for_frame(zones, width, height):
    return [{**zone, "pixel_points": normalized_to_pixels(zone["polygon_points"], width, height)} for zone in zones if zone.get("enabled", True)]

def point_in_zone(point, zone):
    points = zone.get("pixel_points", zone.get("points", []))
    return len(points) >= 3 and cv2.pointPolygonTest(np.array(points, dtype="int32"), point, False) >= 0

def annotate_zones(frame, zones):
    for zone in zones:
        points = np.array(zone.get("pixel_points", zone.get("points", [])), dtype="int32")
        if len(points) >= 3:
            cv2.polylines(frame, [points], True, (70, 80, 230), 2)
            x, y = points[0]
            cv2.putText(frame, zone["name"], (x, max(18, y - 5)), cv2.FONT_HERSHEY_SIMPLEX, .5, (70, 80, 230), 1)
    return frame
