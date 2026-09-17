def calculate_threat(objects, intrusion_duration=0, config=None, plate_matches=None, night_movements=None):
    config = config or {"person": 45, "car": 60, "truck": 65, "motorcycle": 60, "bus": 65, "bicycle": 45, "persistent": 20, "multiple": 10, "duration": 2}
    plate_matches = plate_matches or []
    night_movements = night_movements or []
    intruders = [item for item in objects if item.get("intrusion")]
    if not intruders:
        if night_movements:
            item = night_movements[0]
            condition = item.get("scene_condition", "LOW_LIGHT").replace("_", " ").lower()
            object_name = item.get("class", "object").title()
            return {"score": 20, "severity": "LOW", "reason": f"Night-time movement: {object_name} moving during {condition} conditions", "watchlist_matches": []}
        return {"score": 0, "severity": "LOW", "reason": "No restricted-zone intrusion"}
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
    score = min(100, score)
    severity = "CRITICAL" if score >= 81 else "HIGH" if score >= 61 else "MEDIUM" if score >= 31 else "LOW"
    object_name = intruders[0].get("class", "object")
    reason = f"{object_name.title()} entered restricted zone"
    if plate_matches:
        reason += f"; Watchlist plate {plate_matches[0].get('plate_number', 'UNKNOWN')} matched"
    if night_movements:
        condition = night_movements[0].get("scene_condition", "LOW_LIGHT").replace("_", " ").lower()
        reason += f"; Night-time movement during {condition} conditions"
    return {"score": score, "severity": severity, "reason": reason, "watchlist_matches": plate_matches}
