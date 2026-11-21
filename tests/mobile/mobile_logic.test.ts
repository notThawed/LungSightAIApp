import assert from "node:assert/strict";
import { test } from "node:test";

import {
  formatManilaTime, formatTimeOfDay, manilaDate, manilaDayRange, manilaYearMonth, monthLabel, shiftMonth,
} from "../../mobile_app/src/lib/time.ts";
import {
  isActiveAppointment, patientName, sortAppointments, toAppointment, toExamination,
} from "../../mobile_app/src/lib/today.ts";
import {
  buildIncidenceRows, classifyRelativeIncidence, fetchPopulation, clearPopulationCache, markerSize, parsePopulation, psgcDigits,
} from "../../mobile_app/src/lib/incidence.ts";

// ------------------------------------------------------------------ time

test("Manila date flips at 16:00 UTC", () => {
  assert.equal(manilaDate(new Date("2026-11-21T15:59:59Z")), "2026-11-21");
  assert.equal(manilaDate(new Date("2026-11-21T16:00:00Z")), "2026-11-22");
});

test("a Manila day maps to the right UTC range", () => {
  assert.deepEqual(manilaDayRange("2026-11-22"), {
    start: "2026-11-21T16:00:00.000Z",
    end: "2026-11-22T16:00:00.000Z",
  });
});

test("month helpers", () => {
  assert.deepEqual(manilaYearMonth(new Date("2026-12-31T17:00:00Z")), { year: 2027, month: 1 });
  assert.deepEqual(shiftMonth(2026, 1, -1), { year: 2025, month: 12 });
  assert.deepEqual(shiftMonth(2026, 11, -5), { year: 2026, month: 6 });
  assert.equal(monthLabel(2026, 11), "November 2026");
  assert.equal(monthLabel(2026, 11, true), "Nov 2026");
});

test("time formatting", () => {
  assert.equal(formatManilaTime("2026-11-22T00:30:00Z"), "8:30 AM");
  assert.equal(formatManilaTime("2026-11-22T05:05:00+00:00"), "1:05 PM");
  assert.equal(formatManilaTime(null), "—");
  assert.equal(formatTimeOfDay("14:30:00"), "2:30 PM");
  assert.equal(formatTimeOfDay("00:15"), "12:15 AM");
  assert.equal(formatTimeOfDay(null), "No time set");
  assert.equal(formatTimeOfDay("99:00"), "No time set");
});

// ------------------------------------------------------------------ today lists

test("appointments map, sort by time and keep untimed last", () => {
  const rows = [
    { follow_up_id: 1, follow_up_time: null, status: "Scheduled", follow_up_code: "FU-1", patients: { first_name: "Ana", last_name: "Cruz", patient_code: "P-1" } },
    { follow_up_id: 2, follow_up_time: "09:00:00", status: "Arrived", patients: [{ first_name: "Ben", last_name: "Diaz" }] },
    { follow_up_id: 3, follow_up_time: "08:30:00", status: "Rescheduled", patients: null },
  ].map(toAppointment);

  const sorted = sortAppointments(rows);
  assert.deepEqual(sorted.map((a) => a.id), ["3", "2", "1"]);
  assert.equal(sorted[2].patientName, "Ana Cruz");
  assert.equal(sorted[2].code, "FU-1");
  assert.equal(sorted[0].patientName, "Unnamed patient");
});

test("only Scheduled and Rescheduled count as upcoming (same as Streamlit)", () => {
  assert.ok(isActiveAppointment("Scheduled"));
  assert.ok(isActiveAppointment("Rescheduled"));
  for (const status of ["Arrived", "Completed", "Cancelled", "Missed", null]) {
    assert.ok(!isActiveAppointment(status), String(status));
  }
});

test("examinations use time_in, then created_at", () => {
  const exam = toExamination({
    examination_id: "e1", time_in: null, created_at: "2026-11-22T01:00:00Z", status: "Pending",
    examination_type: "General Consult", patients: { first_name: "Ana", patient_code: "P-9" },
  });
  assert.equal(exam.time, "2026-11-22T01:00:00Z");
  assert.equal(exam.patientName, "Ana");
  assert.equal(patientName({}), "Unnamed patient");
});

// ------------------------------------------------------------------ incidence

test("population parsing matches get_barangay_population()", () => {
  assert.deepEqual(parsePopulation("0702250003", { data: { code: "0702250003", level: "barangay", population: "14,545", name: "X" } }),
    { code: "0702250003", population: 14545, name: "X" });
  assert.equal(parsePopulation("0702250003", { data: { code: "0702250003", level: "barangay", population: 0 } }), null);
  assert.throws(() => parsePopulation("0702250003", { data: { code: "0702250003", level: "city", population: 5 } }));
  assert.throws(() => parsePopulation("0702250003", { data: { code: "0702250099", level: "barangay", population: 5 } }));
  assert.throws(() => parsePopulation("0702250003", { nope: true }));
  assert.equal(psgcDigits("legacy:cebu|cebu|mabolo"), null);
  assert.equal(psgcDigits("072217001"), "072217001");
});

test("population fetch: 404 is unknown, server errors are not cached", async () => {
  clearPopulationCache();
  let calls = 0;
  const notFound = async () => { calls++; return { status: 404, ok: false, json: async () => ({}) }; };
  assert.equal(await fetchPopulation("0702250001", notFound), null);
  assert.equal(await fetchPopulation("0702250001", notFound), null);
  assert.equal(calls, 1, "404 cached");

  const broken = async () => ({ status: 503, ok: false, json: async () => ({}) });
  await assert.rejects(fetchPopulation("0702250002", broken));
  const ok = async () => ({ status: 200, ok: true, json: async () => ({ data: { code: "0702250002", level: "barangay", population: 1000 } }) });
  assert.equal((await fetchPopulation("0702250002", ok))?.population, 1000, "a failure was not cached");
  assert.equal(await fetchPopulation("legacy:x", ok), null, "legacy keys never call the API");
});

test("relative incidence bands", () => {
  assert.deepEqual(classifyRelativeIncidence(0, null, 10), { level: "Unavailable", ratio: null });
  assert.deepEqual(classifyRelativeIncidence(0, 0, 10), { level: "No cases", ratio: 0 });
  assert.equal(classifyRelativeIncidence(2, 8, 10).level, "Low");
  assert.equal(classifyRelativeIncidence(2, 10, 10).level, "Moderate");
  assert.equal(classifyRelativeIncidence(2, 17.6, 10).level, "High");
  assert.deepEqual(classifyRelativeIncidence(2, 5, 0), { level: "Unavailable", ratio: null });
});

test("marker size stays within 6..21 px", () => {
  assert.equal(markerSize(null, 100), 6);
  assert.equal(markerSize(100, 100), 21);
  assert.equal(markerSize(500, 100), 21);
});

test("pooled reference and duplicate canonical codes", () => {
  const current = [
    { barangay_key: "0700000001", province: "P", city: "C", barangay: "A", latitude: 1, longitude: 1, cases: 2 },
    { barangay_key: "070000001", province: "P", city: "C", barangay: "A-old", latitude: null, longitude: null, cases: 1 },
    { barangay_key: "legacy:p|c|z", province: "P", city: "C", barangay: "Z", latitude: null, longitude: null, cases: 4 },
  ];
  const pops = {
    "0700000001": { code: "0700000001", population: 10_000, name: "A" },
    "070000001": { code: "0700000001", population: 10_000, name: "A" }, // same canonical barangay
  };
  const summary = buildIncidenceRows(current, { "0700000001": 1 }, pops);
  assert.equal(summary.coveredBarangays, 1);
  assert.equal(summary.unavailableBarangays, 2);
  assert.equal(summary.reference, 20);           // 2 cases / 10,000 * 100k
  const a = summary.rows.find((r) => r.key === "0700000001")!;
  assert.equal(a.incidence, 20);
  assert.equal(a.changePercent, 100);
  assert.equal(summary.rows.find((r) => r.key === "070000001")!.level, "Unavailable");
  assert.equal(summary.rows.at(-1)!.incidence, null, "rows without incidence sort last");
});
