BEHAVIOR_SCORES = {
    "LOITERING": 20,
    "EXTENDED_RESTRICTED_PRESENCE": 15,
    "REPEATED_FENCE_CROSSING": 25,
    "PROLONGED_STATIONARY": 15,
    "PERSON_VEHICLE_PROXIMITY": 15,
}


def calculate_threat(objects, intrusion_duration=0, config=None, plate_matches=None, night_movements=None, behaviors=None, identity_context=None):
    config = config or {"person": 45, "car": 60, "truck": 65, "motorcycle": 60, "bus": 65, "bicycle": 45, "persistent": 20, "multiple": 10, "duration": 2}
    plate_matches = plate_matches or []
    night_movements = night_movements or []
    behaviors = behaviors or []
    identity_context = identity_context or []
    behavior_types = list(dict.fromkeys(
        item.get("behavior_type") for item in behaviors if item.get("behavior_type")
    ))
    behavior_score = max((BEHAVIOR_SCORES.get(item, 0) for item in behavior_types), default=0)
    behavior_reasons = [item.get("behavior_reason") for item in behaviors if item.get("behavior_reason")]
    intruders = [item for item in objects if item.get("intrusion")]
    protected_unverified = [
        item for item in identity_context
        if item.get("intrusion") and item.get("protected_zone")
        and item.get("identity_status") in {"unknown", "unverified", "not_attempted"}
    ]
    identity_watchlist = [item for item in identity_context if item.get("watchlist_match") and item.get("intrusion")]
    if not intruders:
        if behavior_types:
            score = behavior_score
            severity = "HIGH" if score >= 61 else "MEDIUM" if score >= 31 else "LOW"
            return {
                "score": score,
                "severity": severity,
                "reason": "; ".join(behavior_reasons) or f"Suspicious activity: {behavior_types[0].replace('_', ' ').title()}",
                "watchlist_matches": [],
                "behaviors": behavior_types,
                "behavior_reasons": behavior_reasons,
                "identity_context": [],
            }
        if night_movements:
            item = night_movements[0]
            condition = item.get("scene_condition", "LOW_LIGHT").replace("_", " ").lower()
            object_name = item.get("class", "object").title()
            return {"score": 20, "severity": "LOW", "reason": f"Night-time movement: {object_name} moving during {condition} conditions", "watchlist_matches": [], "behaviors": [], "behavior_reasons": [], "identity_context": []}
        return {"score": 0, "severity": "LOW", "reason": "No restricted-zone intrusion", "behaviors": [], "behavior_reasons": [], "identity_context": []}
    score = max(config.get(item.get("class"), 0) for item in intruders)
    if any(item.get("hits", 0) >= 5 for item in intruders):
        score += config["persistent"]
    if len(intruders) > 1:
        score += config["multiple"]
    score += min(20, int(intrusion_duration * config["duration"]))
    if plate_matches:
        score += min(20, max(int(item.get("priority_score", 20)) for item in plate_matches))
    if night_movements:
        score += 20
    if behavior_score:
        score += behavior_score
    if protected_unverified:
        score += 20
    if identity_watchlist:
        score += 20
    score = min(100, score)
    severity = "CRITICAL" if score >= 81 else "HIGH" if score >= 61 else "MEDIUM" if score >= 31 else "LOW"
    object_name = intruders[0].get("class", "object")
    reason = f"{object_name.title()} entered restricted zone"
    if plate_matches:
        reason += f"; Watchlist plate {plate_matches[0].get('plate_number', 'UNKNOWN')} matched"
    if night_movements:
        condition = night_movements[0].get("scene_condition", "LOW_LIGHT").replace("_", " ").lower()
        reason += f"; Night-time movement during {condition} conditions"
    if behavior_reasons:
        reason += "; " + "; ".join(behavior_reasons)
    if protected_unverified:
        reason += "; Unverified person inside protected zone"
    if identity_watchlist:
        reason += "; Configured face watchlist category matched"
    return {"score": score, "severity": severity, "reason": reason, "watchlist_matches": plate_matches, "behaviors": behavior_types, "behavior_reasons": behavior_reasons, "identity_context": [{"track_id": item.get("track_id"), "identity_status": item.get("identity_status"), "subject_id": item.get("subject_id")} for item in identity_context]}
