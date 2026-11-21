// Asia/Manila date helpers. The Philippines has no daylight saving, so a
// fixed UTC+08:00 offset matches the Streamlit app's PH_TIME / MANILA rules.

const MANILA_OFFSET_MS = 8 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

/** Today's calendar date in Manila, as YYYY-MM-DD. */
export function manilaDate(now: Date = new Date()): string {
  return new Date(now.getTime() + MANILA_OFFSET_MS).toISOString().slice(0, 10);
}

/** UTC instants for a Manila calendar day: [start, end). */
export function manilaDayRange(day: string): { start: string; end: string } {
  const start = new Date(`${day}T00:00:00+08:00`);
  return {
    start: start.toISOString(),
    end: new Date(start.getTime() + DAY_MS).toISOString(),
  };
}

export function manilaYearMonth(now: Date = new Date()): { year: number; month: number } {
  const [year, month] = manilaDate(now).split("-").map(Number);
  return { year, month };
}

export function shiftMonth(year: number, month: number, delta: number): { year: number; month: number } {
  const index = year * 12 + (month - 1) + delta;
  return { year: Math.floor(index / 12), month: (index % 12) + 1 };
}

export function monthLabel(year: number, month: number, short = false): string {
  const name = MONTHS[month - 1] ?? "";
  return `${short ? name.slice(0, 3) : name} ${year}`;
}

function clock(hours: number, minutes: number): string {
  const suffix = hours >= 12 ? "PM" : "AM";
  const h = hours % 12 === 0 ? 12 : hours % 12;
  return `${h}:${String(minutes).padStart(2, "0")} ${suffix}`;
}

/** "2026-11-22T00:30:00Z" -> "8:30 AM" (Manila). */
export function formatManilaTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  const manila = new Date(date.getTime() + MANILA_OFFSET_MS);
  return clock(manila.getUTCHours(), manila.getUTCMinutes());
}

/** Postgres time "14:30:00" -> "2:30 PM". */
export function formatTimeOfDay(value: string | null | undefined): string {
  const match = /^(\d{1,2}):(\d{2})/.exec(String(value ?? ""));
  if (!match) return "No time set";
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) return "No time set";
  return clock(hours, minutes);
}
