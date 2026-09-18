"""
Standalone ANPR test harness.

Runs vehicle detection + tracking + plate OCR on a video file, with no
FastAPI app, database, or frontend involved. Use this to validate the ANPR
module in isolation before wiring it into frame_processor.py / stream_manager.py.

Usage:
    python scripts/test_anpr.py path/to/video.mp4
    python scripts/test_anpr.py path/to/video.mp4 --plate-model ai_models/yolo/plate_detector.pt
    python scripts/test_anpr.py path/to/video.mp4 --max-frames 300 --show

Output:
    - Prints each newly-confirmed plate as it's recognized.
    - Writes an annotated video to runs/anpr_test/<input_name>_annotated.mp4
    - Prints a final summary table of track_id -> best plate.
"""

import argparse
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.ai.detector import YOLODetector  # noqa: E402
from app.ai.tracker import CentroidTracker  # noqa: E402
from app.ai.plate_recognizer import PlateRecognizer, PlateAggregator  # noqa: E402

VEHICLE_CLASSES = {"car", "truck", "motorcycle", "bus"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="Path to a video file (mp4/avi/etc)")
    parser.add_argument("--vehicle-model", default=str(PROJECT_ROOT / "ai_models" / "yolo" / "model.pt"),
                         help="YOLO model used for vehicle detection")
    parser.add_argument("--plate-model", default=None,
                         help="Optional dedicated plate-detector .pt. If omitted, a heuristic crop is used.")
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--ocr-every", type=int, default=3,
                         help="Run OCR every N frames per track (OCR is the slow step)")
    parser.add_argument("--show", action="store_true", help="Show a live preview window")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        sys.exit(f"Video not found: {video_path}")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        sys.exit(f"Could not open video: {video_path}")

    detector = YOLODetector(args.vehicle_model, confidence=args.confidence)
    tracker = CentroidTracker()
    recognizer = PlateRecognizer(plate_model_path=args.plate_model)
    aggregator = PlateAggregator()

    out_dir = PROJECT_ROOT / "runs" / "anpr_test"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{video_path.stem}_annotated.mp4"

    fps = capture.get(cv2.CAP_PROP_FPS) or 25
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))

    reported = set()
    frame_idx = 0

    print(f"Processing {video_path.name} ({width}x{height} @ {fps:.0f}fps)")
    print(f"Plate detector: {'dedicated model' if args.plate_model else 'heuristic crop (no model)'}")
    print("-" * 60)

    while args.max_frames is None or frame_idx < args.max_frames:
        ok, frame = capture.read()
        if not ok:
            break

        detections = [d for d in detector.detect(frame) if d["class"] in VEHICLE_CLASSES]
        tracks = tracker.update(detections)

        for track in tracks:
            track_id = track["track_id"]
            if frame_idx % args.ocr_every == 0:
                reading = recognizer.read_plate(frame, track["bbox"])
                aggregator.add(track_id, reading)

            best = aggregator.best(track_id)
            x1, y1, x2, y2 = map(int, track["bbox"])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (80, 210, 120), 2)
            label = f"{track['class']} #{track_id}"
            if best:
                label += f" [{best['text']}]"
            cv2.putText(frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (80, 210, 120), 2)

            if best and best["votes"] >= 3 and track_id not in reported:
                reported.add(track_id)
                print(f"  Track #{track_id}: plate {best['text']}  (confidence {best['confidence']:.2f}, {best['votes']} votes)")

        writer.write(frame)
        if args.show:
            cv2.imshow("ANPR test", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        frame_idx += 1

    capture.release()
    writer.release()
    if args.show:
        cv2.destroyAllWindows()

    print("-" * 60)
    print(f"Processed {frame_idx} frames. Annotated video saved to: {out_path}")
    print("\nFinal plate summary:")
    if not reported:
        print("  No plates confirmed. See troubleshooting notes below.")
    for track_id in sorted(reported):
        best = aggregator.best(track_id)
        print(f"  Track #{track_id}: {best['text']}  ({best['votes']} votes, conf {best['confidence']:.2f})")

    if not reported:
        print("""
Troubleshooting:
  - Camera too far / plates < ~100px wide -> crop tighter or use closer footage
  - No --plate-model given and vehicle is angled, not front/rear-on -> heuristic
    crop will miss the plate. Try footage where vehicles face the camera
    (toll booths, gates, barriers), or supply a dedicated plate detector.
  - Check runs/anpr_test/*_annotated.mp4 to see exactly what the model is
    detecting as the vehicle box before assuming OCR is the problem.
""")


if __name__ == "__main__":
    main()
