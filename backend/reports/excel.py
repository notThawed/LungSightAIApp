"""
Excel export of a HospitalReport.

Sheets: Summary, Examinations, Clinical Review, Definitions. The two
patient-level sheets are written only when report.patient_level is true and
contain internal ids / patient codes, never names. Every text cell is written
as a literal string and neutralised if it starts with = + - @.
"""

import io

import xlsxwriter


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_text(value):
    if value is None:
        return ""
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


class _Sheet:
    def __init__(self, book, name, formats):
        self.ws = book.add_worksheet(name)
        self.f = formats
        self.row = 0

    def text(self, row, col, value, fmt=None):
        self.ws.write_string(row, col, safe_text(value), fmt)

    def cell(self, row, col, value, fmt=None):
        if value is None:
            self.ws.write_blank(row, col, None, fmt)
        elif isinstance(value, bool):
            self.ws.write_string(row, col, "Yes" if value else "No", fmt)
        elif isinstance(value, (int, float)):
            self.ws.write_number(row, col, value, fmt)
        else:
            self.text(row, col, value, fmt)

    def line(self, *values, fmt=None):
        for col, value in enumerate(values):
            self.cell(self.row, col, value, fmt)
        self.row += 1

    def header(self, *labels):
        self.line(*labels, fmt=self.f["header"])

    def title(self, text):
        self.text(self.row, 0, text, self.f["title"])
        self.row += 1

    def gap(self):
        self.row += 1


def _summary(sheet, report):
    ws = sheet.ws
    ws.set_column(0, 0, 44)
    ws.set_column(1, 4, 16)
    ws.set_column(5, 5, 48)

    sheet.title("LungSight Hospital Activity Report")
    for label, value in report.hospital:
        sheet.line(label, value)
    sheet.line("Period", report.period_label)
    sheet.line("Period start (local, inclusive)", report.period_start)
    sheet.line("Period end (local, inclusive)", report.period_end)
    sheet.line("Timezone", report.timezone)
    sheet.line("Generated (Manila)", report.generated_at_local)
    sheet.line("Generated (UTC)", report.generated_at_utc)
    sheet.line("Report ID", report.report_id)
    sheet.gap()

    sheet.header("Measure", "Value", "Denominator", "Percent", "Unit", "As shown in report")
    for metric in report.metrics:
        sheet.line(
            metric.label,
            metric.value,
            metric.denominator,
            metric.pct,
            metric.unit,
            metric.display() + (f" — {metric.note}" if metric.note else ""),
        )
    sheet.gap()

    for breakdown in report.breakdowns:
        sheet.title(f"{breakdown.title} (n = {breakdown.denominator})")
        sheet.header("Category", "Count", "Percent")
        if not breakdown.items:
            sheet.line("No data in this period", 0, None)
        for label, count in breakdown.items:
            sheet.line(label, count, breakdown.pct(count))
        sheet.gap()

    sheet.title(f"Examinations per {report.trend_granularity} (by registration date)")
    sheet.header("Period", "Registered", "Analysed", "Reviewed")
    for bucket in report.trend:
        sheet.line(bucket.label, bucket.registered, bucket.analyzed, bucket.reviewed)
    sheet.gap()

    sheet.title("System activity (audit log)")
    activity = report.audit_activity
    if activity is None or activity.total == 0:
        sheet.line("No audit events were recorded for this hospital in this period.")
    else:
        sheet.header("Measure", "Count")
        for label, count in activity.highlights:
            sheet.line(label, count)
        sheet.line("All audit events", activity.total)
    if activity is not None:
        sheet.line(activity.note)
    sheet.gap()

    sheet.title("AI performance")
    sheet.line(report.report_b_status)
    sheet.gap()
    sheet.line(report.disclaimer, fmt=sheet.f["note"])


EXAM_COLUMNS = (
    ("Examination ID", "examination_id", 38),
    ("Patient code", "patient_code", 16),
    ("Registered (Manila)", "registered_local", 18),
    ("Examination date", "examination_date", 16),
    ("Type", "examination_type", 22),
    ("Follow-up", "follow_up", 10),
    ("Status", "status", 16),
    ("X-ray request status", "request_status", 18),
    ("AI category", "ai_category", 22),
    ("AI-flagged type", "ai_type", 22),
    ("AI model version", "ai_model_version", 24),
    ("Review status", "review_status", 24),
    ("Request to AI (min)", "request_to_ai_minutes", 18),
    ("AI to review (min)", "ai_to_review_minutes", 18),
)

REVIEW_COLUMNS = (
    ("Examination ID", "examination_id", 38),
    ("Patient code", "patient_code", 16),
    ("AI category", "ai_category", 22),
    ("AI-flagged type", "ai_type", 22),
    ("Review status", "review_status", 20),
    ("Findings documented", "findings_documented", 18),
    ("Disposition", "disposition", 22),
    ("Severity (CURB-65 risk)", "severity", 22),
    ("AI to review (min)", "ai_to_review_minutes", 18),
)


def _rows_sheet(sheet, report, columns, rows, empty_text):
    for index, (_, _, width) in enumerate(columns):
        sheet.ws.set_column(index, index, width)

    if report.exam_rows_capped:
        sheet.line(f"Only the first {len(report.exam_rows):,} of {report.exam_rows_total:,} examinations "
                   "are listed. Narrow the period for the full list.", fmt=sheet.f["note"])

    sheet.header(*(label for label, _, _ in columns))
    sheet.ws.freeze_panes(sheet.row, 0)

    if not rows:
        sheet.line(empty_text)
    for row in rows:
        sheet.line(*(getattr(row, attr) for _, attr, _ in columns))


def _definitions(sheet, report):
    sheet.ws.set_column(0, 0, 36)
    sheet.ws.set_column(1, 1, 110)
    sheet.header("Term", "Definition")
    for term, definition in report.definitions:
        sheet.line(term, definition, fmt=sheet.f["wrap"])
    sheet.gap()
    sheet.title("Limitations")
    for item in report.limitations:
        sheet.line(item)
    sheet.gap()
    sheet.line(report.disclaimer, fmt=sheet.f["note"])


def render_excel(report):
    buffer = io.BytesIO()
    book = xlsxwriter.Workbook(buffer, {"in_memory": True, "strings_to_formulas": False,
                                        "strings_to_urls": False})
    formats = {
        "title": book.add_format({"bold": True, "font_size": 12, "font_color": "#0E7490"}),
        "header": book.add_format({"bold": True, "bg_color": "#E2E8F0", "border": 1}),
        "note": book.add_format({"italic": True, "font_color": "#475569"}),
        "wrap": book.add_format({"text_wrap": True, "valign": "top"}),
    }

    _summary(_Sheet(book, "Summary", formats), report)

    if report.patient_level:
        _rows_sheet(_Sheet(book, "Examinations", formats), report, EXAM_COLUMNS, report.exam_rows,
                    "No examinations in this period.")
        reviewed = [r for r in report.exam_rows if r.review_status in ("Reviewed", "Awaiting review")]
        _rows_sheet(_Sheet(book, "Clinical Review", formats), report, REVIEW_COLUMNS, reviewed,
                    "No completed analyses in this period.")

    _definitions(_Sheet(book, "Definitions", formats), report)

    book.close()
    return buffer.getvalue()
