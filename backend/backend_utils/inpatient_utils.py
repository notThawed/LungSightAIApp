# backend/backend_utils/inpatient_utils.py

def calculate_discharge_readiness(vitals_history):
    """
    Evaluates the latest vitals and trend.
    Returns a strict score (0-3) for UI enforcement.
    """
    if not vitals_history:
        return {
            "score": 0, 
            "status": "No Data", 
            "tone": "slate", 
            "alerts": ["No vitals recorded."], 
            "checklist": {},
            "can_discharge": False
        }

    latest = vitals_history[0]
    spo2 = latest.get("spo2")
    temp = latest.get("temperature")
    rr = latest.get("respiratory_rate")
    oxygen = latest.get("oxygen_support")

    score = 0
    alerts = []
    checklist = {"afebrile": False, "spo2_stable": False, "rr_normal": False}

    # 1. SpO2 (Target >= 92%)
    if spo2 is not None:
        if spo2 >= 92:
            score += 1
            checklist["spo2_stable"] = True
        else:
            alerts.append(f"Clinical flag: SpO2 is {spo2}%. Hypoxia detected.")
    else:
        alerts.append("SpO2 missing from latest round.")
    
    # 2. Temperature (Target < 37.5)
    if temp is not None:
        if temp < 37.5:
            score += 1
            checklist["afebrile"] = True
        else:
            alerts.append(f"Clinical flag: Fever present ({temp}°C).")
    else:
        alerts.append("Temperature missing from latest round.")
    
    # 3. Respiratory Rate (Target < 24)
    if rr is not None:
        if rr < 24:
            score += 1
            checklist["rr_normal"] = True
        else:
            alerts.append(f"Clinical flag: Tachypnea ({rr}/min).")
    else:
        alerts.append("Respiratory rate missing from latest round.")

    # 4. Oxygen Support (Review flag only)
    if not oxygen or oxygen == "Unknown":
        alerts.append("Oxygen support status not documented.")
    elif oxygen == "Supplemental oxygen" and spo2 and spo2 < 95:
        alerts.append("Patient is on supplemental oxygen and SpO2 is still below 95%.")

    # 5. Trend check
    if len(vitals_history) >= 2:
        prev = vitals_history[1]
        if temp and prev.get("temperature") and temp > prev.get("temperature"):
            alerts.append("Clinical flag: Temperature is rising.")
        if spo2 and prev.get("spo2") and spo2 < prev.get("spo2"):
            alerts.append("Clinical flag: SpO2 is dropping.")

    # Enforce strict threshold: 3/3 required to unlock discharge
    can_discharge = (score == 3)
    
    if can_discharge:
        status, tone = "Cleared for Discharge", "green"
    elif score >= 2:
        status, tone = "Improving - Monitor", "amber"
    else:
        status, tone = "Not Ready - High Risk", "red"

    return {
        "score": score, 
        "status": status, 
        "tone": tone, 
        "alerts": alerts, 
        "checklist": checklist,
        "can_discharge": can_discharge
    }