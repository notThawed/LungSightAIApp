import pytest

from backend import fetches


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table):
        self.client = client
        self.table_name = table
        self.filters = {}

    def select(self, _columns):
        return self

    def order(self, *_args, **_kwargs):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def in_(self, column, values):
        self.filters[column] = values
        return self

    def execute(self):
        self.client.queries.append((self.table_name, dict(self.filters)))
        rows = self.client.rows.get(self.table_name, [])
        if self.table_name == "patients" and "hospital_id" in self.filters:
            rows = [
                row for row in rows
                if row["hospital_id"] == self.filters["hospital_id"]
            ]
        if self.table_name == "examinations":
            rows = [
                row for row in rows
                if row["patient_id"] in self.filters["patient_id"]
                and row["status"] in self.filters["status"]
            ]
        return FakeResponse(rows)


class FakeSupabase:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def table(self, name):
        return FakeQuery(self, name)


def test_patient_records_include_hospital_patients_without_eligible_exams(monkeypatch):
    patient_a = {
        "patient_id": "patient-a",
        "first_name": "Ari",
        "hospital_id": "hospital-a",
    }
    patient_b = {
        "patient_id": "patient-b",
        "first_name": "Bea",
        "hospital_id": "hospital-a",
    }
    other_hospital_patient = {
        "patient_id": "patient-c",
        "first_name": "Cam",
        "hospital_id": "hospital-b",
    }
    client = FakeSupabase({
        "patients": [patient_a, patient_b, other_hospital_patient],
        "examinations": [{
            "examination_id": "exam-a",
            "patient_id": "patient-a",
            "status": "Completed",
            "examination_date": "2026-10-01",
            "created_at": "2026-10-01",
            "curb65_score": 1,
            "severity_status": "Low Risk",
        }],
        "xray_requests": [],
    })
    monkeypatch.setattr(fetches, "admin_supabase", client)

    rows = fetches.get_completed_patients_with_latest_ai("hospital-a")

    assert [row["patient"]["patient_id"] for row in rows] == [
        "patient-a",
        "patient-b",
    ]
    assert rows[0]["examination_id"] == "exam-a"
    assert rows[0]["severity_status"] == "Low Risk"
    assert rows[1]["examination_id"] is None
    assert rows[1]["examination_date"] is None
    assert rows[1]["ai_findings"] is None
    assert client.queries[0] == (
        "patients",
        {"hospital_id": "hospital-a"},
    )


def test_patient_records_surface_query_failures(monkeypatch):
    class FailedQuery:
        def select(self, _columns):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def execute(self):
            raise OSError("database unavailable")

    class FailedSupabase:
        def table(self, _name):
            return FailedQuery()

    monkeypatch.setattr(fetches, "admin_supabase", FailedSupabase())

    with pytest.raises(RuntimeError, match="Failed to fetch patients"):
        fetches.get_completed_patients_with_latest_ai("hospital-a")
