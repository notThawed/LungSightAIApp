import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import MapView, { Callout, Marker } from "react-native-maps";
import Ionicons from "@expo/vector-icons/Ionicons";

import { supabase } from "../lib/supabase";
import { getCurrentUserProfile } from "../lib/user";
import {
  buildIncidenceRows,
  fetchPopulation,
  LEVEL_COLORS,
  markerSize,
  psgcDigits,
} from "../lib/incidence";
import type { BarangayCount, IncidenceRow, IncidenceSummary, Population } from "../lib/incidence";
import { manilaYearMonth, monthLabel, shiftMonth } from "../lib/time";

type GeospatialProps = { role?: string };

type Hospital = { name: string; latitude: number | null; longitude: number | null };

type MonthKey = { year: number; month: number };

type TrendPoint = { label: string; cases: number };

const DEFAULT_REGION = {
  latitude: 10.3157,
  longitude: 123.8854,
  latitudeDelta: 0.3,
  longitudeDelta: 0.3,
};

const LEGEND: { label: string; color: string }[] = [
  { label: "Low", color: LEVEL_COLORS.Low },
  { label: "Moderate", color: LEVEL_COLORS.Moderate },
  { label: "High", color: LEVEL_COLORS.High },
  { label: "No cases", color: LEVEL_COLORS["No cases"] },
  { label: "Population unavailable", color: LEVEL_COLORS.Unavailable },
];

async function loadCounts(year: number, month: number): Promise<BarangayCount[]> {
  const { data, error } = await supabase.rpc("hospital_barangay_cases", { p_year: year, p_month: month });
  if (error) throw new Error(error.message);
  return ((data ?? []) as any[]).map((row) => ({
    barangay_key: String(row.barangay_key),
    province: row.province ?? "",
    city: row.city ?? "",
    barangay: row.barangay ?? "",
    latitude: row.latitude === null || row.latitude === undefined ? null : Number(row.latitude),
    longitude: row.longitude === null || row.longitude === undefined ? null : Number(row.longitude),
    cases: Number(row.cases) || 0,
  }));
}

function hasCoordinates(row: { latitude: number | null; longitude: number | null }): boolean {
  return (
    row.latitude !== null && row.longitude !== null &&
    Number.isFinite(row.latitude) && Number.isFinite(row.longitude) &&
    Math.abs(row.latitude) <= 90 && Math.abs(row.longitude) <= 180
  );
}

function formatNumber(value: number | null, digits = 2): string {
  if (value === null) return "Unavailable";
  return value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function Geospatial(_props: GeospatialProps) {
  const mapRef = useRef<MapView | null>(null);
  const now = manilaYearMonth();
  const monthOptions = useMemo<MonthKey[]>(
    () => Array.from({ length: 12 }, (_, i) => shiftMonth(now.year, now.month, -i)),
    [now.year, now.month],
  );

  const [selectedMonth, setSelectedMonth] = useState<MonthKey>(monthOptions[0]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [hospital, setHospital] = useState<Hospital | null>(null);
  const [summary, setSummary] = useState<IncidenceSummary | null>(null);
  const [catalogSize, setCatalogSize] = useState(0);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [populationProblems, setPopulationProblems] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError("");

    try {
      const profile = await getCurrentUserProfile();
      if (!profile.hospitalId) {
        throw new Error("Your account is not assigned to a hospital.");
      }

      const { data: hospitalRow } = await supabase
        .from("hospitals")
        .select("hospital_name, latitude, longitude")
        .eq("hospital_id", profile.hospitalId)
        .maybeSingle();

      setHospital({
        name: hospitalRow?.hospital_name ?? profile.hospitalName ?? "Your hospital",
        latitude: hospitalRow?.latitude === null || hospitalRow?.latitude === undefined ? null : Number(hospitalRow.latitude),
        longitude: hospitalRow?.longitude === null || hospitalRow?.longitude === undefined ? null : Number(hospitalRow.longitude),
      });

      // Six months ending with the selected one: the last two are the
      // current and previous month used for the summary.
      const months = Array.from({ length: 6 }, (_, i) => shiftMonth(selectedMonth.year, selectedMonth.month, i - 5));
      const counts = await Promise.all(months.map((m) => loadCounts(m.year, m.month)));
      const current = counts[5];
      const previous = Object.fromEntries(counts[4].map((row) => [row.barangay_key, row.cases]));

      const codes = current.map((row) => row.barangay_key).filter((key) => psgcDigits(key));
      const results = await Promise.allSettled(codes.map((code) => fetchPopulation(code)));
      const populations: Record<string, Population | null> = {};
      let problems = 0;
      results.forEach((result, index) => {
        if (result.status === "fulfilled") {
          populations[codes[index]] = result.value;
        } else {
          populations[codes[index]] = null;
          problems += 1;
        }
      });

      setCatalogSize(current.length);
      setPopulationProblems(problems);
      setSummary(buildIncidenceRows(current, previous, populations));
      setTrend(months.map((m, i) => ({
        label: monthLabel(m.year, m.month, true),
        cases: counts[i].reduce((sum, row) => sum + row.cases, 0),
      })));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load geospatial data.");
      setSummary(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedMonth]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = summary?.rows ?? [];
  const mapped = rows.filter(hasCoordinates);
  const missingCoordinates = rows.filter((r) => r.cases > 0 && !hasCoordinates(r)).length;
  const maxIncidence = Math.max(0, ...rows.map((r) => r.incidence ?? 0));
  const totalCases = rows.reduce((sum, r) => sum + r.cases, 0);
  const previousTotal = rows.reduce((sum, r) => sum + r.previous, 0);
  const withCases = rows.filter((r) => r.cases > 0).length;
  const highest = rows.find((r) => (r.incidence ?? 0) > 0)?.label ?? "—";
  const change = previousTotal
    ? `${((totalCases - previousTotal) / previousTotal) * 100 >= 0 ? "+" : ""}${(((totalCases - previousTotal) / previousTotal) * 100).toFixed(1)}%`
    : "N/A";
  const maxTrend = Math.max(1, ...trend.map((t) => t.cases));

  useEffect(() => {
    const points = mapped.map((r) => ({ latitude: r.latitude as number, longitude: r.longitude as number }));
    if (hospital && hasCoordinates(hospital)) {
      points.push({ latitude: hospital.latitude as number, longitude: hospital.longitude as number });
    }
    if (points.length > 0 && mapRef.current) {
      setTimeout(() => {
        mapRef.current?.fitToCoordinates(points, {
          edgePadding: { top: 60, right: 60, bottom: 60, left: 60 },
          animated: true,
        });
      }, 300);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary, hospital]);

  function focus(row: IncidenceRow) {
    setSelected(row.key);
    if (hasCoordinates(row)) {
      mapRef.current?.animateToRegion({
        latitude: row.latitude as number,
        longitude: row.longitude as number,
        latitudeDelta: 0.04,
        longitudeDelta: 0.04,
      });
    }
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={styles.muted}>Loading geospatial data...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} colors={["#2563eb"]} />}
    >
      <Text style={styles.eyebrow}>ANALYTICS & MONITORING</Text>
      <Text style={styles.title}>Geospatial Case Monitoring</Text>
      <Text style={styles.subtitle}>
        First-recorded clinician-confirmed pneumonia patients by barangay, adjusted for PSA 2024 population.
      </Text>
      {hospital ? (
        <View style={styles.hospitalRow}>
          <Ionicons name="business-outline" size={15} color="#64748b" />
          <Text style={styles.muted}>{hospital.name}</Text>
        </View>
      ) : null}

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.monthBar}>
        {monthOptions.map((m) => {
          const active = m.year === selectedMonth.year && m.month === selectedMonth.month;
          return (
            <TouchableOpacity
              key={`${m.year}-${m.month}`}
              style={[styles.monthChip, active && styles.monthChipActive]}
              onPress={() => { setSelected(null); setSelectedMonth(m); }}
            >
              <Text style={[styles.monthText, active && styles.monthTextActive]}>{monthLabel(m.year, m.month, true)}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {error ? (
        <View style={styles.warning}>
          <Ionicons name="warning-outline" size={18} color="#b45309" />
          <Text style={styles.warningText}>{error}</Text>
        </View>
      ) : catalogSize === 0 ? (
        <View style={styles.emptyCard}>
          <Text style={styles.muted}>No patient records with barangay addresses exist for this hospital yet.</Text>
        </View>
      ) : (
        <>
          <View style={styles.kpiGrid}>
            <Kpi label="Recorded cases" value={String(totalCases)} />
            <Kpi label="Barangays with cases" value={`${withCases} / ${rows.length}`} />
            <Kpi label="Highest-incidence barangay" value={highest} small />
            <Kpi label="Month-over-month change" value={change} />
          </View>

          <Text style={styles.caption}>
            Study-area reference: {summary?.reference !== null && summary?.reference !== undefined ? formatNumber(summary.reference) : "Unavailable"} first-recorded cases per 100,000
            (population-weighted across {summary?.coveredBarangays ?? 0} mapped patient barangays; PSA-derived 2024 population).
          </Text>

          {summary && summary.unavailableBarangays > 0 ? (
            <View style={styles.warning}>
              <Ionicons name="information-circle-outline" size={18} color="#b45309" />
              <Text style={styles.warningText}>
                {summary.unavailableBarangays} barangay(s) have no verified population match{populationProblems ? " or the population service could not be reached" : ""}; incidence is unavailable there.
              </Text>
            </View>
          ) : null}

          <View style={styles.mapCard}>
            <MapView ref={mapRef} style={styles.map} initialRegion={DEFAULT_REGION}>
              {mapped.map((row) => {
                const size = markerSize(row.incidence, maxIncidence);
                const isSelected = row.key === selected;
                return (
                  <Marker
                    key={row.key}
                    coordinate={{ latitude: row.latitude as number, longitude: row.longitude as number }}
                    tracksViewChanges={false}
                    onPress={() => setSelected(row.key)}
                  >
                    <View
                      style={[
                        styles.dot,
                        {
                          width: size * 2,
                          height: size * 2,
                          borderRadius: size,
                          backgroundColor: LEVEL_COLORS[row.level],
                          borderWidth: isSelected ? 3 : 1,
                        },
                      ]}
                    />
                    <Callout>
                      <View style={styles.callout}>
                        <Text style={styles.calloutTitle}>{row.label}</Text>
                        <Text style={styles.calloutText}>Newly recorded cases: {row.cases}</Text>
                        <Text style={styles.calloutText}>Incidence / 100k: {formatNumber(row.incidence)}</Text>
                        <Text style={styles.calloutText}>Relative incidence: {row.level}</Text>
                      </View>
                    </Callout>
                  </Marker>
                );
              })}
              {hospital && hasCoordinates(hospital) ? (
                <Marker
                  coordinate={{ latitude: hospital.latitude as number, longitude: hospital.longitude as number }}
                  title="Your hospital"
                  description={hospital.name}
                  pinColor="#2563eb"
                />
              ) : null}
            </MapView>
          </View>

          <View style={styles.legend}>
            {LEGEND.map((item) => (
              <View key={item.label} style={styles.legendItem}>
                <View style={[styles.legendDot, { backgroundColor: item.color }]} />
                <Text style={styles.legendText}>{item.label}</Text>
              </View>
            ))}
          </View>
          <Text style={styles.caption}>
            Markers are barangay centroids, not patient homes. Colours show relative hospital-recorded incidence, not clinical severity.
          </Text>

          {missingCoordinates > 0 ? (
            <View style={styles.warning}>
              <Ionicons name="location-outline" size={18} color="#b45309" />
              <Text style={styles.warningText}>
                {missingCoordinates} barangay group(s) have recorded cases but no verified coordinates. They are listed below but cannot be plotted yet.
              </Text>
            </View>
          ) : null}

          <Text style={styles.sectionTitle}>Barangay Case Summary</Text>
          {rows.map((row) => (
            <TouchableOpacity
              key={row.key}
              style={[styles.rowCard, row.key === selected && styles.rowCardSelected]}
              onPress={() => focus(row)}
              activeOpacity={0.8}
            >
              <View style={[styles.levelBar, { backgroundColor: LEVEL_COLORS[row.level] }]} />
              <View style={styles.rowBody}>
                <Text style={styles.rowTitle} numberOfLines={2}>{row.label}</Text>
                <Text style={styles.rowMeta}>
                  Cases {row.cases} · Population {row.population !== null ? row.population.toLocaleString() : "Unavailable"}
                </Text>
                <Text style={styles.rowMeta}>
                  Incidence / 100k {formatNumber(row.incidence)} · Ratio {formatNumber(row.ratio, 3)}
                </Text>
                {row.key === selected ? (
                  <Text style={styles.rowMeta}>
                    Previous month {row.previous} · Change {row.changePercent !== null ? `${row.changePercent}%` : "N/A"}
                  </Text>
                ) : null}
              </View>
              <View style={[styles.levelPill, { backgroundColor: LEVEL_COLORS[row.level] }]}>
                <Text style={styles.levelPillText}>{row.level}</Text>
              </View>
            </TouchableOpacity>
          ))}

          <Text style={styles.sectionTitle}>Monthly Trend</Text>
          <View style={styles.trendCard}>
            {trend.map((point) => (
              <View key={point.label} style={styles.trendColumn}>
                <Text style={styles.trendValue}>{point.cases}</Text>
                <View style={styles.trendTrack}>
                  <View style={[styles.trendBar, { height: `${(point.cases / maxTrend) * 100}%` }]} />
                </View>
                <Text style={styles.trendLabel}>{point.label}</Text>
              </View>
            ))}
          </View>
        </>
      )}

      <View style={styles.note}>
        <Text style={styles.noteText}>
          Interpretation: first hospital-recorded clinician-confirmed cases ÷ 2024 PSA census population × 100,000 for the
          selected Philippine month. Categories compare each barangay with the population-weighted study-area reference.
          Not complete community surveillance, clinical severity, transmission risk, or validated DOH alert levels.
        </Text>
      </View>
    </ScrollView>
  );
}

function Kpi({ label, value, small }: { label: string; value: string; small?: boolean }) {
  return (
    <View style={styles.kpi}>
      <Text style={styles.kpiLabel}>{label}</Text>
      <Text style={[styles.kpiValue, small && styles.kpiValueSmall]} numberOfLines={3}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#f8fafc", gap: 10 },
  container: { flex: 1, backgroundColor: "#f8fafc" },
  content: { padding: 20, paddingTop: 56, paddingBottom: 32 },
  eyebrow: { fontSize: 11, fontWeight: "800", letterSpacing: 1.5, color: "#2563eb" },
  title: { fontSize: 24, fontWeight: "800", color: "#0f172a", marginTop: 6 },
  subtitle: { fontSize: 13, lineHeight: 19, color: "#64748b", marginTop: 6 },
  hospitalRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 10 },
  muted: { fontSize: 13, color: "#64748b" },
  monthBar: { marginTop: 16, marginBottom: 6, flexGrow: 0 },
  monthChip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999, marginRight: 8,
    backgroundColor: "#ffffff", borderWidth: 1, borderColor: "#e2e8f0",
  },
  monthChipActive: { backgroundColor: "#2563eb", borderColor: "#2563eb" },
  monthText: { fontSize: 12, fontWeight: "700", color: "#334155" },
  monthTextActive: { color: "#ffffff" },
  kpiGrid: { flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between", marginTop: 12 },
  kpi: {
    width: "48.5%", backgroundColor: "#ffffff", borderRadius: 14, borderWidth: 1,
    borderColor: "#edf2f7", padding: 12, marginBottom: 10, minHeight: 86,
  },
  kpiLabel: { fontSize: 11, color: "#64748b" },
  kpiValue: { fontSize: 20, fontWeight: "800", color: "#0f172a", marginTop: 6 },
  kpiValueSmall: { fontSize: 13, lineHeight: 17 },
  caption: { fontSize: 11, lineHeight: 16, color: "#64748b", marginTop: 6 },
  warning: {
    flexDirection: "row", alignItems: "center", gap: 8, backgroundColor: "#fffbeb",
    borderColor: "#fde68a", borderWidth: 1, borderRadius: 12, padding: 12, marginTop: 10,
  },
  warningText: { flex: 1, fontSize: 12, color: "#92400e" },
  emptyCard: {
    backgroundColor: "#ffffff", borderRadius: 14, borderWidth: 1, borderStyle: "dashed",
    borderColor: "#cbd5e1", padding: 16, marginTop: 14,
  },
  mapCard: { height: 360, borderRadius: 16, overflow: "hidden", marginTop: 14, borderWidth: 1, borderColor: "#e2e8f0" },
  map: { flex: 1 },
  dot: { borderColor: "#ffffff", opacity: 0.85 },
  callout: { width: 220, padding: 4 },
  calloutTitle: { fontSize: 13, fontWeight: "800", color: "#0f172a", marginBottom: 4 },
  calloutText: { fontSize: 12, color: "#334155" },
  legend: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 10 },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 5 },
  legendDot: { width: 10, height: 10, borderRadius: 5 },
  legendText: { fontSize: 11, color: "#475569" },
  sectionTitle: { fontSize: 18, fontWeight: "800", color: "#0f172a", marginTop: 22, marginBottom: 10 },
  rowCard: {
    flexDirection: "row", alignItems: "center", gap: 10, backgroundColor: "#ffffff",
    borderRadius: 14, borderWidth: 1, borderColor: "#edf2f7", padding: 12, marginBottom: 8,
  },
  rowCardSelected: { borderColor: "#2563eb" },
  levelBar: { width: 5, alignSelf: "stretch", borderRadius: 3 },
  rowBody: { flex: 1, minWidth: 0 },
  rowTitle: { fontSize: 13, fontWeight: "700", color: "#0f172a" },
  rowMeta: { fontSize: 11, color: "#64748b", marginTop: 2 },
  levelPill: { borderRadius: 999, paddingHorizontal: 9, paddingVertical: 4 },
  levelPillText: { fontSize: 10, fontWeight: "800", color: "#ffffff" },
  trendCard: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "flex-end",
    backgroundColor: "#ffffff", borderRadius: 14, borderWidth: 1, borderColor: "#edf2f7", padding: 14, height: 170,
  },
  trendColumn: { flex: 1, alignItems: "center", height: "100%", justifyContent: "flex-end" },
  trendValue: { fontSize: 11, fontWeight: "700", color: "#0f172a", marginBottom: 4 },
  trendTrack: { width: 18, flex: 1, justifyContent: "flex-end", backgroundColor: "#eff6ff", borderRadius: 6 },
  trendBar: { width: "100%", backgroundColor: "#2563eb", borderRadius: 6 },
  trendLabel: { fontSize: 10, color: "#64748b", marginTop: 6 },
  note: { backgroundColor: "#eff6ff", borderRadius: 14, padding: 14, marginTop: 22 },
  noteText: { fontSize: 11, lineHeight: 17, color: "#475569" },
});
