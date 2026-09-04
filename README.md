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

## API

`/api/cameras`, `/api/alerts`, `/api/events`, `/api/detections`, `/api/analytics`, `/api/streams/start`, and `/api/streams/stop` are available, with `/ws` broadcasting new alerts. Evidence is served from `/evidence/{filename}`.

## MVP limitations

The tracker is a small IoU tracker for local demos. Webcam/RTSP, authentication, advanced GIS, model training, and production-grade streaming are deferred. Threat scores are deterministic demo rules, not validated security assessments.
