// Barangay incidence calculation for the mobile geospatial screen.
//
// A direct port of backend/geospatial_backend/incidence_population.py
// (get_barangay_population, classify_relative_incidence,
// build_incidence_rows) so the phone shows the same numbers as Streamlit.
// Case counts come from public.hospital_barangay_cases (counts only); the
// population comes from the same public PSGC API. No patient data is sent
// to that API, only barangay PSGC codes.

export const PSGC_POPULATION_API = "https://psgc.billyjamesramos.com/api/v1";
export const CENSUS_YEAR = 2024;
export const LOW_UPPER = 0.85;
export const MODERATE_UPPER = 1.76;

export type IncidenceLevel = "High" | "Moderate" | "Low" | "No cases" | "Unavailable";

export const LEVEL_COLORS: Record<IncidenceLevel, string> = {
  High: "#ef4444",
  Moderate: "#f59e0b",
  Low: "#22c55e",
  "No cases": "#94a3b8",
  Unavailable: "#64748b",
};

export type BarangayCount = {
  barangay_key: string;
  province: string;
  city: string;
  barangay: string;
  latitude: number | null;
  longitude: number | null;
  cases: number;
};

export type Population = { code: string; population: number; name: string };

export type IncidenceRow = {
  key: string;
  label: string;
  cases: number;
  previous: number;
  population: number | null;
  incidence: number | null;
  ratio: number | null;
  level: IncidenceLevel;
  changePercent: number | null;
  latitude: number | null;
  longitude: number | null;
};

export type IncidenceSummary = {
  rows: IncidenceRow[];
  reference: number | null;
  coveredBarangays: number;
  unavailableBarangays: number;
};

export function psgcDigits(value: unknown): string | null {
  const code = String(value ?? "").trim();
  return /^\d{9,10}$/.test(code) ? code : null;
}

/** Parse one API response the way get_barangay_population() does. */
export function parsePopulation(requested: string, payload: unknown): Population | null {
  if (!payload || typeof payload !== "object" || typeof (payload as any).data !== "object" || !(payload as any).data) {
    throw new Error("Unexpected barangay population API response");
  }
  const item = (payload as any).data;
  const resolved = String(item.code ?? "").trim();
  if (item.level !== "barangay" || !/^\d{10}$/.test(resolved)) {
    throw new Error("PSGC code resolved to a non-barangay location");
  }
  if (requested !== resolved && requested.length === 10) {
    throw new Error("API returned a different barangay PSGC code");
  }
  const population = Number.parseInt(String(item.population ?? "").replace(/,/g, ""), 10);
  if (!Number.isFinite(population)) throw new Error("API returned an invalid census population");
  if (population <= 0) return null;
  return { code: resolved, population, name: String(item.name ?? "") };
}

type FetchLike = (url: string, init?: Record<string, unknown>) => Promise<{ status: number; ok: boolean; json(): Promise<unknown> }>;

const populationCache = new Map<string, Population | null>();

/** Population for one barangay code; null when unknown. Errors propagate (not cached). */
export async function fetchPopulation(code: string, fetchImpl: FetchLike = fetch as unknown as FetchLike): Promise<Population | null> {
  const digits = psgcDigits(code);
  if (!digits) return null;
  if (populationCache.has(digits)) return populationCache.get(digits) ?? null;

  const response = await fetchImpl(`${PSGC_POPULATION_API}/codes/${digits}`, { headers: { Accept: "application/json" } });
  if (response.status === 404) {
    populationCache.set(digits, null);
    return null;
  }
  if (!response.ok) throw new Error(`Population API returned HTTP ${response.status}`);

  const result = parsePopulation(digits, await response.json());
  populationCache.set(digits, result);
  return result;
}

export function clearPopulationCache(): void {
  populationCache.clear();
}

export function classifyRelativeIncidence(
  cases: number,
  incidence: number | null,
  reference: number | null,
): { level: IncidenceLevel; ratio: number | null } {
  if (incidence === null) return { level: "Unavailable", ratio: null };
  if (cases === 0) return { level: "No cases", ratio: reference && reference > 0 ? 0 : null };
  if (reference === null || reference <= 0) return { level: "Unavailable", ratio: null };
  const ratio = incidence / reference;
  if (ratio < LOW_UPPER) return { level: "Low", ratio };
  if (ratio < MODERATE_UPPER) return { level: "Moderate", ratio };
  return { level: "High", ratio };
}

const round = (value: number, digits: number) => Math.round(value * 10 ** digits) / 10 ** digits;

export function barangayLabel(row: Pick<BarangayCount, "barangay" | "city" | "province">): string {
  return `${row.barangay ?? ""} — ${row.city ?? ""}, ${row.province ?? ""}`;
}

/**
 * Same as build_incidence_rows(): the reference is pooled (total cases over
 * total covered population), not the mean of barangay rates, and a canonical
 * PSGC code is only counted once.
 */
export function buildIncidenceRows(
  current: BarangayCount[],
  previous: Record<string, number>,
  populations: Record<string, Population | null>,
): IncidenceSummary {
  const good = new Map<string, Population>();
  const seen = new Set<string>();
  for (const row of current) {
    const pop = populations[row.barangay_key];
    if (!pop) continue;
    if (seen.has(pop.code)) continue;
    seen.add(pop.code);
    good.set(row.barangay_key, pop);
  }

  let totalPopulation = 0;
  let countedCases = 0;
  for (const row of current) {
    const pop = good.get(row.barangay_key);
    if (!pop) continue;
    totalPopulation += pop.population;
    countedCases += row.cases;
  }
  const reference = totalPopulation ? (countedCases / totalPopulation) * 100_000 : null;

  const rows: IncidenceRow[] = current.map((row) => {
    const pop = good.get(row.barangay_key)?.population ?? null;
    const incidence = pop ? (row.cases / pop) * 100_000 : null;
    const { level, ratio } = classifyRelativeIncidence(row.cases, incidence, reference);
    const prior = previous[row.barangay_key] ?? 0;
    return {
      key: row.barangay_key,
      label: barangayLabel(row),
      cases: row.cases,
      previous: prior,
      population: pop,
      incidence: incidence === null ? null : round(incidence, 2),
      ratio: ratio === null ? null : round(ratio, 3),
      level,
      changePercent: prior ? round(((row.cases - prior) * 100) / prior, 1) : null,
      latitude: row.latitude,
      longitude: row.longitude,
    };
  });

  rows.sort((a, b) => {
    if ((a.incidence === null) !== (b.incidence === null)) return a.incidence === null ? 1 : -1;
    const diff = (b.incidence ?? 0) - (a.incidence ?? 0);
    return diff !== 0 ? diff : a.label.localeCompare(b.label);
  });

  return {
    rows,
    reference,
    coveredBarangays: good.size,
    unavailableBarangays: current.length - good.size,
  };
}

/** Marker radius in px: 6..21, scaled like the Streamlit CircleMarker. */
export function markerSize(incidence: number | null, maxIncidence: number): number {
  return 6 + Math.min(15, ((incidence ?? 0) / Math.max(1, maxIncidence)) * 15);
}
