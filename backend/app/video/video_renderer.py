import time


def mjpeg_stream(stream_manager, camera_id):
    """Yield the latest processed JPEG frame as an MJPEG response."""
    while True:
        status = stream_manager.status(camera_id)["status"]
        if status in {"offline", "error", "stalled"}:
            return
        frame = stream_manager.latest_frame(camera_id)
        if frame:
            yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
        time.sleep(.05)
