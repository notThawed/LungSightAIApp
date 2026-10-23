"""
How LungSightAI describes AI output to people.

The models only produce:
  * a binary chest X-ray classification ("positive" / "negative" for
    pneumonia) with a softmax probability, and
  * for positive images, a type classification ("bacterial_pneumonia" /
    "viral_pneumonia") with its own probability.

Wording here must never claim more than that (no locations, no severity,
no "risk level") and must keep AI output distinct from the clinician's
final diagnosis. The mobile app uses the same wording in
mobile_app/src/constants/ai.ts.
"""

AI_DISCLAIMER = (
    "AI decision support only — not a diagnosis. "
    "A qualified clinician must review the image and confirm the result."
)

CONFIDENCE_HELP = (
    "Model confidence is the probability the model assigned to its own "
    "prediction. It is not the probability that the patient has pneumonia."
)

AI_RESULT_LABELS = {
    "positive": ("Pneumonia suspected", "red"),
    "negative": ("No pneumonia detected", "green"),
}

PNEUMONIA_TYPE_LABELS = {
    "bacterial_pneumonia": ("Bacterial pattern", "red"),
    "viral_pneumonia": ("Viral pattern", "amber"),
}


def normalize_finding(ai_findings):
    return str(ai_findings or "").strip().lower()


def ai_result_label(ai_findings):
    """
    Return (label, tone) for the binary AI result.
    tone is one of the pill tones: red, green, slate.
    """
    if not ai_findings:
        return ("No AI result", "slate")

    return AI_RESULT_LABELS.get(
        normalize_finding(ai_findings),
        (str(ai_findings).title(), "slate"),
    )


def pneumonia_type_label(pneumonia_type, ai_findings=None):
    """Return (label, tone) for the AI pneumonia-type classification."""
    if pneumonia_type in PNEUMONIA_TYPE_LABELS:
        return PNEUMONIA_TYPE_LABELS[pneumonia_type]

    finding = normalize_finding(ai_findings)

    if finding == "negative":
        return ("Not applicable", "slate")

    if finding == "positive":
        return ("Type not classified", "amber")

    return ("—", "slate")


def ai_findings_narrative(ai_findings, pneumonia_type=None):
    """
    A plain-language sentence describing what the model actually output.
    Returns None when there is no AI result.
    """
    finding = normalize_finding(ai_findings)

    if finding == "positive":
        type_text = {
            "bacterial_pneumonia": " The type classifier favoured a <b>bacterial</b> pattern.",
            "viral_pneumonia": " The type classifier favoured a <b>viral</b> pattern.",
        }.get(pneumonia_type, "")

        return (
            "The AI model classified this chest X-ray as "
            "<b>consistent with pneumonia</b>." + type_text +
            " Correlate with the clinical picture before diagnosis."
        )

    if finding == "negative":
        return (
            "The AI model did <b>not</b> classify this chest X-ray as "
            "consistent with pneumonia. A negative AI result does not "
            "rule out disease; continue standard clinical evaluation."
        )

    return None
