// Dashboard data for the mobile app. Reads run with the signed-in user's
// session, so the database only returns the user's own hospital
// (migration 20261122000000_mobile_hospital_scope). The explicit hospital
// filters below are an extra guard, not the isolation boundary.
//
// Definitions match the Streamlit dashboards:
//   * Today's examinations: registered today (Asia/Manila), excluding
//     inpatient ward rounds.
//   * Today's appointments: follow-ups dated today; "upcoming" counts
//     Scheduled + Rescheduled, like the Streamlit "Follow-ups today" card.
//   * Pending / Awaiting X-Ray / X-Ray Ready: current examination status.

import { supabase } from "./supabase";
import { manilaDate, manilaDayRange } from "./time";
import {
  isActiveAppointment,
  sortAppointments,
  toAppointment,
  toExamination,
} from "./today";
import type { TodayAppointment, TodayExamination } from "./today";

export { isActiveAppointment };
export type { TodayAppointment, TodayExamination };

export type MobileRole = "staff" | "radiologist" | "radiologic_technologist";

export const EXCLUDED_EXAM_TYPE = "Inpatient Round";

export type StatCard = { key: string; label: string; value: number; hint: string; icon: string };

export type DashboardData = {
  day: string;
  stats: StatCard[];
  examinations: TodayExamination[];
  appointments: TodayAppointment[];
};

function fail(what: string, error: { message?: string } | null): never {
  throw new Error(`Could not load ${what}${error?.message ? `: ${error.message}` : ""}`);
}

export async function fetchTodayExaminations(hospitalId: string, now: Date = new Date()): Promise<TodayExamination[]> {
  const { start, end } = manilaDayRange(manilaDate(now));
  const { data, error } = await supabase
    .from("examinations")
    .select("examination_id, examination_type, status, time_in, created_at, patients!inner(first_name, last_name, patient_code, hospital_id)")
    .eq("patients.hospital_id", hospitalId)
    .gte("created_at", start)
    .lt("created_at", end)
    .or(`examination_type.is.null,examination_type.neq."${EXCLUDED_EXAM_TYPE}"`)
    .order("created_at", { ascending: true });

  if (error) fail("today's examinations", error);
  return (data ?? []).map(toExamination);
}

export async function fetchTodayAppointments(hospitalId: string, now: Date = new Date()): Promise<TodayAppointment[]> {
  const { data, error } = await supabase
    .from("follow_ups")
    .select("follow_up_id, follow_up_date, follow_up_time, follow_up_code, status, patients!inner(first_name, last_name, patient_code, hospital_id)")
    .eq("patients.hospital_id", hospitalId)
    .eq("follow_up_date", manilaDate(now));

  if (error) fail("today's appointments", error);
  return sortAppointments((data ?? []).map(toAppointment));
}

async function countExaminations(hospitalId: string, status: string): Promise<number> {
  const { count, error } = await supabase
    .from("examinations")
    .select("examination_id, patients!inner(hospital_id)", { count: "exact", head: true })
    .eq("patients.hospital_id", hospitalId)
    .eq("status", status);

  if (error) fail(`${status} examinations`, error);
  return count ?? 0;
}

async function countPatientsRegisteredToday(hospitalId: string, now: Date): Promise<number> {
  const { start, end } = manilaDayRange(manilaDate(now));
  const { count, error } = await supabase
    .from("patients")
    .select("patient_id", { count: "exact", head: true })
    .eq("hospital_id", hospitalId)
    .gte("created_at", start)
    .lt("created_at", end);

  if (error) fail("registered patients", error);
  return count ?? 0;
}

export async function loadDashboardData(role: MobileRole, hospitalId: string, now: Date = new Date()): Promise<DashboardData> {
  const [examinations, appointments] = await Promise.all([
    fetchTodayExaminations(hospitalId, now),
    fetchTodayAppointments(hospitalId, now),
  ]);

  const upcoming = appointments.filter((a) => isActiveAppointment(a.status)).length;
  const todayExams: StatCard = {
    key: "today_exams", label: "Today's Examinations", value: examinations.length,
    hint: "Registered today", icon: "calendar-outline",
  };
  const todayAppointments: StatCard = {
    key: "today_appointments", label: "Today's Appointments", value: upcoming,
    hint: `${appointments.length} scheduled today`, icon: "people-outline",
  };

  let stats: StatCard[];

  if (role === "radiologist") {
    const [ready, pending] = await Promise.all([
      countExaminations(hospitalId, "X-Ray Ready"),
      countExaminations(hospitalId, "Pending"),
    ]);
    stats = [
      todayExams,
      todayAppointments,
      { key: "to_review", label: "X-Ray Ready to Review", value: ready, hint: "Awaiting your review", icon: "checkmark-circle-outline" },
      { key: "pending", label: "Pending Examinations", value: pending, hint: "Awaiting physician action", icon: "time-outline" },
    ];
  } else if (role === "radiologic_technologist") {
    const [awaiting, ready] = await Promise.all([
      countExaminations(hospitalId, "Awaiting X-Ray"),
      countExaminations(hospitalId, "X-Ray Ready"),
    ]);
    stats = [
      todayExams,
      todayAppointments,
      { key: "awaiting", label: "Awaiting X-Ray", value: awaiting, hint: "Examinations awaiting imaging", icon: "scan-outline" },
      { key: "ready", label: "X-Ray Ready", value: ready, hint: "Sent for physician review", icon: "checkmark-circle-outline" },
    ];
  } else {
    const [registered, pending] = await Promise.all([
      countPatientsRegisteredToday(hospitalId, now),
      countExaminations(hospitalId, "Pending"),
    ]);
    stats = [
      { key: "registered", label: "Registered Today", value: registered, hint: "New patients today", icon: "person-add-outline" },
      todayExams,
      todayAppointments,
      { key: "pending", label: "Pending Examinations", value: pending, hint: "Awaiting physician action", icon: "time-outline" },
    ];
  }

  return { day: manilaDate(now), stats, examinations, appointments };
}
