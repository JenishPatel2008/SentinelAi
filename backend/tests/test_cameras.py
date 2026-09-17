import pytest
from unittest.mock import Mock, patch

from backend.app.database.schemas import CameraCreate, CameraResponse
from backend.app.utils.urls import sanitize_stream_url
from backend.app.video.stream_manager import StreamManager


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
