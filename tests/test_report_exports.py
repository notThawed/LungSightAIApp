"""
PDF / Excel exports render exactly the numbers of the report object.
"""

import re
import zipfile
from io import BytesIO
from xml.etree import ElementTree

import pytest

import test_report_calculations as G
from backend.reports import excel as excel_mod
from backend.reports import pdf as pdf_mod
from backend.reports.calculations import ReportInputs


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


# ============================================================
# XLSX READER (no extra dependency)
# ============================================================

def read_xlsx(data):
    book = zipfile.ZipFile(BytesIO(data))

    shared = []
    if "xl/sharedStrings.xml" in book.namelist():
        root = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))

    workbook = ElementTree.fromstring(book.read("xl/workbook.xml"))
    names = [s.get("name") for s in workbook.find("m:sheets", NS)]

    sheets = {}
    formulas = 0
    for index, name in enumerate(names, start=1):
        root = ElementTree.fromstring(book.read(f"xl/worksheets/sheet{index}.xml"))
        rows = []
        for row in root.iter(f"{{{NS['m']}}}row"):
            values = {}
            for cell in row.findall("m:c", NS):
                if cell.find("m:f", NS) is not None:
                    formulas += 1
                column = re.match(r"[A-Z]+", cell.get("r")).group()
                raw = cell.find("m:v", NS)
                if raw is None:
                    continue
                if cell.get("t") == "s":
                    values[column] = shared[int(raw.text)]
                else:
                    number = float(raw.text)
                    values[column] = int(number) if number.is_integer() else number
            rows.append(values)
        sheets[name] = rows

    return names, sheets, formulas


def find_row(rows, first_cell):
    return next(r for r in rows if r.get("A") == first_cell)


# ============================================================
# EXCEL
# ============================================================

def test_excel_summary_matches_report_numbers():
    report = G.build()
    names, sheets, formulas = read_xlsx(excel_mod.render_excel(report))

    assert names == ["Summary", "Examinations", "Clinical Review", "Definitions"]
    assert formulas == 0

    summary = sheets["Summary"]
    for metric in report.metrics:
        row = find_row(summary, metric.label)
        assert row.get("B") == metric.value
        assert row.get("C") == metric.denominator
        assert row.get("D") == metric.pct
        assert row["F"].startswith(metric.display())

    assert find_row(summary, "Report ID")["B"] == report.report_id


def test_excel_patient_sheets_have_minimal_fields_and_no_names():
    report = G.build()
    _names, sheets, _ = read_xlsx(excel_mod.render_excel(report))

    exams = sheets["Examinations"]
    header = exams[0]
    assert list(header.values())[:3] == ["Examination ID", "Patient code", "Registered (Manila)"]
    assert len(exams) - 1 == report.exam_rows_total == 8

    review = sheets["Clinical Review"]
    assert len(review) - 1 == 3   # E1, E2, E3 have a current AI result
    flat = " ".join(str(v) for row in exams + review for v in row.values())
    assert "Right lower lobe opacity" not in flat     # review text never exported


def test_excel_aggregate_only_for_platform_view():
    report = G.build(patient_level=False)
    names, sheets, _ = read_xlsx(excel_mod.render_excel(report))

    assert names == ["Summary", "Definitions"]


def test_excel_neutralises_formula_like_text():
    inputs = G.golden_inputs()
    inputs.exams[0]["patients"] = {"hospital_id": G.HOSP, "patient_code": '=HYPERLINK("http://x","y")'}
    inputs.hospital["hospital_name"] = "@SUM(A1)"
    report = G.build(inputs)

    _names, sheets, formulas = read_xlsx(excel_mod.render_excel(report))

    assert formulas == 0
    codes = [r.get("B") for r in sheets["Examinations"][1:]]
    assert "'=HYPERLINK(\"http://x\",\"y\")" in codes
    assert find_row(sheets["Summary"], "Hospital")["B"] == "'@SUM(A1)"


@pytest.mark.parametrize("value,expected", [
    ("=1+1", "'=1+1"), ("+1", "'+1"), ("-1", "'-1"), ("@x", "'@x"),
    ("\tx", "'\tx"), ("plain", "plain"), (None, ""), ("a=b", "a=b"),
])
def test_safe_text(value, expected):
    assert excel_mod.safe_text(value) == expected


def test_excel_capped_notice(monkeypatch):
    monkeypatch.setattr(G.calc, "PATIENT_ROW_CAP", 2)
    report = G.build()
    _names, sheets, _ = read_xlsx(excel_mod.render_excel(report))

    assert sheets["Examinations"][0]["A"].startswith("Only the first 2 of 8 examinations")


# ============================================================
# PDF
# ============================================================

def captured_pdf_text(report, monkeypatch):
    seen = []
    original = pdf_mod._p

    def spy(text, style):
        seen.append(str(text))
        return original(text, style)

    monkeypatch.setattr(pdf_mod, "_p", spy)
    data = pdf_mod.render_pdf(report)
    return data, seen


def test_pdf_prints_the_same_numbers_as_the_screen(monkeypatch):
    report = G.build()
    data, seen = captured_pdf_text(report, monkeypatch)

    assert data.startswith(b"%PDF-")
    for metric in report.metrics:
        assert metric.label in seen
        assert metric.display() in seen
    for breakdown in report.breakdowns:
        for label, count in breakdown.items:
            assert label in seen and f"{count:,}" in seen
    assert report.report_id in seen
    assert any("not a diagnosis" in text for text in seen)
    assert report.report_b_status in seen


def test_pdf_has_no_patient_level_rows(monkeypatch):
    report = G.build()
    _data, seen = captured_pdf_text(report, monkeypatch)

    assert not any(text.startswith("PAT-") for text in seen)
    assert not any(row.examination_id in seen for row in report.exam_rows)


def test_pdf_empty_period(monkeypatch):
    report = G.build(ReportInputs(hospital={"hospital_id": G.HOSP, "hospital_name": "Empty"}, exams=[]))
    data, seen = captured_pdf_text(report, monkeypatch)

    assert data.startswith(b"%PDF-")
    assert any("No examinations were registered" in text for text in seen)
    assert "Not available" in seen
