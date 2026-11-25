"""
PDF export of a HospitalReport (aggregates only — no patient-level rows).

Every figure is printed from the same Metric/Breakdown objects the page shows,
using Metric.display(), so screen and PDF cannot disagree.
"""

import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape  # noqa: E402


SECTION_TITLES = (
    ("screening", "Screening activity"),
    ("ai", "AI outcomes"),
    ("review", "Physician review"),
    ("operations", "Operations"),
)

ACCENT = colors.HexColor("#0E7490")
GRID = colors.HexColor("#CBD5E1")
HEADER_BG = colors.HexColor("#E2E8F0")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("t", parent=base["Title"], textColor=ACCENT, fontSize=18, spaceAfter=6),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], textColor=ACCENT, spaceBefore=10, spaceAfter=4),
        "body": ParagraphStyle("b", parent=base["BodyText"], fontSize=9, leading=12),
        "small": ParagraphStyle("s", parent=base["BodyText"], fontSize=8, leading=10, textColor=colors.HexColor("#475569")),
    }


def _p(text, style):
    return Paragraph(escape(str(text if text is not None else "—")), style)


def _table(rows, widths, style_body):
    data = [[_p(cell, style_body) for cell in row] for row in rows]
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("GRID", (0, 0), (-1, -1), 0.4, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _chart_png(draw, width_in=6.6, height_in=2.4):
    fig, ax = plt.subplots(figsize=(width_in, height_in), dpi=150)
    try:
        draw(ax)
        fig.tight_layout()
        buffer = io.BytesIO()
        fig.savefig(buffer, format="png")
        return buffer.getvalue()
    finally:
        plt.close(fig)


def _trend_chart(report):
    labels = [b.label for b in report.trend]
    series = (
        ("Registered", [b.registered for b in report.trend], "#0E7490"),
        ("Analysed", [b.analyzed for b in report.trend], "#F59E0B"),
        ("Reviewed", [b.reviewed for b in report.trend], "#10B981"),
    )

    def draw(ax):
        width = 0.27
        positions = range(len(labels))
        for offset, (name, values, color) in zip((-width, 0, width), series):
            ax.bar([p + offset for p in positions], values, width=width, label=name, color=color)
        step = max(1, len(labels) // 12)
        ax.set_xticks(list(positions)[::step])
        ax.set_xticklabels(labels[::step], rotation=30, ha="right", fontsize=7)
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.set_ylabel("Examinations", fontsize=8)
        ax.tick_params(axis="y", labelsize=7)
        ax.legend(fontsize=7, frameon=False)
        ax.spines[["top", "right"]].set_visible(False)

    return _chart_png(draw)


def _ai_chart(report):
    metrics = report.section_metrics("ai")

    def draw(ax):
        ax.barh([m.label for m in metrics], [m.value for m in metrics], color="#0E7490")
        ax.invert_yaxis()
        ax.xaxis.get_major_locator().set_params(integer=True)
        ax.tick_params(labelsize=7)
        ax.set_xlabel("Examinations (completed analyses)", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)

    return _chart_png(draw, height_in=1.8)


def render_pdf(report, compress=True):
    styles = _styles()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=20 * mm,
        title=f"LungSight Hospital Report {report.report_id}",
        author="LungSight AI",
        pageCompression=1 if compress else 0,
        invariant=1,
    )
    width = doc.width

    story = [
        _p("Hospital Activity Report", styles["title"]),
        _table(
            [("Field", "Value")]
            + [(label, value) for label, value in report.hospital]
            + [
                ("Period", report.period_label),
                ("Period (local dates)", f"{report.period_start} to {report.period_end} inclusive"),
                ("Timezone", report.timezone),
                ("Generated", f"{report.generated_at_local} (Manila) / {report.generated_at_utc} UTC"),
                ("Report ID", report.report_id),
            ],
            [width * 0.28, width * 0.72],
            styles["body"],
        ),
    ]

    if report.metric("exams_registered").value == 0:
        story += [Spacer(1, 6), _p("No examinations were registered in this period. All counts are zero.", styles["body"])]

    for section, title in SECTION_TITLES:
        block = [_p(title, styles["h2"])]
        block.append(_table(
            [("Measure", "Value", "Note")]
            + [(m.label, m.display(), m.note) for m in report.section_metrics(section)],
            [width * 0.40, width * 0.30, width * 0.30],
            styles["body"],
        ))

        if section == "screening":
            block += [Spacer(1, 4), _p(f"Examinations per {report.trend_granularity} "
                                       "(grouped by registration date; totals equal the counts above)",
                                       styles["small"]),
                      Image(io.BytesIO(_trend_chart(report)), width=width, height=width * 2.4 / 6.6)]
        if section == "ai":
            block += [Spacer(1, 4),
                      Image(io.BytesIO(_ai_chart(report)), width=width, height=width * 1.8 / 6.6),
                      _p("AI flags are a screening aid, not a diagnosis.", styles["small"])]

        story.append(KeepTogether(block[:2]))
        story += block[2:]

        for breakdown in report.section_breakdowns(section):
            rows = [("Category", "Count", "Percent")] + [
                (label, f"{count:,}",
                 f"{breakdown.pct(count):.1f}%" if breakdown.pct(count) is not None else "n/a")
                for label, count in breakdown.items
            ]
            if len(rows) == 1:
                rows.append(("No data in this period", "0", "n/a"))
            story += [Spacer(1, 4), KeepTogether([
                _p(f"{breakdown.title} (n = {breakdown.denominator:,})", styles["body"]),
                _table(rows, [width * 0.55, width * 0.2, width * 0.25], styles["body"]),
            ])]

    story.append(_p("System activity", styles["h2"]))
    activity = report.audit_activity
    if activity is None or activity.total == 0:
        story.append(_p("No audit events were recorded for this hospital in this period.", styles["body"]))
    else:
        story.append(_table([("Measure", "Count")] + [(k, f"{v:,}") for k, v in activity.highlights]
                            + [("All audit events", f"{activity.total:,}")],
                            [width * 0.7, width * 0.3], styles["body"]))
    if activity is not None:
        story.append(_p(activity.note, styles["small"]))

    story += [
        _p("AI performance", styles["h2"]),
        _p(report.report_b_status, styles["body"]),
        _p("Definitions", styles["h2"]),
        _table([("Term", "Definition")] + list(report.definitions), [width * 0.28, width * 0.72], styles["body"]),
        _p("Limitations", styles["h2"]),
    ]
    story += [_p(f"• {item}", styles["body"]) for item in report.limitations]

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawString(16 * mm, 12 * mm, report.disclaimer[:150])
        canvas.drawString(16 * mm, 8 * mm, f"Report {report.report_id}")
        canvas.drawRightString(A4[0] - 16 * mm, 8 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
