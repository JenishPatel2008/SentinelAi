import time


def mjpeg_stream(stream_manager, camera_id):
    """Yield the latest processed JPEG frame as an MJPEG response."""
    while True:
        frame = stream_manager.latest_frame(camera_id)
        if frame:
            yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
        elif stream_manager.status(camera_id)["status"] in {"offline", "error"}:
            return
        time.sleep(.05)
