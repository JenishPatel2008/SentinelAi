import cv2


def assess_face_quality(face_crop, min_size=24, min_blur=35.0, min_brightness=25.0, max_brightness=235.0):
    if face_crop is None or face_crop.size == 0:
        return {"usable": False, "reason": "face unavailable"}
    height, width = face_crop.shape[:2]
    if min(width, height) < min_size:
        return {"usable": False, "reason": "face too small"}
    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    if blur_score < min_blur:
        return {"usable": False, "reason": "face too blurry", "blur_score": blur_score, "brightness": brightness}
    if not min_brightness <= brightness <= max_brightness:
        return {"usable": False, "reason": "face lighting is insufficient", "blur_score": blur_score, "brightness": brightness}
    return {"usable": True, "reason": "face quality sufficient", "blur_score": blur_score, "brightness": brightness}
