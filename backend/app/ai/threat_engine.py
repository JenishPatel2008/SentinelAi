def calculate_threat(objects, intrusion_duration=0, config=None):
    config = config or {"person": 45, "car": 60, "truck": 65, "motorcycle": 60, "bus": 65, "bicycle": 45, "persistent": 20, "multiple": 10, "duration": 2}
    intruders = [item for item in objects if item.get("intrusion")]
    if not intruders:
        return {"score": 0, "severity": "LOW", "reason": "No restricted-zone intrusion"}
    score = max(config.get(item.get("class"), 0) for item in intruders)
    if any(item.get("hits", 0) >= 5 for item in intruders):
        score += config["persistent"]
    if len(intruders) > 1:
        score += config["multiple"]
    score += min(20, int(intrusion_duration * config["duration"]))
    score = min(100, score)
    severity = "CRITICAL" if score >= 81 else "HIGH" if score >= 61 else "MEDIUM" if score >= 31 else "LOW"
    object_name = intruders[0].get("class", "object")
    return {"score": score, "severity": severity, "reason": f"{object_name.title()} entered restricted zone"}
