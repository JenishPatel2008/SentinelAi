from collections import deque
from datetime import datetime
import json

from .face_detector import FaceDetector, crop_face
from .face_quality import assess_face_quality


class FaceIntelligence:
    """Enrich existing person tracks with face and stabilized identity context."""

    def __init__(self, detector: FaceDetector, encoder, enabled=False, recognition_threshold=0.363, confirmation_frames=3, sample_interval=5, identity_loss_frames=5, min_size=24, track_cleanup_seconds=180):
        self.detector = detector
        self.encoder = encoder
        self.enabled = bool(enabled)
        self.recognition_threshold = float(recognition_threshold)
        self.confirmation_frames = int(confirmation_frames)
        self.sample_interval = max(1, int(sample_interval))
        self.identity_loss_frames = int(identity_loss_frames)
        self.min_size = int(min_size)
        self.track_cleanup_seconds = int(track_cleanup_seconds)
        self.states = {}
        self.frame_number = 0

    def reset(self):
        self.states.clear()
        self.frame_number = 0

    def update(self, frame, tracks, subjects, timestamp=None):
        timestamp = timestamp or datetime.utcnow()
        self.frame_number += 1
        subjects_by_id = {int(subject["id"]): subject for subject in subjects if subject.get("enabled", True)}
        observations = []
        events = []
        current_ids = set()
        for track in tracks:
            if track.get("class") != "person":
                continue
            track_id = int(track["track_id"])
            current_ids.add(track_id)
            state = self.states.setdefault(track_id, self._new_state(timestamp))
            state["last_seen"] = timestamp
            sample = self.frame_number % self.sample_interval == 0 or state["face_status"] == "unknown"
            if sample:
                result = self._analyze_track(frame, track, subjects_by_id)
                self._apply_result(state, result, subjects_by_id)
                observations.append(self._observation(track, state, timestamp))
                events.extend(self._transition_events(track, state, result, timestamp))
            self._apply_track_context(track, state, subjects_by_id)
        self._cleanup(timestamp, current_ids)
        return tracks, observations, events

    def _analyze_track(self, frame, track, subjects):
        faces = self.detector.detect(frame, track.get("bbox"))
        if not faces:
            return {"face_status": "unavailable", "identity_status": "unverified", "recognition_status": "not_attempted", "reason": "Face unavailable or obstructed"}
        face = max(faces, key=lambda item: (item["face_bbox"][2] - item["face_bbox"][0]) * (item["face_bbox"][3] - item["face_bbox"][1]))
        quality = assess_face_quality(crop_face(frame, face["face_bbox"]), self.min_size)
        if not quality["usable"]:
            return {**face, "face_status": "obstructed", "identity_status": "unverified", "recognition_status": "unavailable", "reason": f"Recognition unavailable: {quality['reason']}", "quality": quality}
        if not self.enabled:
            return {**face, "face_status": "detected", "identity_status": "not_attempted", "recognition_status": "disabled", "reason": "Face recognition is disabled"}
        if not self.encoder or not self.encoder.available:
            return {**face, "face_status": "detected", "identity_status": "unverified", "recognition_status": "unavailable", "reason": "Recognition unavailable: face encoder model is not installed"}
        embedding = self.encoder.encode(frame, face)
        if embedding is None:
            return {**face, "face_status": "detected", "identity_status": "unverified", "recognition_status": "unavailable", "reason": "Recognition unavailable: face embedding could not be generated"}
        best_subject, best_similarity = None, None
        for subject in subjects.values():
            candidate = self.encoder.similarity(embedding, subject["embedding"])
            if candidate is not None and (best_similarity is None or candidate > best_similarity):
                best_subject, best_similarity = subject, candidate
        if best_subject is None or best_similarity < self.recognition_threshold:
            return {**face, "face_status": "detected", "identity_status": "unknown", "recognition_status": "unknown", "similarity": best_similarity, "reason": "No trusted subject passed the configured cosine-similarity threshold"}
        return {**face, "face_status": "detected", "identity_status": "candidate", "recognition_status": "recognized", "subject": best_subject, "similarity": best_similarity, "reason": "Trusted subject candidate observed"}

    def _apply_result(self, state, result, subjects):
        state.update({key: value for key, value in result.items() if key not in {"subject", "quality"}})
        state["quality"] = result.get("quality")
        if result.get("identity_status") == "candidate":
            candidate_id = int(result["subject"]["id"])
            state["candidate_history"].append(candidate_id)
            state["unknown_count"] = 0
            recent = list(state["candidate_history"])
            if len(recent) >= self.confirmation_frames and len(set(recent[-self.confirmation_frames:])) == 1:
                state["confirmed_subject_id"] = candidate_id
        elif result.get("identity_status") == "unknown":
            state["candidate_history"].append(None)
            state["unknown_count"] += 1
            if state["confirmed_subject_id"] is not None and state["unknown_count"] >= self.identity_loss_frames:
                state["confirmed_subject_id"] = None
        elif result.get("identity_status") in {"unverified", "not_attempted"}:
            state["unknown_count"] += 1

        confirmed_id = state["confirmed_subject_id"]
        if confirmed_id is not None and confirmed_id in subjects:
            state["identity_status"] = "trusted"
            state["recognition_status"] = "recognized"
            state["subject"] = subjects[confirmed_id]
        elif result.get("identity_status") == "candidate":
            state["identity_status"] = "unknown"
            state["recognition_status"] = "pending"
            state["subject"] = None
        elif result.get("identity_status") == "unknown":
            state["identity_status"] = "unknown"
            state["subject"] = None
        elif result.get("identity_status") in {"unverified", "not_attempted"}:
            state["identity_status"] = result["identity_status"]
            state["subject"] = None

    @staticmethod
    def _new_state(timestamp):
        return {
            "first_seen": timestamp, "last_seen": timestamp, "face_status": "unavailable",
            "identity_status": "unverified", "recognition_status": "not_attempted",
            "face_bbox": None, "face_confidence": None, "similarity": None, "reason": "Face not sampled yet",
            "quality": None, "candidate_history": deque(maxlen=30), "confirmed_subject_id": None,
            "subject": None, "unknown_count": 0,
        }

    @staticmethod
    def _apply_track_context(track, state, subjects):
        track.update({
            "face_detected": state["face_status"] == "detected",
            "face_status": state["face_status"],
            "face_bbox": state.get("face_bbox"),
            "face_confidence": state.get("face_confidence"),
            "face_similarity": state.get("similarity"),
            "recognition_status": state["recognition_status"],
            "identity_status": state["identity_status"],
            "identity_reason": state["reason"],
        })
        subject = state.get("subject")
        if subject:
            track.update({"subject_id": subject["id"], "subject_label": subject["label"], "subject_category": subject["category"], "watchlist_match": subject["category"].lower() == "watchlist"})
        else:
            track.update({"subject_id": None, "subject_label": None, "subject_category": None, "watchlist_match": False})

    @staticmethod
    def _observation(track, state, timestamp):
        return {
            "track_id": track["track_id"], "face_status": state["face_status"], "recognition_status": state["recognition_status"],
            "identity_status": state["identity_status"], "subject_id": state.get("confirmed_subject_id"),
            "face_confidence": state.get("face_confidence"), "similarity": state.get("similarity"),
            "face_bbox": state.get("face_bbox"), "timestamp": timestamp,
        }

    def _transition_events(self, track, state, result, timestamp):
        previous = state.get("last_event_state", {})
        current = {"face_status": state["face_status"], "identity_status": state["identity_status"], "subject_id": state.get("confirmed_subject_id")}
        state["last_event_state"] = current
        events = []
        if current["face_status"] == "detected" and previous.get("face_status") != "detected":
            events.append(self._event("FACE_DETECTED", track, state, timestamp, "Face detected on existing person track"))
        if current["face_status"] in {"obstructed", "unavailable"} and previous.get("face_status") != current["face_status"]:
            events.append(self._event("FACE_OBSTRUCTED", track, state, timestamp, state["reason"]))
        if current["identity_status"] == "unknown" and previous.get("identity_status") != "unknown":
            events.append(self._event("UNKNOWN_FACE", track, state, timestamp, state["reason"]))
        if current["subject_id"] is not None and current["subject_id"] != previous.get("subject_id"):
            subject = state.get("subject") or {}
            events.append(self._event("IDENTITY_RECOGNIZED", track, state, timestamp, "Trusted identity confirmed after multi-frame consensus"))
            events.append(self._event("TRUSTED_PERSON_DETECTED", track, state, timestamp, "Trusted person detected"))
            if subject.get("category", "").lower() == "watchlist":
                events.append(self._event("WATCHLIST_MATCH", track, state, timestamp, "Configured watchlist category matched"))
        return events

    @staticmethod
    def _event(event_type, track, state, timestamp, reason):
        subject = state.get("subject") or {}
        return {
            "event_type": event_type, "track_id": track["track_id"], "object_type": "person", "timestamp": timestamp,
            "identity_status": state["identity_status"], "subject_id": state.get("confirmed_subject_id"),
            "subject_label": subject.get("label"), "subject_category": subject.get("category"),
            "face_status": state["face_status"], "face_confidence": state.get("face_confidence"),
            "face_similarity": state.get("similarity"), "face_bbox": state.get("face_bbox"), "reason": reason,
            "zone": track.get("zone_matches", [{}])[0].get("name") if track.get("zone_matches") else None,
            "zone_type": track.get("zone_matches", [{}])[0].get("zone_type") if track.get("zone_matches") else None,
            "scene_condition": track.get("scene_condition"), "night_confidence": track.get("night_confidence"),
        }

    def _cleanup(self, timestamp, current_ids):
        for track_id, state in list(self.states.items()):
            if track_id not in current_ids and (timestamp - state["last_seen"]).total_seconds() > self.track_cleanup_seconds:
                self.states.pop(track_id, None)
