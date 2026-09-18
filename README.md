# Sentinel AI Border Control Unit

Local MVP for AI-assisted border surveillance. It registers simulated CCTV cameras, processes MP4 frames with OpenCV and an optional Ultralytics YOLO model, tracks objects, evaluates a restricted polygon, creates debounced alerts, saves evidence, and exposes results through FastAPI and WebSocket.

## Stack

- Backend: FastAPI, SQLAlchemy, SQLite, OpenCV, optional Ultralytics YOLO
- Frontend: React, Vite, React Router
- Runtime data: `sentinel.db`, `data/videos/`, and `data/evidence/`

## Run

```powershell
.\venv\Scripts\activate
pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

API docs: `http://127.0.0.1:8000/docs`. Frontend: `http://127.0.0.1:5173`.

## Operator login

The frontend now uses the backend operator session before opening protected views and API routes. The local development defaults are:

- Username: `operator`
- Password: `sentinel`

Set `SENTINEL_OPERATOR_USERNAME`, `SENTINEL_OPERATOR_PASSWORD`, and `SENTINEL_AUTH_SECRET` before starting the backend to replace them.

## Demo data

Place MP4 files under `data/videos/`. Register one with `POST /api/cameras`:

```json
{
  "camera_code": "CAM-DEMO-01",
  "name": "Demo Intrusion Camera",
  "sector": "Sector 04",
  "stream_url": "data/videos/intrusion.mp4",
  "source_type": "video"
}
```

Place the trained model at `ai_models/yolo/model.pt`. Without it, the backend stays healthy and reports the missing model when processing is requested; it never fabricates detections.

## RTSP cameras

Sentinel can ingest a live IP camera through an RTSP URL and sends its frames through the same OpenCV, YOLO, IoU tracking, zone, alert, evidence, and WebSocket pipeline used for MP4 sources. Most browsers cannot play RTSP directly, so the backend provides the browser MJPEG preview.

In **Cameras**, choose **RTSP / IP Camera**, enter the complete URL, and use **Test Connection** before saving. Use the URL supplied by your camera vendor, for example:

```text
rtsp://username:password@192.168.1.100:554/stream
```

The test confirms that the backend can open and read the stream; a syntactically valid URL alone is not treated as online. Start the saved camera from **Live Monitoring**. The camera and the Sentinel PC must be able to reach each other on the same LAN or routed network.

API equivalents:

```text
POST /api/cameras/test-rtsp
{"stream_url":"rtsp://192.168.1.100:554/stream"}
```

```text
POST /api/cameras
{"camera_code":"BOP-01","name":"BOP Camera 01","sector":"North Border Fence","source_type":"rtsp","stream_url":"rtsp://192.168.1.100:554/stream"}
```

RTSP connection failures are reported as offline and retried with backoff. Passwords are stored for the camera connection but masked in camera API responses and are not included in user-facing errors. Do not commit real camera URLs or credentials.

## API

`/api/auth/login`, `/api/auth/me`, `/api/cameras`, `/api/cameras/test-rtsp`, `/api/alerts`, `/api/events`, `/api/detections`, `/api/analytics`, `/api/settings`, `/api/plates/history`, `/api/watchlist`, `/api/streams/start`, and `/api/streams/stop` are available to an authenticated operator, with `/ws?token=...` broadcasting new alerts and ANPR observations. Evidence is served from `/evidence/{filename}`.

## MVP limitations

The tracker is a small IoU tracker for local demos. Advanced GIS, model training, and production-grade streaming are deferred. Threat scores are deterministic demo rules, not validated security assessments. Operator authentication is a local HMAC-signed session suitable for this MVP, not a complete enterprise identity system.
## Automatic Number Plate Recognition (ANPR)

ANPR is integrated into the shared MP4/RTSP worker after vehicle tracking. It samples tracked vehicle crops, detects plate candidates, preprocesses the crop, optionally runs Tesseract OCR, and aggregates valid results per track. Unreadable or unavailable OCR is recorded as `UNKNOWN`; the system never invents a plate number.

### ANPR setup

Install the Python dependencies from `requirements.txt`, then install the Tesseract executable separately and either add it to `PATH` or set `TESSERACT_CMD` to its full path. A dedicated one-class Ultralytics plate detector can be supplied with:

```powershell
$env:PLATE_MODEL_PATH = "ai_models/anpr/plate_model.pt"
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

If `PLATE_MODEL_PATH` is absent, Sentinel uses a conservative OpenCV contour fallback to locate plate-shaped regions inside vehicle boxes. This fallback can store `UNKNOWN` observations, but reliable ANPR requires a suitable plate model and visible, sufficiently large plates.

The sampling interval and OCR threshold are configurable through `/api/settings` as `anpr_frame_interval` and `anpr_min_ocr_confidence`. Plate observations are available at `GET /api/plates/history`; local watchlist entries are managed with `/api/watchlist`. Watchlist matches influence only intrusion threat scoring, not every vehicle detection.

### ANPR demonstration

1. Start the backend with `python -m uvicorn backend.app.main:app --reload` from the repository root.
2. Start the frontend with `npm run dev` from `frontend`.
3. Register `data/videos/test.mp4` as an MP4 camera and start it from Live Monitoring.
4. Open Plate History to inspect actual observations and their evidence crops. `UNKNOWN` means the detector/OCR could not produce a sufficiently confident valid plate.
5. To test a local watchlist, POST a synthetic registration such as `GJ01AB1234` to `/api/watchlist`; do not use real personal data.

ANPR accuracy depends on camera resolution, distance, lighting, motion blur, plate angle, compression, and visibility. The feature does not claim perfect recognition.

## Night-time movement detection

Night detection runs inside the shared MP4/RTSP worker after YOLO tracking. It calculates grayscale mean brightness, classifies the scene as `DAY`, `LOW_LIGHT`, or `NIGHT`, and requires consecutive confirmation frames before changing state. Tracked-object center displacement determines `moving`; night movement is sampled without adding a second motion detector.

Defaults are available through `/api/settings`: `night_brightness_threshold=60`, `low_light_brightness_threshold=100`, `night_confirmation_frames=5`, `day_confirmation_frames=5`, `movement_threshold=12`, and `night_alert_cooldown=30`. Safe-zone movement creates a rate-limited `night_movement` event. Restricted-zone night movement is passed to the existing threat engine and creates a `night_intrusion` alert with the normal evidence snapshot and explainable reason.

The test video is not assumed to be nighttime. For deterministic tests, use darkened frames with the `NightDetector` unit tests. Actual accuracy depends on exposure, infrared illumination, image noise, weather, camera placement, and visibility; complete darkness cannot guarantee movement detection.

## Explicit vehicle classification

Vehicle classification reuses the class already emitted by the configured YOLO model after tracking. The verified COCO model currently supports these vehicle classes: `bicycle` (class ID 1), `car` (2), `motorcycle` (3), `bus` (5), and `truck` (7). It does not support `van` or a generic `other vehicle` class, so those labels are never fabricated; low-confidence results are reported as `unknown`.

The classifier keeps a short history per track and requires repeated observations before changing a confirmed class. Defaults are available through `/api/settings`: `vehicle_class_confidence_threshold=0.5`, `vehicle_class_history_size=5`, and `vehicle_class_change_confirmation_frames=3`. These values affect classification only and do not create a second detector or tracker.

Vehicle class and confidence are returned by `/api/detections`, `/api/events`, `/api/alerts`, and `/api/analytics`, included in evidence-related alert metadata, sent in live scene WebSocket messages, and shown in Live Monitoring, Events, Alerts, and Analytics. Classification is contextual: zone, movement, night context, and the existing threat engine still determine security severity. Accuracy depends on the underlying YOLO model and camera quality.

## Suspicious activity detection

The shared camera worker now evaluates temporal behavior over persistent IoU track IDs. It does not use a second detector or infer intent. Supported explainable signals are `LOITERING`, `EXTENDED_RESTRICTED_PRESENCE`, `REPEATED_FENCE_CROSSING`, `PROLONGED_STATIONARY`, and conservative `PERSON_VEHICLE_PROXIMITY` when a person and a supported vehicle remain close for the configured duration.

Defaults are available through `/api/settings`: loitering after 45 seconds with at most 80 pixels of accumulated movement, restricted-zone presence after 10 seconds, three zone-boundary interactions within 120 seconds, stationary behavior after 60 seconds, person-vehicle proximity within 100 pixels for 20 seconds, a 30-second behavior alert cooldown, and 180-second missing-track cleanup. Changes apply to newly started workers.

Behavior alerts use the existing evidence snapshot, SQLite event/alert records, WebSocket `alert` messages, and operator confirm/decline flow. Confirming an alert uses the existing laptop alarm path; declining it does not play audio. The Alerts, Event Archive, Live Monitoring, and Analytics views show behavior type, state, reason, or duration where available.

Behavior rules are conservative and camera-coordinate based. They do not claim identity, intent, group behavior, reliable direction-change semantics, or production security accuracy. A signal is only produced when the required track continuity and configured temporal thresholds are satisfied.

## Trusted persons, face detection, and optional recognition

Face intelligence is an enrichment layer after the existing YOLO person track. Sentinel crops each existing person bounding box, detects a face, checks size/blur/brightness, and only then optionally runs OpenCV SFace embedding recognition. It never creates a face tracker and it never treats an unrecognized face as proof of malicious intent.

Face detection works with the OpenCV Haar cascade bundled with the installed OpenCV package. Optional higher-quality YuNet detection uses `ai_models/face/face_detection_yunet_2023mar.onnx`. Recognition uses the OpenCV SFace encoder at `ai_models/face/face_recognition_sface_2021dec.onnx`; recognition remains unavailable, rather than fabricating identities, until that model is installed and `face_recognition_enabled` is enabled through Settings or `/api/settings`.

The SFace matcher uses cosine similarity. The default threshold is `0.363`, so a candidate is recognized only when its cosine similarity is at least that value. Three consistent observations are required by default (`face_recognition_confirmation_frames=3`); temporary unknown or obstructed frames do not immediately replace a confirmed track identity, and repeated failures eventually return the track to unverified.

To install the optional OpenCV Zoo models from PowerShell:

```powershell
New-Item -ItemType Directory -Force ai_models/face | Out-Null
Invoke-WebRequest https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx -OutFile ai_models/face/face_detection_yunet_2023mar.onnx
Invoke-WebRequest https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx -OutFile ai_models/face/face_recognition_sface_2021dec.onnx
```

Register synthetic or explicitly authorized test identities from **Trusted Persons**. Reference images must contain exactly one usable face. Embeddings are stored privately in SQLite and are not returned by subject APIs, observations, alerts, events, WebSockets, logs, or the frontend. The MVP does not provide encryption/key management for the local SQLite embedding blob, so access to `sentinel.db` must be restricted and retention should be managed by the operator.

Protected zones can be selected in the Zone Editor with security mode `PROTECTED` and trusted-person policy `ONLY_TRUSTED`. Existing zones default to `MONITORED`, preserving their prior behavior. In a protected zone, a recognized enabled subject is shown as trusted and does not trigger an identity-only intrusion; an unknown, unverified, obstructed, or not-attempted person is treated as an unverified protected-zone presence and evaluated by the existing threat engine. This includes a backend alarm state, evidence, alert, event, WebSocket message, and incident. Alarm acknowledgement or silencing does not resolve the incident.

Useful endpoints are `/api/face-subjects`, `/api/face-subjects/{id}`, `/api/face-subjects/{id}/reference`, `/api/face-subjects/observations/list`, `/api/alarms/{alert_id}`, `/api/alarms/{alert_id}/acknowledge`, `/api/alarms/{alert_id}/silence`, and `/api/incidents`. No endpoint exposes embedding vectors. Face processing uses the same worker for MP4 and RTSP sources.

Unknown or obstructed status is an identity-verification result, not a criminal or intent classification. Recognition accuracy depends on the SFace/YuNet models, pose, resolution, lighting, blur, occlusion, camera placement, and track continuity.
