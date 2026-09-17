from collections import defaultdict, deque
from datetime import datetime
from math import hypot


class BehaviorEngine:
    """Rule-based temporal behavior analysis for the existing tracked objects."""

    def __init__(self, loitering_time_seconds=45, loitering_movement_threshold=80, restricted_zone_dwell_seconds=10, fence_crossing_count_threshold=3, fence_crossing_window_seconds=120, stationary_time_seconds=60, stationary_movement_threshold=12, proximity_threshold=100, proximity_time_seconds=20, track_cleanup_seconds=180):
        self.loitering_time_seconds = loitering_time_seconds
        self.loitering_movement_threshold = loitering_movement_threshold
        self.restricted_zone_dwell_seconds = restricted_zone_dwell_seconds
        self.fence_crossing_count_threshold = fence_crossing_count_threshold
        self.fence_crossing_window_seconds = fence_crossing_window_seconds
        self.stationary_time_seconds = stationary_time_seconds
        self.stationary_movement_threshold = stationary_movement_threshold
        self.proximity_threshold = proximity_threshold
        self.proximity_time_seconds = proximity_time_seconds
        self.track_cleanup_seconds = track_cleanup_seconds
        self.states = {}
        self.proximity_states = {}

    def reset(self):
        self.states.clear()
        self.proximity_states.clear()

    def update(self, tracks, scene=None, timestamp=None):
        timestamp = timestamp or datetime.utcnow()
        scene = scene or {"scene_condition": "UNKNOWN", "night_confidence": 0.0}
        observations = []
        current_ids = set()
        for track in tracks:
            track_id = track["track_id"]
            current_ids.add(track_id)
            state = self.states.setdefault(track_id, self._new_state(timestamp, track))
            previous_zones = state["zones"]
            zone_matches = [
                zone for zone in track.get("zone_matches", [])
                if zone.get("zone_type") in {"restricted", "high_security", "vehicle_restricted"}
            ]
            zones = {zone["name"] for zone in zone_matches}
            entered = bool(zones - previous_zones)
            exited = bool(previous_zones - zones)
            if entered:
                state["zone_started"] = timestamp
                state["crossings"].append(timestamp)
            if exited:
                state["zone_started"] = None
                state["crossings"].append(timestamp)
            state["zones"] = zones
            state["last_seen"] = timestamp
            movement_distance = float(track.get("movement_distance", 0) or 0)
            state["path_distance"] += movement_distance
            state["low_movement_seconds"] += self._elapsed(state["last_movement_sample"], timestamp) if movement_distance <= self.stationary_movement_threshold else 0
            state["last_movement_sample"] = timestamp
            if track.get("moving") and movement_distance > self.stationary_movement_threshold:
                state["stationary_started"] = None
            elif state["stationary_started"] is None:
                state["stationary_started"] = timestamp
            state["behavior_flags"] = set()
            dwell = self._elapsed(state["zone_started"], timestamp)
            stationary = self._elapsed(state["stationary_started"], timestamp)
            recent_crossings = self._recent_crossings(state["crossings"], timestamp)
            if zones and dwell >= self.restricted_zone_dwell_seconds:
                state["behavior_flags"].add("EXTENDED_RESTRICTED_PRESENCE")
            if zones and dwell >= self.loitering_time_seconds and state["path_distance"] <= self.loitering_movement_threshold:
                state["behavior_flags"].add("LOITERING")
            if zones and stationary >= self.stationary_time_seconds:
                state["behavior_flags"].add("PROLONGED_STATIONARY")
            if len(recent_crossings) >= self.fence_crossing_count_threshold:
                state["behavior_flags"].add("REPEATED_FENCE_CROSSING")
            track["dwell_seconds"] = round(dwell, 2)
            track["stationary_seconds"] = round(stationary, 2)
            track["fence_crossings"] = len(recent_crossings)
            track["behavior_types"] = sorted(state["behavior_flags"])
            track["behavior_state"] = self._state_name(state["behavior_flags"])
            track["behavior_reason"] = self._reason(track, scene, dwell, stationary, len(recent_crossings))
            for behavior_type in sorted(state["behavior_flags"]):
                if behavior_type not in state["emitted"]:
                    state["emitted"].add(behavior_type)
                    observations.append(self._observation(track, behavior_type, scene, dwell, stationary, len(recent_crossings)))

        self._add_proximity_context(tracks, timestamp, observations, scene)
        self._cleanup(timestamp, current_ids)
        return tracks, observations

    def _new_state(self, timestamp, track):
        return {
            "first_seen": timestamp,
            "last_seen": timestamp,
            "zones": set(),
            "zone_started": None,
            "stationary_started": timestamp,
            "last_movement_sample": timestamp,
            "path_distance": 0.0,
            "low_movement_seconds": 0.0,
            "crossings": deque(maxlen=50),
            "emitted": set(),
            "behavior_flags": set(),
        }

    @staticmethod
    def _elapsed(start, end):
        return max(0.0, (end - start).total_seconds()) if start else 0.0

    def _recent_crossings(self, crossings, timestamp):
        return [value for value in crossings if self._elapsed(value, timestamp) <= self.fence_crossing_window_seconds]

    @staticmethod
    def _state_name(flags):
        if len(flags) >= 2:
            return "HIGH_RISK"
        if "REPEATED_FENCE_CROSSING" in flags or "LOITERING" in flags:
            return "SUSPICIOUS"
        if flags:
            return "WATCH"
        return "NORMAL"

    @staticmethod
    def _reason(track, scene, dwell, stationary, crossings):
        reasons = []
        if dwell:
            reasons.append(f"Present in zone for {dwell:.0f} seconds")
        if stationary:
            reasons.append(f"Movement below threshold for {stationary:.0f} seconds")
        if crossings:
            reasons.append(f"{crossings} fence interactions in the configured window")
        if scene.get("scene_condition") in {"NIGHT", "LOW_LIGHT"}:
            reasons.append(f"{scene['scene_condition'].replace('_', ' ').title()} conditions")
        if track.get("vehicle_class"):
            reasons.append(f"Vehicle class: {track['vehicle_class']}")
        return "; ".join(reasons) or "No suspicious behavior signal"

    @staticmethod
    def _observation(track, behavior_type, scene, dwell, stationary, crossings):
        return {
            "behavior_type": behavior_type,
            "behavior_state": track["behavior_state"],
            "behavior_reason": track["behavior_reason"],
            "track_id": track["track_id"],
            "object_type": track["class"],
            "vehicle_class": track.get("vehicle_class"),
            "vehicle_class_confidence": track.get("vehicle_class_confidence"),
            "zone": track.get("zone_matches", [{}])[0].get("name") if track.get("zone_matches") else None,
            "zone_type": track.get("zone_matches", [{}])[0].get("zone_type") if track.get("zone_matches") else None,
            "duration_seconds": round(max(dwell, stationary), 2),
            "fence_crossings": crossings,
            "scene_condition": scene.get("scene_condition"),
            "night_confidence": scene.get("night_confidence", 0.0),
        }

    def _add_proximity_context(self, tracks, timestamp, observations, scene):
        persons = [track for track in tracks if track.get("class") == "person"]
        vehicles = [
            track for track in tracks
            if track.get("category") == "vehicle"
            or track.get("class") in {"bicycle", "car", "motorcycle", "bus", "truck"}
        ]
        active_pairs = set()
        for person in persons:
            for vehicle in vehicles:
                distance = hypot(person["center"][0] - vehicle["center"][0], person["center"][1] - vehicle["center"][1])
                key = (person["track_id"], vehicle["track_id"])
                if distance > self.proximity_threshold:
                    continue
                active_pairs.add(key)
                started = self.proximity_states.setdefault(key, timestamp)
                duration = self._elapsed(started, timestamp)
                person["near_vehicle_track_id"] = vehicle["track_id"]
                person["near_vehicle_seconds"] = round(duration, 2)
                if duration >= self.proximity_time_seconds and not self.states[person["track_id"]]["emitted"].__contains__("PERSON_VEHICLE_PROXIMITY"):
                    self.states[person["track_id"]]["emitted"].add("PERSON_VEHICLE_PROXIMITY")
                    person["behavior_types"] = sorted(set(person.get("behavior_types", [])) | {"PERSON_VEHICLE_PROXIMITY"})
                    person["behavior_state"] = "SUSPICIOUS"
                    observations.append({
                        "behavior_type": "PERSON_VEHICLE_PROXIMITY",
                        "behavior_state": "SUSPICIOUS",
                        "behavior_reason": f"Person remained near vehicle track #{vehicle['track_id']} for {duration:.0f} seconds",
                        "track_id": person["track_id"], "object_type": "person", "vehicle_class": None,
                        "vehicle_class_confidence": None, "zone": person.get("zone_matches", [{}])[0].get("name") if person.get("zone_matches") else None,
                        "zone_type": person.get("zone_matches", [{}])[0].get("zone_type") if person.get("zone_matches") else None,
                        "duration_seconds": round(duration, 2), "fence_crossings": person.get("fence_crossings", 0),
                        "scene_condition": scene.get("scene_condition"), "night_confidence": scene.get("night_confidence", 0.0),
                        "near_vehicle_track_id": vehicle["track_id"],
                    })
        for key in set(self.proximity_states) - active_pairs:
            self.proximity_states.pop(key, None)

    def _cleanup(self, timestamp, current_ids):
        for track_id, state in list(self.states.items()):
            if track_id not in current_ids and self._elapsed(state["last_seen"], timestamp) > self.track_cleanup_seconds:
                self.states.pop(track_id, None)
