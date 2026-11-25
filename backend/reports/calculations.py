"""
Hospital report calculations — pure functions, no Supabase, no Streamlit.

Unit of counting: one examination. Each exam is reduced to a single record
using the app's own "current result" rule before anything is counted:

    current request = latest xray_request by requested_at
    current image   = latest xray_image of that request by uploaded_at
    current AI      = latest xray_ai_result of that image by processed_at
    current review  = latest xray_review of that request by reviewed_at

So retries and re-analyses never add a second count. The result is one
immutable HospitalReport consumed by the page, the PDF and the Excel export.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from statistics import median

from backend.reports.periods import REPORT_TZ, REPORT_TZ_LABEL, parse_timestamp, to_local_date


REPORT_TYPE = "hospital_activity"

EXCLUDED_EXAM_TYPES = ("Inpatient Round",)
CANCELLED = "Cancelled"

AI_CATEGORIES = {
    "positive": "AI-flagged positive",
    "negative": "AI negative",
    "inconclusive": "AI inconclusive",
}
AI_OTHER = "AI result unrecognised"

PNEUMONIA_TYPES = {
    "bacterial_pneumonia": "Bacterial (AI-flagged)",
    "viral_pneumonia": "Viral (AI-flagged)",
    "covid_pneumonia": "COVID-19 (AI-flagged)",
    "inconclusive": "Type inconclusive",
}

PATIENT_ROW_CAP = 5_000
WEEKLY_BUCKET_AFTER_DAYS = 62

DISCLAIMER = (
    "LungSight AI is a screening aid. AI results are not a confirmed diagnosis; "
    "diagnosis is made by the reviewing physician."
)


# ============================================================
# RESULT TYPES
# ============================================================

@dataclass(frozen=True)
class Metric:
    key: str
    section: str
    label: str
    value: float | int | None
    denominator: int | None = None
    unit: str = "count"          # "count" | "minutes"
    note: str = ""

    @property
    def pct(self):
        if self.denominator is None or self.unit != "count":
            return None
        if self.denominator == 0 or self.value is None:
            return None
        return round(100.0 * self.value / self.denominator, 1)

    def display(self):
        if self.value is None:
            return "Not available"

        if self.unit == "minutes":
            return f"{format_minutes(self.value)} (n = {self.denominator})"

        text = f"{self.value:,}"

        if self.denominator is not None:
            pct = self.pct
            text += f" of {self.denominator:,}"
            text += f" ({pct:.1f}%)" if pct is not None else " (n/a)"

        return text


@dataclass(frozen=True)
class Breakdown:
    key: str
    section: str
    title: str
    denominator: int
    items: tuple            # ((label, count), ...)

    def pct(self, count):
        return None if not self.denominator else round(100.0 * count / self.denominator, 1)


@dataclass(frozen=True)
class TrendBucket:
    label: str
    registered: int
    analyzed: int
    reviewed: int


@dataclass(frozen=True)
class ExamRow:
    examination_id: str
    patient_code: str | None
    registered_local: str
    examination_date: str | None
    examination_type: str | None
    follow_up: bool
    status: str | None
    request_status: str | None
    ai_category: str | None
    ai_type: str | None
    ai_model_version: str | None
    review_status: str
    findings_documented: bool | None
    disposition: str | None
    severity: str | None
    request_to_ai_minutes: float | None
    ai_to_review_minutes: float | None


@dataclass(frozen=True)
class AuditActivity:
    total: int
    by_category: tuple      # ((category, count), ...)
    by_outcome: tuple
    highlights: tuple       # ((label, count), ...)
    note: str


@dataclass(frozen=True)
class HospitalReport:
    report_id: str
    report_type: str
    hospital: tuple         # ((label, value), ...)
    hospital_id: str
    hospital_name: str
    period_kind: str
    period_label: str
    period_start: str       # local ISO date, inclusive
    period_end: str         # local ISO date, inclusive (last day)
    period_start_utc: str
    period_end_utc: str     # exclusive
    timezone: str
    generated_at_utc: str
    generated_at_local: str
    metrics: tuple
    breakdowns: tuple
    trend: tuple
    trend_granularity: str
    exam_rows: tuple
    exam_rows_total: int
    exam_rows_capped: bool
    patient_level: bool
    definitions: tuple      # ((term, definition), ...)
    limitations: tuple
    report_b_status: str
    audit_activity: AuditActivity | None = None
    disclaimer: str = DISCLAIMER

    def metric(self, key):
        for item in self.metrics:
            if item.key == key:
                return item
        raise KeyError(key)

    def breakdown(self, key):
        for item in self.breakdowns:
            if item.key == key:
                return item
        raise KeyError(key)

    def section_metrics(self, section):
        return tuple(m for m in self.metrics if m.section == section)

    def section_breakdowns(self, section):
        return tuple(b for b in self.breakdowns if b.section == section)


@dataclass
class ReportInputs:
    hospital: dict
    exams: list
    requests: list = field(default_factory=list)
    images: list = field(default_factory=list)
    ai_results: list = field(default_factory=list)
    reviews: list = field(default_factory=list)
    images_uploaded: int = 0
    patients_registered: int = 0
    currently_admitted: int = 0
    active_staff: list = field(default_factory=list)   # [{"role": "Radiologist"}, ...]
    audit_rows: list | None = None


# ============================================================
# HELPERS
# ============================================================

def format_minutes(minutes):
    if minutes is None:
        return "—"
    minutes = float(minutes)
    if minutes < 60:
        return f"{minutes:.0f} min"
    hours = minutes / 60
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} days"


def _latest(rows, time_key, id_key):
    """Latest row by timestamp, ties broken by id; rows without a timestamp sort first."""

    if not rows:
        return None

    def key(row):
        moment = parse_timestamp(row.get(time_key))
        return (moment is not None, moment.timestamp() if moment else 0.0, str(row.get(id_key) or ""))

    return max(rows, key=key)


def _group(rows, key):
    grouped = {}
    for row in rows:
        grouped.setdefault(str(row.get(key)), []).append(row)
    return grouped


def _minutes_between(start, end):
    if start is None or end is None:
        return None
    delta = (end - start).total_seconds() / 60.0
    return delta if delta >= 0 else None


def _patient_hospital(exam):
    patient = exam.get("patients")
    if isinstance(patient, list):
        patient = patient[0] if patient else None
    return (patient or {}).get("hospital_id"), (patient or {}).get("patient_code")


# ============================================================
# PER-EXAM REDUCTION
# ============================================================

@dataclass(frozen=True)
class _ExamFact:
    exam: dict
    created_at: object
    patient_code: str | None
    cancelled: bool
    follow_up: bool
    request: dict | None
    image: dict | None
    ai: dict | None
    review: dict | None

    @property
    def has_request(self):
        return self.request is not None

    @property
    def has_ai(self):
        return self.ai is not None

    @property
    def reviewed(self):
        return self.ai is not None and self.review is not None

    @property
    def ai_key(self):
        if not self.ai:
            return None
        return (self.ai.get("ai_findings") or "").strip().lower() or None


def reduce_exams(inputs, period, hospital_id):
    """One fact per in-scope examination, applying the current-result rule."""

    requests_by_exam = _group(inputs.requests, "examination_id")
    images_by_request = _group(inputs.images, "request_id")
    ai_by_image = _group(inputs.ai_results, "image_id")
    reviews_by_request = _group(inputs.reviews, "request_id")

    facts = {}

    for exam in inputs.exams:
        exam_id = exam.get("examination_id")
        if not exam_id or str(exam_id) in facts:
            continue

        if exam.get("examination_type") in EXCLUDED_EXAM_TYPES:
            continue

        patient_hospital, patient_code = _patient_hospital(exam)
        if str(patient_hospital) != str(hospital_id):
            continue

        created_at = parse_timestamp(exam.get("created_at"))
        if not period.contains(created_at):
            continue

        request = _latest(requests_by_exam.get(str(exam_id), []), "requested_at", "request_id")
        image = (
            _latest(images_by_request.get(str(request["request_id"]), []), "uploaded_at", "image_id")
            if request else None
        )
        ai = (
            _latest(ai_by_image.get(str(image["image_id"]), []), "processed_at", "ai_result_id")
            if image else None
        )
        review = (
            _latest(reviews_by_request.get(str(request["request_id"]), []), "reviewed_at", "review_id")
            if request else None
        )

        facts[str(exam_id)] = _ExamFact(
            exam=exam,
            created_at=created_at,
            patient_code=patient_code,
            cancelled=exam.get("status") == CANCELLED,
            follow_up=exam.get("follow_up_sequence") is not None,
            request=request,
            image=image,
            ai=ai,
            review=review,
        )

    return sorted(facts.values(), key=lambda f: (f.created_at, str(f.exam["examination_id"])))


# ============================================================
# REPORT
# ============================================================

def _count_items(values, order=None, missing_label="Not recorded"):
    counts = Counter(v if v not in (None, "") else missing_label for v in values)
    labels = list(order or []) + sorted(k for k in counts if k not in (order or []))
    return tuple((label, counts[label]) for label in labels if counts.get(label))


def _trend(facts, period):
    weekly = period.days > WEEKLY_BUCKET_AFTER_DAYS
    buckets = {}

    day = period.start
    while day < period.end:
        if weekly:
            monday = day - timedelta(days=day.weekday())
            iso_year, iso_week, _ = monday.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
        else:
            key = day.isoformat()
        buckets.setdefault(key, [0, 0, 0])
        day += timedelta(days=1)

    for fact in facts:
        local = to_local_date(fact.created_at)
        if weekly:
            monday = local - timedelta(days=local.weekday())
            iso_year, iso_week, _ = monday.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
        else:
            key = local.isoformat()
        bucket = buckets.setdefault(key, [0, 0, 0])
        bucket[0] += 1
        if not fact.cancelled and fact.has_ai:
            bucket[1] += 1
        if not fact.cancelled and fact.reviewed:
            bucket[2] += 1

    granularity = "ISO week" if weekly else "day"
    return tuple(TrendBucket(k, *v) for k, v in buckets.items()), granularity


def _audit_activity(rows):
    if rows is None:
        return None

    categories = Counter((r.get("event_type") or "").split(".", 1)[0] for r in rows)
    outcomes = Counter(r.get("outcome") for r in rows)
    events = Counter(r.get("event_type") for r in rows)

    highlights = (
        ("Successful sign-ins", events["auth.login"]),
        ("Sign-ins denied (account/hospital status)", events["auth.login_denied"]),
        ("Access denied events", events["auth.permission_denied"]),
        ("AI analyses that failed", events["ai.analysis_failed"]),
        ("Images rejected by the X-ray validator", events["xray.quality_rejected"]),
        ("Validator overrides", events["xray.quality_overridden"]),
        ("AI results corrected by physicians", events["ai.result_corrected"]),
        ("Audit / report exports generated", events["audit.exported"] + events["report.exported"]),
    )

    return AuditActivity(
        total=len(rows),
        by_category=tuple(sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))),
        by_outcome=tuple((o, outcomes[o]) for o in ("success", "failure", "denied") if outcomes[o]),
        highlights=highlights,
        note=(
            "From the audit log for this hospital. Audit logging began on 2026-10-25, so earlier "
            "activity is not included. Failed sign-ins without a known account are platform-wide "
            "and not attributed to a hospital."
        ),
    )


DEFINITIONS = (
    ("Examination", "One row in examinations for this hospital, registered (created_at) inside the period. "
                    "Inpatient ward rounds are excluded."),
    ("Current result", "Latest X-ray request of the exam, its latest image, that image's latest AI result, "
                       "and the latest physician review of the request. Re-analyses replace, never add."),
    ("Active examinations", "Examinations whose current status is not Cancelled."),
    ("X-ray requested", "Active examinations with at least one X-ray request."),
    ("Analyses completed", "X-ray-requested examinations whose current image has a saved AI result."),
    ("Awaiting analysis", "X-ray-requested examinations without a current AI result."),
    ("Awaiting physician review", "Completed analyses with no physician review on the current request."),
    ("AI-flagged positive / negative / inconclusive", "The current AI result's finding. Percentages use all "
                                                      "completed analyses as the denominator. "
                                                      "An AI flag is not a diagnosis."),
    ("Reviewed", "Completed analyses with a physician review on the current request."),
    ("Findings documented", "Reviews whose findings field is filled in (presence only)."),
    ("Turnaround", "Median minutes between request and AI result, and between AI result and review, "
                   "for examinations that have both timestamps. n is shown."),
    ("X-ray images uploaded", "Images uploaded in the period (the subscription-usage basis). Can exceed "
                              "completed analyses when an upload is retried."),
    ("Snapshot values", "Current status, currently admitted and active staff reflect the moment the report "
                        "was generated, not the end of the period."),
)

LIMITATIONS = (
    "Statuses are current values; the database keeps no status history for examinations.",
    "Failed AI analyses and images rejected by the X-ray validator are not stored with the examination. "
    "They appear in the System activity section (audit log, from 2026-10-25).",
    "Physician-confirmed labels are only stored for patients with AI-training consent, so AI-versus-"
    "physician agreement is not reported.",
    "AI accuracy (sensitivity, specificity) is not reported: no independent labelled reference set exists.",
    "Subscription usage counts images per UTC calendar month; this report uses Asia/Manila days.",
)

REPORT_B_STATUS = (
    "Unavailable. AI accuracy needs an independent, labelled reference set (not model outputs and not "
    "routine physician reviews without an approved methodology). None exists in this system."
)


def compute_hospital_report(inputs, period, *, report_id, generated_at, patient_level):
    """Build the immutable report. generated_at must be an aware datetime."""

    hospital = inputs.hospital or {}
    hospital_id = str(hospital.get("hospital_id"))

    facts = reduce_exams(inputs, period, hospital_id)

    active = [f for f in facts if not f.cancelled]
    requested = [f for f in active if f.has_request]
    completed = [f for f in requested if f.has_ai]
    awaiting_analysis = [f for f in requested if not f.has_ai]
    reviewed = [f for f in completed if f.reviewed]
    awaiting_review = [f for f in completed if not f.reviewed]

    ai_counts = Counter(f.ai_key if f.ai_key in AI_CATEGORIES else "other" for f in completed)
    positives = [f for f in completed if f.ai_key == "positive"]

    findings_documented = [
        f for f in reviewed if (f.review.get("findings") or "").strip()
    ]

    tat_request_ai = [
        m for m in (
            _minutes_between(parse_timestamp(f.request.get("requested_at")),
                             parse_timestamp(f.ai.get("processed_at")))
            for f in completed
        ) if m is not None
    ]
    tat_ai_review = [
        m for m in (
            _minutes_between(parse_timestamp(f.ai.get("processed_at")),
                             parse_timestamp(f.review.get("reviewed_at")))
            for f in reviewed
        ) if m is not None
    ]

    metrics = (
        Metric("exams_registered", "screening", "Examinations registered", len(facts)),
        Metric("exams_initial", "screening", "Initial examinations", sum(not f.follow_up for f in facts)),
        Metric("exams_follow_up", "screening", "Follow-up examinations", sum(f.follow_up for f in facts)),
        Metric("exams_cancelled", "screening", "Cancelled", len(facts) - len(active), len(facts)),
        Metric("xray_requested", "screening", "X-ray requested", len(requested), len(active)),
        Metric("analyses_completed", "screening", "Analyses completed", len(completed), len(requested)),
        Metric("awaiting_analysis", "screening", "Awaiting analysis", len(awaiting_analysis), len(requested)),
        Metric("awaiting_review", "screening", "Awaiting physician review", len(awaiting_review), len(completed)),

        Metric("ai_positive", "ai", "AI-flagged positive", ai_counts["positive"], len(completed)),
        Metric("ai_negative", "ai", "AI negative", ai_counts["negative"], len(completed)),
        Metric("ai_inconclusive", "ai", "AI inconclusive", ai_counts["inconclusive"], len(completed)),
        Metric("ai_other", "ai", AI_OTHER, ai_counts["other"], len(completed)),

        Metric("reviewed", "review", "Reviewed by a physician", len(reviewed), len(completed)),
        Metric("findings_documented", "review", "Findings documented", len(findings_documented), len(reviewed)),

        Metric("tat_request_to_ai", "operations", "Median time, request to AI result",
               round(median(tat_request_ai), 1) if tat_request_ai else None,
               len(tat_request_ai), unit="minutes"),
        Metric("tat_ai_to_review", "operations", "Median time, AI result to review",
               round(median(tat_ai_review), 1) if tat_ai_review else None,
               len(tat_ai_review), unit="minutes"),
        Metric("images_uploaded", "operations", "X-ray images uploaded", inputs.images_uploaded,
               note=f"Compare with {len(completed):,} completed analyses."),
        Metric("patients_registered", "operations", "Patients registered", inputs.patients_registered),
        Metric("currently_admitted", "operations", "Currently admitted (snapshot)", inputs.currently_admitted),
    )

    breakdowns = (
        Breakdown("status", "screening", "Current status of examinations", len(facts),
                  _count_items((f.exam.get("status") for f in facts),
                               ["Pending", "Awaiting X-Ray", "X-Ray Ready", "Completed",
                                "Admitted", "Discharged", "Cancelled"])),
        Breakdown("ai_type", "ai", "AI-flagged type among AI-flagged positives", len(positives),
                  _count_items((PNEUMONIA_TYPES.get((f.ai.get("pneumonia_type") or "").strip().lower(),
                                                    f.ai.get("pneumonia_type")) for f in positives),
                               list(PNEUMONIA_TYPES.values()), missing_label="Type not classified")),
        Breakdown("disposition", "review", "Disposition of reviewed examinations", len(reviewed),
                  _count_items((f.exam.get("disposition") for f in reviewed))),
        Breakdown("severity", "review", "Severity (CURB-65 risk) of reviewed examinations", len(reviewed),
                  _count_items((f.exam.get("severity_status") for f in reviewed),
                               ["Low Risk", "Moderate Risk", "High Risk"])),
        Breakdown("staff", "operations", "Active staff by role (snapshot)", len(inputs.active_staff),
                  _count_items((s.get("role") for s in inputs.active_staff),
                               ["Hospital Admin", "Radiologist", "Radiologic Technologist", "Staff"])),
    )

    trend, granularity = _trend(facts, period)

    rows = []
    if patient_level:
        for f in facts[:PATIENT_ROW_CAP]:
            ai_type = None
            if f.ai and f.ai_key == "positive":
                raw = (f.ai.get("pneumonia_type") or "").strip().lower()
                ai_type = PNEUMONIA_TYPES.get(raw, raw or "Type not classified")

            if f.cancelled:
                review_status = "Not applicable (cancelled)"
            elif f.reviewed:
                review_status = "Reviewed"
            elif f.has_ai:
                review_status = "Awaiting review"
            else:
                review_status = "No AI result"

            request_ai = (
                _minutes_between(parse_timestamp(f.request.get("requested_at")),
                                 parse_timestamp(f.ai.get("processed_at")))
                if f.has_ai else None
            )
            ai_review = (
                _minutes_between(parse_timestamp(f.ai.get("processed_at")),
                                 parse_timestamp(f.review.get("reviewed_at")))
                if f.reviewed else None
            )

            rows.append(ExamRow(
                examination_id=str(f.exam["examination_id"]),
                patient_code=f.patient_code,
                registered_local=f.created_at.astimezone(REPORT_TZ).strftime("%Y-%m-%d %H:%M"),
                examination_date=(str(f.exam.get("examination_date"))[:10]
                                  if f.exam.get("examination_date") else None),
                examination_type=f.exam.get("examination_type"),
                follow_up=f.follow_up,
                status=f.exam.get("status"),
                request_status=(f.request or {}).get("status"),
                ai_category=(AI_CATEGORIES.get(f.ai_key, AI_OTHER) if f.has_ai else None),
                ai_type=ai_type,
                ai_model_version=(f.ai or {}).get("ai_model_version"),
                review_status=review_status,
                findings_documented=(bool((f.review.get("findings") or "").strip()) if f.reviewed else None),
                disposition=f.exam.get("disposition") if f.reviewed else None,
                severity=f.exam.get("severity_status") if f.reviewed else None,
                request_to_ai_minutes=round(request_ai, 1) if request_ai is not None else None,
                ai_to_review_minutes=round(ai_review, 1) if ai_review is not None else None,
            ))

    hospital_info = (
        ("Hospital", hospital.get("hospital_name")),
        ("Hospital code", hospital.get("hospital_code")),
        ("Type", hospital.get("hospital_type")),
        ("Address", hospital.get("address")),
    )

    generated_utc = generated_at.astimezone(timezone.utc)

    return HospitalReport(
        report_id=str(report_id),
        report_type=REPORT_TYPE,
        hospital=hospital_info,
        hospital_id=hospital_id,
        hospital_name=hospital.get("hospital_name") or "",
        period_kind=period.kind,
        period_label=period.label,
        period_start=period.start.isoformat(),
        period_end=period.last_day.isoformat(),
        period_start_utc=period.start_utc.isoformat(),
        period_end_utc=period.end_utc.isoformat(),
        timezone=REPORT_TZ_LABEL,
        generated_at_utc=generated_utc.isoformat(timespec="seconds"),
        generated_at_local=generated_utc.astimezone(REPORT_TZ).strftime("%Y-%m-%d %H:%M"),
        metrics=metrics,
        breakdowns=breakdowns,
        trend=trend,
        trend_granularity=granularity,
        exam_rows=tuple(rows),
        exam_rows_total=len(facts) if patient_level else 0,
        exam_rows_capped=patient_level and len(facts) > PATIENT_ROW_CAP,
        patient_level=patient_level,
        definitions=DEFINITIONS,
        limitations=LIMITATIONS,
        report_b_status=REPORT_B_STATUS,
        audit_activity=_audit_activity(inputs.audit_rows),
    )

