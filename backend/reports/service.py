"""
Hospital report service: scope -> fetch -> calculate -> render, with audit.

report.generated is written after the calculation succeeds; report.exported
after the file bytes exist ("export generated", not "downloaded"). Both are
keyed by report id so Streamlit reruns never duplicate them.
"""

import re
import uuid
from datetime import datetime, timezone

from backend import audit
from backend.reports.calculations import compute_hospital_report
from backend.reports.data import fetch_report_inputs, get_report_scope


class ReportExportError(Exception):
    pass


def _metadata(period_kind, period_start, period_end, report_type="hospital_activity"):
    return {
        "report_type": report_type,
        "period_kind": period_kind,
        "period_start": period_start,
        "period_end": period_end,
    }


def generate_hospital_report(period, requested_hospital_id=None):
    scope = get_report_scope(requested_hospital_id)
    report_id = str(uuid.uuid4())
    metadata = _metadata(period.kind, period.start.isoformat(), period.last_day.isoformat())

    try:
        inputs = fetch_report_inputs(scope.hospital_id, period)
        report = compute_hospital_report(
            inputs,
            period,
            report_id=report_id,
            generated_at=datetime.now(timezone.utc),
            patient_level=scope.patient_level,
        )

    except Exception as exc:
        audit.record_event(
            "report.generated",
            "failure",
            target_id=report_id,
            target_hospital_id=scope.hospital_id,
            metadata={**metadata, "error_class": audit.error_class(exc)},
            idempotency_key=f"report.generated:{report_id}",
        )
        raise

    audit.record_event(
        "report.generated",
        target_id=report_id,
        target_hospital_id=scope.hospital_id,
        metadata=metadata,
        idempotency_key=f"report.generated:{report_id}",
    )

    return report


def _renderers():
    from backend.reports.excel import render_excel
    from backend.reports.pdf import render_pdf

    return {
        "pdf": (render_pdf, "application/pdf"),
        "xlsx": (render_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }


def export_filename(report, fmt):
    code = re.sub(r"[^A-Za-z0-9-]+", "-", report.hospital[1][1] or "hospital").strip("-") or "hospital"
    return f"lungsight_report_{code}_{report.period_start}_{report.period_end}.{fmt}"


def export_hospital_report(report, fmt):
    """Returns (bytes, filename, mime). Raises ReportExportError; never returns a partial file."""

    renderers = _renderers()

    if fmt not in renderers:
        raise ValueError(f"Unsupported format: {fmt}")

    scope = get_report_scope(report.hospital_id)

    if scope.hospital_id != report.hospital_id or (report.patient_level and not scope.patient_level):
        audit.record_event(
            "auth.permission_denied",
            "denied",
            metadata={"resource": "hospital_reports"},
        )
        raise audit.AuditAccessDenied("You do not have access to this report.")

    render, mime = renderers[fmt]
    metadata = {
        **_metadata(report.period_kind, report.period_start, report.period_end, report.report_type),
        "format": fmt,
    }

    try:
        data = render(report)
        if not data:
            raise ReportExportError("empty output")

    except Exception as exc:
        audit.record_event(
            "report.exported",
            "failure",
            target_id=report.report_id,
            target_hospital_id=report.hospital_id,
            metadata={**metadata, "error_class": audit.error_class(exc)},
            idempotency_key=f"report.exported:{report.report_id}:{fmt}:failure",
        )
        raise ReportExportError(f"The {fmt.upper()} file could not be generated.") from exc

    audit.record_event(
        "report.exported",
        target_id=report.report_id,
        target_hospital_id=report.hospital_id,
        metadata=metadata,
        idempotency_key=f"report.exported:{report.report_id}:{fmt}",
    )

    return data, export_filename(report, fmt), mime
