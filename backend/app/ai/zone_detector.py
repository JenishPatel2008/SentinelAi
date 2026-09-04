import cv2

DEFAULT_ZONE = {"id": 1, "name": "Restricted Zone A", "points": [[0, 0], [640, 0], [640, 260], [0, 260]], "severity": "high"}

def point_in_zone(point, zone=DEFAULT_ZONE):
    polygon = zone["points"]
    return cv2.pointPolygonTest(__import__("numpy").array(polygon, dtype="int32"), point, False) >= 0

def annotate_zone(frame, zone=DEFAULT_ZONE):
    points = __import__("numpy").array(zone["points"], dtype="int32")
    return cv2.polylines(frame, [points], True, (70, 80, 230), 2)
