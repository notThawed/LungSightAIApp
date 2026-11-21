// Pure helpers for the dashboard's "today" lists (no Supabase imports, so
// they can be unit-tested outside the app).

export const ACTIVE_APPOINTMENT_STATUSES = ["Scheduled", "Rescheduled"];

export type TodayExamination = {
  id: string;
  time: string | null;
  patientName: string;
  patientCode: string | null;
  type: string;
  status: string;
};

export type TodayAppointment = {
  id: string;
  time: string | null;
  patientName: string;
  patientCode: string | null;
  code: string | null;
  status: string;
};

type PatientEmbed = { first_name?: string | null; last_name?: string | null; patient_code?: string | null };

function embedded(value: PatientEmbed | PatientEmbed[] | null | undefined): PatientEmbed {
  if (Array.isArray(value)) return value[0] ?? {};
  return value ?? {};
}

export function patientName(patient: PatientEmbed): string {
  const name = [patient.first_name, patient.last_name].filter(Boolean).join(" ").trim();
  return name || "Unnamed patient";
}

export function isActiveAppointment(status: string | null | undefined): boolean {
  return ACTIVE_APPOINTMENT_STATUSES.includes(String(status ?? ""));
}

export function toExamination(row: any): TodayExamination {
  const patient = embedded(row.patients);
  return {
    id: String(row.examination_id),
    time: row.time_in ?? row.created_at ?? null,
    patientName: patientName(patient),
    patientCode: patient.patient_code ?? null,
    type: row.examination_type ?? "Examination",
    status: row.status ?? "Unknown",
  };
}

export function toAppointment(row: any): TodayAppointment {
  const patient = embedded(row.patients);
  return {
    id: String(row.follow_up_id),
    time: row.follow_up_time ?? null,
    patientName: patientName(patient),
    patientCode: patient.patient_code ?? null,
    code: row.follow_up_code ?? null,
    status: row.status ?? "Unknown",
  };
}

/** Appointments by time; those without a time go last. */
export function sortAppointments(rows: TodayAppointment[]): TodayAppointment[] {
  return [...rows].sort((a, b) => {
    if (a.time === b.time) return a.patientName.localeCompare(b.patientName);
    if (!a.time) return 1;
    if (!b.time) return -1;
    return a.time.localeCompare(b.time);
  });
}
