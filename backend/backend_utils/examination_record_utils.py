"""Shared clinical archive eligibility for all LungSight patient-record portals."""

FINALIZED_EXAMINATION_STATUSES = frozenset({"completed", "admitted", "discharged"})


def is_finalized_examination_record(exam):
    """A finalized consultation/follow-up; exclude inpatient round entries."""
    status = str(exam.get("status") or "").strip().lower()
    exam_type = str(exam.get("examination_type") or "").strip().lower()
    return status in FINALIZED_EXAMINATION_STATUSES and exam_type != "inpatient round"


def finalized_examination_records(examinations):
    return [e for e in (examinations or []) if is_finalized_examination_record(e)]
