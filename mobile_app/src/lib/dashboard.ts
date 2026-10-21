/**
 * Role dashboard metrics for the mobile app.
 *
 * Mirrors ROLE_METRICS in backend/backend_utils/dashboard_utils.py so a
 * clinician sees the same numbers on web and mobile. Unlike the web app
 * (server-side service key), these queries run with the signed-in user's
 * session, so Supabase Row Level Security decides which rows are counted.
 */

import { supabase } from "./supabase";
import type { UserRole } from "./user";

type MetricKind =
  | { kind: "exam_status"; status: string }
  | { kind: "followups_today" }
  | { kind: "followup_status"; statuses: string[] };

export type MetricKey =
  | "pending_exams"
  | "xray_ready"
  | "awaiting_xray"
  | "completed_exams"
  | "followups_today"
  | "followups_upcoming"
  | "followups_missed";

type MetricDefinition = {
  key: MetricKey;
  label: string;
  hint: string;
} & MetricKind;

export type DashboardMetric = {
  key: MetricKey;
  label: string;
  hint: string;
  /** null when this metric could not be loaded. */
  value: number | null;
};

const ROLE_METRICS: Partial<Record<UserRole, MetricDefinition[]>> = {
  radiologist: [
    { key: "pending_exams", label: "Pending examinations", hint: "Waiting in your patient queue", kind: "exam_status", status: "Pending" },
    { key: "xray_ready", label: "X-ray results to review", hint: "AI analysis finished", kind: "exam_status", status: "X-Ray Ready" },
    { key: "awaiting_xray", label: "Awaiting X-ray", hint: "Requested, not yet imaged", kind: "exam_status", status: "Awaiting X-Ray" },
    { key: "followups_today", label: "Follow-ups today", hint: "Scheduled for today", kind: "followups_today" },
  ],
  radiologic_technologist: [
    { key: "awaiting_xray", label: "Awaiting X-ray", hint: "In your X-ray queue", kind: "exam_status", status: "Awaiting X-Ray" },
    { key: "xray_ready", label: "Sent for review", hint: "Analyzed, awaiting physician", kind: "exam_status", status: "X-Ray Ready" },
    { key: "pending_exams", label: "Pending examinations", hint: "Not yet requested for X-ray", kind: "exam_status", status: "Pending" },
    { key: "completed_exams", label: "Completed examinations", hint: "Reviewed by a physician", kind: "exam_status", status: "Completed" },
  ],
  staff: [
    { key: "followups_today", label: "Follow-ups today", hint: "Scheduled for today", kind: "followups_today" },
    { key: "followups_upcoming", label: "Upcoming follow-ups", hint: "Scheduled or rescheduled", kind: "followup_status", statuses: ["Scheduled", "Rescheduled"] },
    { key: "followups_missed", label: "Missed follow-ups", hint: "Need rescheduling", kind: "followup_status", statuses: ["Missed"] },
    { key: "pending_exams", label: "Pending examinations", hint: "Registered, awaiting physician", kind: "exam_status", status: "Pending" },
  ],
};

/** Today's date in the hospital timezone (Asia/Manila, UTC+8, no DST). */
export function manilaToday(now: Date = new Date()): string {
  return new Date(now.getTime() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

async function countExaminations(hospitalId: string, status: string) {
  const { count, error } = await supabase
    .from("examinations")
    .select("examination_id, patients!inner(hospital_id)", { count: "exact", head: true })
    .eq("status", status)
    .eq("patients.hospital_id", hospitalId);

  if (error) throw error;
  return count ?? 0;
}

async function countFollowUps(hospitalId: string, statuses: string[], date?: string) {
  let query = supabase
    .from("follow_ups")
    .select("follow_up_id, patients!inner(hospital_id)", { count: "exact", head: true })
    .in("status", statuses)
    .eq("patients.hospital_id", hospitalId);

  if (date) {
    query = query.eq("follow_up_date", date);
  }

  const { count, error } = await query;

  if (error) throw error;
  return count ?? 0;
}

async function loadMetric(definition: MetricDefinition, hospitalId: string): Promise<number> {
  switch (definition.kind) {
    case "exam_status":
      return countExaminations(hospitalId, definition.status);
    case "followups_today":
      return countFollowUps(hospitalId, ["Scheduled", "Rescheduled"], manilaToday());
    case "followup_status":
      return countFollowUps(hospitalId, definition.statuses);
  }
}

export async function getDashboardMetrics(
  role: UserRole,
  hospitalId: string
): Promise<DashboardMetric[]> {
  const definitions = ROLE_METRICS[role] ?? [];

  return Promise.all(
    definitions.map(async (definition) => {
      const { key, label, hint } = definition;

      try {
        return { key, label, hint, value: await loadMetric(definition, hospitalId) };
      } catch (error) {
        console.warn(`Dashboard metric ${key} failed:`, error);
        return { key, label, hint, value: null };
      }
    })
  );
}
