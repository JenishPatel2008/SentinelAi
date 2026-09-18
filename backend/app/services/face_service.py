from datetime import datetime

import cv2
import numpy as np

from ..ai.face_detector import FaceDetector, crop_face
from ..ai.face_quality import assess_face_quality
from ..ai.face_recognition import SFaceEncoder, embedding_bytes
from ..database.models import FaceEmbedding, FaceSubject


def build_subject_embedding(image, detector: FaceDetector, encoder: SFaceEncoder, min_size=24):
    faces = detector.detect(image)
    if len(faces) != 1:
        if not faces:
            raise ValueError("No usable face detected. Please provide a clearer reference image.")
        raise ValueError("Reference image must contain exactly one face.")
    face = faces[0]
    quality = assess_face_quality(crop_face(image, face["face_bbox"]), min_size)
    if not quality["usable"]:
        raise ValueError(f"No usable face detected: {quality['reason']}.")
    if not encoder.available:
        raise RuntimeError("Face encoder model is not installed. Add the configured SFace model before registering a subject.")
    embedding = encoder.encode(image, face)
    if embedding is None or embedding.size == 0:
        raise ValueError("Unable to generate a face embedding from this image.")
    return embedding, face, quality


def create_subject(db, label, category, enabled, image, detector, encoder, min_size):
    embedding, _, _ = build_subject_embedding(image, detector, encoder, min_size)
    now = datetime.utcnow()
    subject = FaceSubject(label=label.strip(), category=category.strip().lower(), enabled=enabled, created_at=now, updated_at=now)
    db.add(subject)
    db.flush()
    db.add(FaceEmbedding(subject_id=subject.id, embedding=embedding_bytes(embedding), dimension=int(embedding.size), metric=encoder.metric, created_at=now, updated_at=now))
    db.commit()
    db.refresh(subject)
    return subject


def decode_image(content):
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ValueError("The uploaded reference image could not be decoded.")
    return image
