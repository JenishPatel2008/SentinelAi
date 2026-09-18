from threading import Lock

from ..api.websocket import manager


class AlarmService:
    """Backend alarm state with a replaceable provider boundary for future hardware."""

    def __init__(self):
        self._states = {}
        self._lock = Lock()

    def trigger_alarm(self, camera_id, alert_id, track_id, zone, reason):
        key = (camera_id, alert_id)
        with self._lock:
            if self._states.get(key, {}).get("status") == "ACTIVE":
                return self._states[key]
            state = {"alert_id": alert_id, "camera_id": camera_id, "track_id": track_id, "zone": zone, "status": "ACTIVE", "reason": reason}
            self._states[key] = state
        manager.broadcast_from_sync({"type": "intrusion_alarm", "data": {**state, "alarm_status": "ACTIVE"}})
        return state

    def set_status(self, alert_id, status):
        with self._lock:
            for state in self._states.values():
                if state["alert_id"] == alert_id:
                    state["status"] = status
                    return state.copy()
        return None

    def get_status(self, alert_id):
        with self._lock:
            for state in self._states.values():
                if state["alert_id"] == alert_id:
                    return state.copy()
        return None


alarm_service = AlarmService()
