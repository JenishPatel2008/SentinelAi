import pytest
import cv2
from pathlib import Path
from threading import Event
from unittest.mock import Mock, patch

from backend.app.database.schemas import CameraCreate, CameraResponse
from backend.app.utils.urls import sanitize_stream_url
from backend.app.video.stream_manager import StreamManager


class FakeCamera:
    id = 101
    source_type = "video"
    stream_url = "data/videos/test.mp4"


def test_rtsp_camera_schema_accepts_valid_url():
    camera = CameraCreate(
        camera_code="RTSP-01",
        name="BOP Camera 01",
        sector="North Border Fence",
        source_type="rtsp",
        stream_url="rtsp://operator:secret@192.168.1.100:554/stream",
    )

    assert camera.stream_url.endswith("/stream")
    assert sanitize_stream_url(camera.stream_url) == "rtsp://operator:****@192.168.1.100:554/stream"


def test_rtsp_camera_schema_rejects_non_rtsp_url():
    with pytest.raises(ValueError, match="RTSP URL"):
        CameraCreate(
            camera_code="RTSP-INVALID",
            name="Invalid",
            sector="North",
            source_type="rtsp",
            stream_url="http://192.168.1.100/stream",
        )


def test_legacy_video_source_type_remains_valid():
    camera = CameraCreate(
        camera_code="MP4-01",
        name="Recorded Camera",
        sector="North",
        source_type="video",
        stream_url="data/videos/test.mp4",
    )

    assert camera.source_type == "video"


def test_rtsp_connection_test_releases_capture():
    capture = Mock()
    capture.isOpened.return_value = True
    capture.read.return_value = (True, object())

    with patch("backend.app.video.stream_manager.cv2.VideoCapture", return_value=capture) as video_capture:
        assert StreamManager.test_connection("rtsp://192.168.1.100:554/stream") is True

    video_capture.assert_called_once_with("rtsp://192.168.1.100:554/stream")
    capture.release.assert_called_once_with()


def test_rtsp_connection_failure_releases_capture():
    capture = Mock()
    capture.isOpened.return_value = False

    with patch("backend.app.video.stream_manager.cv2.VideoCapture", return_value=capture):
        assert StreamManager.test_connection("rtsp://192.168.1.100:554/stream") is False

    capture.release.assert_called_once_with()


def test_local_video_source_resolves_from_project_root():
    resolved = StreamManager.resolve_source("data/videos/test.mp4", "video")

    assert Path(resolved).is_absolute()
    assert Path(resolved).name == "test.mp4"


def test_real_mp4_reads_multiple_consecutive_frames():
    source = Path(__file__).parents[2] / "data" / "videos" / "test.mp4"
    capture = cv2.VideoCapture(str(source))
    try:
        assert capture.isOpened()
        frames = [capture.read() for _ in range(5)]
    finally:
        capture.release()

    assert all(ok for ok, _ in frames)
    assert all(frame is not None for _, frame in frames)


def test_mp4_loops_but_rtsp_does_not():
    assert StreamManager.is_looping_file("video") is True
    assert StreamManager.is_looping_file("mp4") is True
    assert StreamManager.is_looping_file("rtsp") is False


def test_invalid_local_source_does_not_create_worker():
    manager = StreamManager()
    camera = FakeCamera()
    camera.stream_url = "data/videos/does-not-exist.mp4"

    with pytest.raises(ValueError, match="Unable to find"):
        manager.start(camera)

    assert manager.streams == {}


def test_duplicate_start_keeps_one_worker():
    manager = StreamManager()
    worker_started = Event()

    def fake_worker(state, source, source_type):
        worker_started.set()
        state["stop"].wait()

    camera = FakeCamera()
    with patch.object(manager, "_worker", side_effect=fake_worker) as worker:
        manager.start(camera)
        assert worker_started.wait(1)
        first_thread = manager.streams[camera.id]["thread"]
        manager.start(camera)

        assert worker.call_count == 1
        assert manager.streams[camera.id]["thread"] is first_thread
        assert manager.stop(camera.id) is True


def test_stop_then_start_replaces_worker_after_termination():
    manager = StreamManager()
    worker_started = Event()

    def fake_worker(state, source, source_type):
        worker_started.set()
        state["stop"].wait()

    camera = FakeCamera()
    with patch.object(manager, "_worker", side_effect=fake_worker) as worker:
        manager.start(camera)
        assert worker_started.wait(1)
        assert manager.stop(camera.id) is True
        worker_started.clear()
        manager.start(camera)

        assert worker_started.wait(1)
        assert worker.call_count == 2
        assert manager.stop(camera.id) is True
