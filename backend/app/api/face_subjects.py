from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..ai.face_detector import FaceDetector
from ..ai.face_recognition import SFaceEncoder, embedding_bytes
from ..core.config import get_runtime_settings
from ..database.database import PROJECT_ROOT, get_db
from ..database.models import FaceEmbedding, FaceObservation, FaceSubject
from ..database.schemas import FaceObservationResponse, FaceSubjectResponse, FaceSubjectUpdate
from ..services.face_service import build_subject_embedding, create_subject, decode_image


router = APIRouter(prefix="/face-subjects", tags=["Trusted Persons"])


def _components():
    settings = get_runtime_settings()
    detector_path = PROJECT_ROOT / settings["face_detection_model_path"]
    encoder_path = PROJECT_ROOT / settings["face_recognition_model_path"]
    return (
        FaceDetector(detector_path, settings["face_min_size"], settings["face_detection_confidence_threshold"]),
        SFaceEncoder(encoder_path),
        settings,
    )


@router.get("", response_model=list[FaceSubjectResponse])
def list_subjects(db: Session = Depends(get_db)):
    return db.query(FaceSubject).order_by(FaceSubject.created_at.desc()).all()


@router.post("", response_model=FaceSubjectResponse, status_code=201)
async def add_subject(label: str = Form(...), category: str = Form("authorized"), enabled: bool = Form(True), image: UploadFile = File(...), db: Session = Depends(get_db)):
    if not label.strip():
        raise HTTPException(422, "A subject label is required")
    try:
        content = await image.read()
        frame = decode_image(content)
        detector, encoder, settings = _components()
        return create_subject(db, label, category, enabled, frame, detector, encoder, settings["face_min_size"])
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    finally:
        await image.close()


@router.get("/observations/list", response_model=list[FaceObservationResponse])
def list_observations(db: Session = Depends(get_db)):
    return db.query(FaceObservation).order_by(FaceObservation.timestamp.desc()).limit(500).all()


@router.get("/{subject_id}", response_model=FaceSubjectResponse)
def get_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.get(FaceSubject, subject_id)
    if subject is None:
        raise HTTPException(404, "Trusted person not found")
    return subject


@router.patch("/{subject_id}", response_model=FaceSubjectResponse)
def update_subject(subject_id: int, data: FaceSubjectUpdate, db: Session = Depends(get_db)):
    subject = db.get(FaceSubject, subject_id)
    if subject is None:
        raise HTTPException(404, "Trusted person not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(subject, key, value.lower() if key == "category" else value)
    db.commit()
    db.refresh(subject)
    return subject


@router.post("/{subject_id}/reference", response_model=FaceSubjectResponse)
async def replace_reference(subject_id: int, image: UploadFile = File(...), db: Session = Depends(get_db)):
    subject = db.get(FaceSubject, subject_id)
    if subject is None:
        raise HTTPException(404, "Trusted person not found")
    try:
        frame = decode_image(await image.read())
        detector, encoder, settings = _components()
        embedding, _, _ = build_subject_embedding(frame, detector, encoder, settings["face_min_size"])
        stored = db.query(FaceEmbedding).filter(FaceEmbedding.subject_id == subject_id).first()
        if stored is None:
            stored = FaceEmbedding(subject_id=subject_id, embedding=b"", dimension=0, metric=encoder.metric)
            db.add(stored)
        stored.embedding = embedding_bytes(embedding)
        stored.dimension = int(embedding.size)
        stored.metric = encoder.metric
        db.commit()
        db.refresh(subject)
        return subject
    except (ValueError, RuntimeError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    finally:
        await image.close()


@router.delete("/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    subject = db.get(FaceSubject, subject_id)
    if subject is None:
        raise HTTPException(404, "Trusted person not found")
    db.query(FaceEmbedding).filter(FaceEmbedding.subject_id == subject_id).delete()
    db.delete(subject)
    db.commit()
    return {"subject_id": subject_id, "status": "deleted"}

