"""
AI wording must describe only what the models output and must never present
an AI result as a diagnosis, a risk level, or an anatomical finding.
"""

import re
from pathlib import Path

import pytest

from shared import ai_labels
from shared.ai_labels import (
    AI_DISCLAIMER,
    ai_findings_narrative,
    ai_result_label,
    pneumonia_type_label,
)

ROOT = Path(__file__).resolve().parents[2]

OVERCLAIMING = re.compile(r"bilateral|consolidation|opacit|risk level|\bHIGH\b|\bLOW\b|diagnosed", re.I)


def all_wording():
    narratives = [
        ai_findings_narrative(finding, kind)
        for finding in ("positive", "negative")
        for kind in (None, "bacterial_pneumonia", "viral_pneumonia")
    ]
    labels = [label for label, _ in ai_labels.AI_RESULT_LABELS.values()]
    labels += [label for label, _ in ai_labels.PNEUMONIA_TYPE_LABELS.values()]
    return narratives + labels + [AI_DISCLAIMER, ai_labels.CONFIDENCE_HELP]


@pytest.mark.parametrize("text", all_wording())
def test_wording_does_not_overclaim(text):
    assert not OVERCLAIMING.search(text)


def test_binary_labels():
    assert ai_result_label("positive") == ("Pneumonia suspected", "red")
    assert ai_result_label(" Negative ") == ("No pneumonia detected", "green")
    assert ai_result_label(None) == ("No AI result", "slate")


def test_type_labels():
    assert pneumonia_type_label("viral_pneumonia")[0] == "Viral pattern"
    assert pneumonia_type_label(None, "negative")[0] == "Not applicable"
    assert pneumonia_type_label(None, "positive")[0] == "Type not classified"
    assert pneumonia_type_label(None)[0] == "—"


def test_narrative_for_missing_result_is_none():
    assert ai_findings_narrative(None) is None
    assert ai_findings_narrative("unexpected") is None


def test_negative_narrative_does_not_rule_out_disease():
    assert "does not rule out" in ai_findings_narrative("negative")


def test_disclaimer_says_not_a_diagnosis():
    assert "not a diagnosis" in AI_DISCLAIMER


def test_mobile_disclaimer_matches_web():
    mobile = (ROOT / "mobile_app/src/constants/ai.ts").read_text(encoding="utf-8")
    assert AI_DISCLAIMER in mobile


@pytest.mark.parametrize(
    "page",
    [
        "streamlit_app/pages/physician/review_patient.py",
        "streamlit_app/pages/system_administrator/manage_medical_records.py",
        "streamlit_app/pages/system_administrator/training_data_review.py",
    ],
)
def test_clinical_pages_do_not_show_risk_levels(page):
    """Regression: AI output used to be shown as 'Risk Level: HIGH/LOW' with
    invented findings such as 'Bilateral consolidation detected'."""
    source = (ROOT / page).read_text(encoding="utf-8")
    assert "Risk Level" not in source
    assert "Bilateral" not in source
    assert '("HIGH"' not in source
