"""
Golden-fixture tests for backend/reports/calculations.py and periods.py.

Every expected number below was computed by hand from the fixture.
"""

import dataclasses
from datetime import date, datetime, timezone

import pytest

from backend.reports import calculations as calc
from backend.reports.calculations import ReportInputs, compute_hospital_report
from backend.reports.periods import (
    REPORT_TZ,
    custom_period,
    monthly_period,
    parse_timestamp,
    weekly_period,
)


HOSP = "aaaaaaaa-0000-0000-0000-000000000001"
OTHER = "bbbbbbbb-0000-0000-0000-000000000002"
GENERATED = datetime(2026, 10, 8, 2, 0, tzinfo=timezone.utc)

# Period: Oct 1-7, 2026 Manila == [2026-09-30T16:00Z, 2026-10-07T16:00Z)
PERIOD = custom_period(date(2026, 10, 1), date(2026, 10, 7))


def exam(exam_id, created, status, *, hospital=HOSP, exam_type="General Consult",
         follow_up=None, disposition=None, severity=None):
    return {
        "examination_id": exam_id,
        "created_at": created,
        "examination_date": created[:10],
        "status": status,
        "examination_type": exam_type,
        "follow_up_sequence": follow_up,
        "disposition": disposition,
        "severity_status": severity,
        "patients": {"hospital_id": hospital, "patient_code": f"PAT-{exam_id}"},
    }


def golden_inputs():
    exams = [
        # E1: reviewed AI-flagged positive (bacterial); exactly at period start
        exam("E1", "2026-09-30T16:00:00+00:00", "Admitted", disposition="Admission", severity="High Risk"),
        # E2: retried upload (first image has no AI), awaiting review
        exam("E2", "2026-10-01T23:00:00+00:00", "X-Ray Ready"),
        # E3: re-analysed image (two AI results, latest inconclusive), reviewed without findings
        exam("E3", "2026-10-02T23:00:00+00:00", "Completed", disposition="Treated and Sent Home"),
        # E4: follow-up, awaiting analysis (request, no image)
        exam("E4", "2026-10-03T23:00:00+00:00", "Awaiting X-Ray", follow_up=1),
        # E5: no X-ray requested
        exam("E5", "2026-10-04T10:00:00+00:00", "Pending"),
        # E6: cancelled although it has an AI result
        exam("E6", "2026-10-05T01:00:00+00:00", "Cancelled"),
        # E7: inpatient ward round (excluded)
        exam("E7", "2026-10-05T02:00:00+00:00", "Completed", exam_type="Inpatient Round"),
        # E8: another hospital (excluded)
        exam("E8", "2026-10-05T03:00:00+00:00", "Pending", hospital=OTHER),
        # E9: exactly at period end (excluded, end is exclusive)
        exam("E9", "2026-10-07T16:00:00+00:00", "Pending"),
        # E10: last second of the period (included)
        exam("E10", "2026-10-07T15:59:59+00:00", "Pending"),
        # E11: older request reviewed, newer request pending -> current = newer, awaiting analysis
        exam("E11", "2026-10-03T23:30:00+00:00", "Awaiting X-Ray"),
    ]
    exams.append(dict(exams[0]))  # join fan-out duplicate of E1

    requests = [
        {"request_id": "R1", "examination_id": "E1", "status": "Completed", "requested_at": "2026-10-01T01:00:00+00:00"},
        {"request_id": "R2", "examination_id": "E2", "status": "Completed", "requested_at": "2026-10-02T00:00:00+00:00"},
        {"request_id": "R3", "examination_id": "E3", "status": "Completed", "requested_at": "2026-10-03T00:00:00+00:00"},
        {"request_id": "R4", "examination_id": "E4", "status": "Pending", "requested_at": "2026-10-04T00:00:00+00:00"},
        {"request_id": "R6", "examination_id": "E6", "status": "Completed", "requested_at": "2026-10-05T02:00:00+00:00"},
        {"request_id": "R11a", "examination_id": "E11", "status": "Completed", "requested_at": "2026-10-04T00:00:00+00:00"},
        {"request_id": "R11b", "examination_id": "E11", "status": "Pending", "requested_at": "2026-10-05T00:00:00+00:00"},
    ]
    images = [
        {"image_id": "I1", "request_id": "R1", "uploaded_at": "2026-10-01T02:00:00+00:00"},
        {"image_id": "I2a", "request_id": "R2", "uploaded_at": "2026-10-02T00:30:00+00:00"},
        {"image_id": "I2b", "request_id": "R2", "uploaded_at": "2026-10-02T00:45:00+00:00"},
        {"image_id": "I3", "request_id": "R3", "uploaded_at": "2026-10-03T00:05:00+00:00"},
        {"image_id": "I6", "request_id": "R6", "uploaded_at": "2026-10-05T02:10:00+00:00"},
        {"image_id": "I11", "request_id": "R11a", "uploaded_at": "2026-10-04T00:10:00+00:00"},
    ]
    ai = [
        {"ai_result_id": "A1", "image_id": "I1", "ai_findings": "positive", "pneumonia_type": "bacterial_pneumonia",
         "ai_model_version": "pneumonia_resnet50_v1", "processed_at": "2026-10-01T02:10:00+00:00"},
        {"ai_result_id": "A2", "image_id": "I2b", "ai_findings": "negative", "pneumonia_type": None,
         "ai_model_version": "pneumonia_resnet50_v1", "processed_at": "2026-10-02T00:50:00+00:00"},
        {"ai_result_id": "A3a", "image_id": "I3", "ai_findings": "positive", "pneumonia_type": "viral_pneumonia",
         "ai_model_version": "pneumonia_resnet50_v1", "processed_at": "2026-10-03T00:10:00+00:00"},
        {"ai_result_id": "A3b", "image_id": "I3", "ai_findings": "inconclusive", "pneumonia_type": None,
         "ai_model_version": "pneumonia_resnet50_v1", "processed_at": "2026-10-03T00:20:00+00:00"},
        {"ai_result_id": "A6", "image_id": "I6", "ai_findings": "positive", "pneumonia_type": None,
         "ai_model_version": "pneumonia_resnet50_v1", "processed_at": "2026-10-05T02:20:00+00:00"},
        {"ai_result_id": "A11", "image_id": "I11", "ai_findings": "positive", "pneumonia_type": "viral_pneumonia",
         "ai_model_version": "pneumonia_resnet50_v1", "processed_at": "2026-10-04T00:20:00+00:00"},
    ]
    reviews = [
        {"review_id": "V1", "request_id": "R1", "findings": "Right lower lobe opacity", "reviewed_at": "2026-10-01T03:10:00+00:00"},
        {"review_id": "V3", "request_id": "R3", "findings": "  ", "reviewed_at": "2026-10-03T01:20:00+00:00"},
        {"review_id": "V11", "request_id": "R11a", "findings": "Clear", "reviewed_at": "2026-10-04T01:00:00+00:00"},
    ]

    return ReportInputs(
        hospital={"hospital_id": HOSP, "hospital_name": "Test Hospital", "hospital_code": "T-1",
                  "hospital_type": "Private", "address": "Somewhere"},
        exams=exams,
        requests=requests,
        images=images,
        ai_results=ai,
        reviews=reviews,
        images_uploaded=6,
        patients_registered=4,
        currently_admitted=1,
        active_staff=[{"role": "Radiologist"}, {"role": "Radiologist"}, {"role": "Staff"}],
        audit_rows=[
            {"event_type": "auth.login", "outcome": "success"},
            {"event_type": "auth.login", "outcome": "success"},
            {"event_type": "ai.analysis_failed", "outcome": "failure"},
            {"event_type": "xray.quality_rejected", "outcome": "failure"},
            {"event_type": "auth.permission_denied", "outcome": "denied"},
            {"event_type": "report.exported", "outcome": "success"},
        ],
    )


def build(inputs=None, period=PERIOD, patient_level=True):
    return compute_hospital_report(
        inputs or golden_inputs(),
        period,
        report_id="rep-1",
        generated_at=GENERATED,
        patient_level=patient_level,
    )


def values(report, *keys):
    return {k: (report.metric(k).value, report.metric(k).denominator) for k in keys}


# ============================================================
# GOLDEN NUMBERS
# ============================================================

def test_screening_counts_unique_exams_with_boundaries_and_exclusions():
    report = build()

    assert values(report, "exams_registered", "exams_initial", "exams_follow_up", "exams_cancelled") == {
        "exams_registered": (8, None),
        "exams_initial": (7, None),
        "exams_follow_up": (1, None),
        "exams_cancelled": (1, 8),
    }
    assert values(report, "xray_requested", "analyses_completed", "awaiting_analysis", "awaiting_review") == {
        "xray_requested": (5, 7),
        "analyses_completed": (3, 5),
        "awaiting_analysis": (2, 5),
        "awaiting_review": (1, 3),
    }


def test_ai_outcomes_use_current_result_and_completed_denominator():
    report = build()

    assert values(report, "ai_positive", "ai_negative", "ai_inconclusive", "ai_other") == {
        "ai_positive": (1, 3),
        "ai_negative": (1, 3),
        "ai_inconclusive": (1, 3),
        "ai_other": (0, 3),
    }
    assert report.breakdown("ai_type").denominator == 1
    assert report.breakdown("ai_type").items == (("Bacterial (AI-flagged)", 1),)


def test_review_totals_and_documented_findings():
    report = build()

    assert values(report, "reviewed", "findings_documented") == {
        "reviewed": (2, 3),
        "findings_documented": (1, 2),
    }
    assert report.breakdown("disposition").items == (("Admission", 1), ("Treated and Sent Home", 1))
    assert report.breakdown("severity").items == (("High Risk", 1), ("Not recorded", 1))


def test_turnaround_medians_and_n():
    report = build()

    request_ai = report.metric("tat_request_to_ai")
    ai_review = report.metric("tat_ai_to_review")

    assert (request_ai.value, request_ai.denominator) == (50.0, 3)   # 70, 50, 20
    assert (ai_review.value, ai_review.denominator) == (60.0, 2)     # 60, 60
    assert request_ai.display() == "50 min (n = 3)"


def test_status_breakdown_covers_every_exam():
    report = build()
    status = report.breakdown("status")

    assert status.denominator == 8
    assert dict(status.items) == {
        "Pending": 2, "Awaiting X-Ray": 2, "X-Ray Ready": 1,
        "Completed": 1, "Admitted": 1, "Cancelled": 1,
    }
    assert sum(count for _, count in status.items) == 8


def test_operations_and_snapshot_values_pass_through():
    report = build()

    assert report.metric("images_uploaded").value == 6
    assert "3 completed analyses" in report.metric("images_uploaded").note
    assert report.metric("patients_registered").value == 4
    assert report.metric("currently_admitted").value == 1
    assert report.breakdown("staff").items == (("Radiologist", 2), ("Staff", 1))


def test_trend_sums_match_headline_numbers():
    report = build()

    assert report.trend_granularity == "day"
    assert [(b.label, b.registered, b.analyzed, b.reviewed) for b in report.trend] == [
        ("2026-10-01", 1, 1, 1),
        ("2026-10-02", 1, 1, 0),
        ("2026-10-03", 1, 1, 1),
        ("2026-10-04", 3, 0, 0),
        ("2026-10-05", 1, 0, 0),
        ("2026-10-06", 0, 0, 0),
        ("2026-10-07", 1, 0, 0),
    ]
    assert sum(b.registered for b in report.trend) == report.metric("exams_registered").value
    assert sum(b.analyzed for b in report.trend) == report.metric("analyses_completed").value
    assert sum(b.reviewed for b in report.trend) == report.metric("reviewed").value


def test_percentages_always_carry_their_denominator():
    report = build()

    assert report.metric("reviewed").display() == "2 of 3 (66.7%)"
    assert report.metric("exams_registered").display() == "8"


def test_patient_level_rows_are_minimal_and_ordered():
    report = build()

    assert report.exam_rows_total == 8
    assert not report.exam_rows_capped
    assert [r.examination_id for r in report.exam_rows] == ["E1", "E2", "E3", "E4", "E11", "E5", "E6", "E10"]

    e1 = report.exam_rows[0]
    assert e1.registered_local == "2026-10-01 00:00"
    assert e1.ai_category == "AI-flagged positive"
    assert e1.ai_type == "Bacterial (AI-flagged)"
    assert e1.review_status == "Reviewed"
    assert e1.findings_documented is True
    assert (e1.request_to_ai_minutes, e1.ai_to_review_minutes) == (70.0, 60.0)

    e11 = next(r for r in report.exam_rows if r.examination_id == "E11")
    assert (e11.request_status, e11.ai_category, e11.review_status) == ("Pending", None, "No AI result")

    e6 = next(r for r in report.exam_rows if r.examination_id == "E6")
    assert e6.review_status == "Not applicable (cancelled)"

    fields = {f.name for f in dataclasses.fields(calc.ExamRow)}
    assert not fields & {"first_name", "last_name", "patient_name", "diagnosis", "findings", "date_of_birth"}


def test_aggregate_only_report_has_no_patient_rows():
    report = build(patient_level=False)

    assert report.exam_rows == ()
    assert report.exam_rows_total == 0
    assert report.metric("exams_registered").value == 8


def test_patient_row_cap(monkeypatch):
    monkeypatch.setattr(calc, "PATIENT_ROW_CAP", 3)
    report = build()

    assert len(report.exam_rows) == 3
    assert report.exam_rows_total == 8
    assert report.exam_rows_capped


def test_audit_activity_section():
    activity = build().audit_activity

    assert activity.total == 6
    assert dict(activity.by_outcome) == {"success": 3, "failure": 2, "denied": 1}
    highlights = dict(activity.highlights)
    assert highlights["Successful sign-ins"] == 2
    assert highlights["AI analyses that failed"] == 1
    assert highlights["Images rejected by the X-ray validator"] == 1
    assert highlights["Access denied events"] == 1
    assert highlights["Audit / report exports generated"] == 1


def test_report_is_immutable():
    report = build()

    with pytest.raises(dataclasses.FrozenInstanceError):
        report.report_id = "other"
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.metrics[0].value = 99
    assert isinstance(report.metrics, tuple) and isinstance(report.exam_rows, tuple)


def test_report_metadata():
    report = build()

    assert report.report_id == "rep-1"
    assert report.period_start == "2026-10-01" and report.period_end == "2026-10-07"
    assert report.period_start_utc == "2026-09-30T16:00:00+00:00"
    assert report.period_end_utc == "2026-10-07T16:00:00+00:00"
    assert report.generated_at_local == "2026-10-08 10:00"
    assert "not a confirmed diagnosis" in report.disclaimer
    assert report.report_b_status.startswith("Unavailable")


# ============================================================
# EMPTY PERIOD / NULLS
# ============================================================

def test_empty_period():
    inputs = ReportInputs(hospital={"hospital_id": HOSP, "hospital_name": "Test Hospital"}, exams=[])
    report = build(inputs)

    assert report.metric("exams_registered").value == 0
    assert report.metric("reviewed").pct is None
    assert report.metric("reviewed").display() == "0 of 0 (n/a)"
    assert report.metric("tat_request_to_ai").value is None
    assert report.metric("tat_request_to_ai").display() == "Not available"
    assert all(b.registered == 0 for b in report.trend)
    assert report.audit_activity is None
    assert all(not b.items for b in report.breakdowns)


def test_missing_timestamps_are_excluded_from_turnaround_not_counts():
    inputs = golden_inputs()
    inputs.ai_results[0]["processed_at"] = None   # A1 -> still the only AI result of I1
    report = build(inputs)

    assert report.metric("analyses_completed").value == 3
    assert report.metric("tat_request_to_ai").denominator == 2
    assert report.metric("tat_ai_to_review").denominator == 1


def test_negative_durations_are_ignored():
    inputs = golden_inputs()
    inputs.reviews[0]["reviewed_at"] = "2026-10-01T02:00:00+00:00"  # before the AI result
    report = build(inputs)

    assert report.metric("tat_ai_to_review").denominator == 1


def test_unrecognised_ai_finding_is_counted_separately():
    inputs = golden_inputs()
    inputs.ai_results[1]["ai_findings"] = "weird"
    report = build(inputs)

    assert values(report, "ai_negative", "ai_other") == {"ai_negative": (0, 3), "ai_other": (1, 3)}


# ============================================================
# PERIODS
# ============================================================

def test_weekly_period_is_iso_week_in_manila_time():
    period = weekly_period(date(2026, 10, 25))   # a Sunday

    assert (period.start, period.end) == (date(2026, 10, 19), date(2026, 10, 26))
    assert period.label.startswith("ISO week 2026-W43")
    assert period.start_utc == datetime(2026, 10, 18, 16, 0, tzinfo=timezone.utc)


def test_weekly_period_across_iso_year_boundary():
    period = weekly_period(date(2027, 1, 1))

    assert period.start == date(2026, 12, 28)
    assert period.label.startswith("ISO week 2026-W53")


def test_monthly_period_december_and_february():
    december = monthly_period(2026, 12)
    february = monthly_period(2028, 2)

    assert (december.start, december.end) == (date(2026, 12, 1), date(2027, 1, 1))
    assert december.end_utc == datetime(2026, 12, 31, 16, 0, tzinfo=timezone.utc)
    assert february.days == 29


def test_custom_period_validation():
    with pytest.raises(ValueError):
        custom_period(date(2026, 10, 7), date(2026, 10, 1))
    with pytest.raises(ValueError):
        custom_period(date(2025, 1, 1), date(2026, 1, 2))

    single = custom_period(date(2026, 10, 1), date(2026, 10, 1))
    assert single.days == 1


def test_period_boundaries_are_start_inclusive_end_exclusive():
    period = custom_period(date(2026, 10, 1), date(2026, 10, 1))

    assert period.contains(parse_timestamp("2026-09-30T16:00:00Z"))
    assert period.contains(parse_timestamp("2026-10-01T15:59:59.999999+00:00"))
    assert not period.contains(parse_timestamp("2026-10-01T16:00:00+00:00"))
    assert not period.contains(parse_timestamp("2026-09-30T15:59:59+00:00"))
    assert not period.contains(None)


def test_naive_timestamps_are_treated_as_utc():
    assert parse_timestamp("2026-10-01T00:00:00") == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert parse_timestamp("not a date") is None
    assert parse_timestamp(datetime(2026, 10, 1, 8, tzinfo=REPORT_TZ)) == datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_long_custom_period_buckets_by_iso_week():
    period = custom_period(date(2026, 8, 1), date(2026, 10, 31))
    report = build(period=period)

    assert report.trend_granularity == "ISO week"
    assert sum(b.registered for b in report.trend) == report.metric("exams_registered").value
    assert any(b.label == "2026-W40" for b in report.trend)
