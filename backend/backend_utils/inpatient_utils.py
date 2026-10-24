# backend/backend_utils/inpatient_utils.py

def calculate_discharge_readiness(vitals_history):
    """
    Evaluates the latest vitals and the trend.
    vitals_history: list of dicts (newest first)
    """
    if not vitals_history:
        return {
            "score": 0, 
            "status": "No Data", 
            "tone": "slate", 
            "alerts": ["No vitals recorded."], 
            "checklist": {}
        }

    latest = vitals_history[0]
    spo2 = latest.get("spo2")
    temp = latest.get("temperature")
    rr = latest.get("respiratory_rate")

    score = 0
    alerts = []
    checklist = {"afebrile": False, "spo2_stable": False, "rr_normal": False}

    # 1. SpO2 (Target >= 92%)
    if spo2 is not None:
        if spo2 >= 92:
            score += 1
            checklist["spo2_stable"] = True
        else:
            alerts.append(f"CRITICAL: SpO2 is {spo2}%. Hypoxia detected.")
    
    # 2. Temperature (Target < 37.5)
    if temp is not None:
        if temp < 37.5:
            score += 1
            checklist["afebrile"] = True
        else:
            alerts.append(f"WARNING: Fever present ({temp}°C).")
    
    # 3. Respiratory Rate (Target < 24)
    if rr is not None:
        if rr < 24:
            score += 1
            checklist["rr_normal"] = True
        else:
            alerts.append(f"WARNING: Tachypnea ({rr}/min).")

    # 4. Trend check
    if len(vitals_history) >= 2:
        prev = vitals_history[1]
        if temp and prev.get("temperature") and temp > prev.get("temperature"):
            alerts.append("CRITICAL: Temperature is trending upward despite treatment.")
        if spo2 and prev.get("spo2") and spo2 < prev.get("spo2"):
            alerts.append("CRITICAL: Oxygen saturation is dropping despite treatment.")

    if score == 3 and not alerts:
        status, tone = "Ready for Discharge", "green"
    elif score >= 2:
        status, tone = "Improving - Monitor closely", "amber"
    else:
        status, tone = "Not Ready - High Risk", "red"

    return {
        "score": score, 
        "status": status, 
        "tone": tone, 
        "alerts": alerts, 
        "checklist": checklist
    }