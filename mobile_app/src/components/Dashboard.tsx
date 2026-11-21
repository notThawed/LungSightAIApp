
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { router } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";

import { supabase } from "../lib/supabase";
import { getCurrentUserProfile, UserProfile } from "../lib/user";
import { isActiveAppointment, loadDashboardData } from "../lib/dashboard";
import type { DashboardData, TodayAppointment, TodayExamination } from "../lib/dashboard";
import { formatManilaTime, formatTimeOfDay } from "../lib/time";

type DashboardRole = "staff" | "radiologist" | "radiologic_technologist";

interface DashboardProps {
  role?: DashboardRole;
}

export default function Dashboard({ role }: DashboardProps) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [data, setData] = useState<DashboardData | null>(null);
  const [dataError, setDataError] = useState("");

  const activeRole = role ?? user?.role;

  const loadDashboard = useCallback(async (isRefresh = false) => {
    // Only show the full-screen loader on the initial load.
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const profile = await getCurrentUserProfile();

      // Mobile is for clinical staff roles only.
      if (
        profile.role !== "radiologist" &&
        profile.role !== "radiologic_technologist" &&
        profile.role !== "staff"
      ) {
        await supabase.auth.signOut();
        router.replace("/login");
        return;
      }

      setUser(profile);

      if (profile.hospitalId) {
        try {
          setData(await loadDashboardData(profile.role, profile.hospitalId));
          setDataError("");
        } catch (error) {
          console.error("Dashboard data error:", error);
          setDataError("Some dashboard information could not be loaded. Pull down to try again.");
        }
      } else {
        setData(null);
        setDataError("");
      }
    } catch (error) {
      console.error("Dashboard error:", error);

      if (isRefresh) {
        Alert.alert(
          "Refresh failed",
          "Unable to refresh your dashboard. Please check your connection and try again."
        );
      } else {
        Alert.alert("Error", "Unable to load your dashboard.");
        router.replace("/login");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const onRefresh = useCallback(() => {
    void loadDashboard(true);
  }, [loadDashboard]);

  const handleNotifications = () => {
    const current = activeRole ?? "radiologist";

    router.push(
      current === "radiologist"
        ? "/physician/notifications"
        : current === "staff"
          ? "/staff/notifications"
          : "/rad_tech/notifications"
    );
  };

  if (loading || !user) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={styles.loadingText}>Loading LungSight...</Text>
      </View>
    );
  }

  const isPhysician = user.role === "radiologist";
  const displayName = isPhysician
    ? `Dr. ${user.fullName}`
    : user.fullName;
  const roleLabel = isPhysician
    ? "Radiologist / Physician"
    : user.role === "staff"
      ? "Staff"
      : "Radiologic Technologist";
  const hospitalLabel =
    user.hospitalName ||
    (user.hospitalId ? "Hospital name unavailable" : "Hospital not assigned");

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onRefresh}
          colors={["#2563eb"]}
          tintColor="#2563eb"
          progressBackgroundColor="#ffffff"
        />
      }
    >
      <View style={styles.header}>
        <View style={styles.brandRow}>
          <View style={styles.brandIcon}>
            <Ionicons
              name="pulse-outline"
              size={23}
              color="#ffffff"
            />
          </View>

          <View>
            <Text style={styles.brand}>
              LungSight <Text style={styles.brandAI}>AI</Text>
            </Text>
            <Text style={styles.brandSubtitle}>
              Clinical dashboard
            </Text>
          </View>
        </View>

        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Open notifications"
          style={styles.bellButton}
          onPress={handleNotifications}
        >
          <Ionicons
            name="notifications-outline"
            size={23}
            color="#0f172a"
          />
        </TouchableOpacity>
      </View>

      <View style={styles.welcomeBlock}>
        <Text style={styles.welcomeEyebrow}>WELCOME BACK</Text>
        <Text style={styles.welcome}>Hello, {displayName}</Text>

        <View style={styles.hospitalRow}>
          <Ionicons
            name="business-outline"
            size={16}
            color="#64748b"
          />
          <Text style={styles.hospital}>
            {hospitalLabel}
          </Text>
        </View>
      </View>

      <View style={styles.roleBadge}>
        <Ionicons
          name={isPhysician ? "medkit-outline" : user.role === "staff" ? "people-outline" : "scan-outline"}
          size={15}
          color="#1d4ed8"
        />
        <Text style={styles.roleText}>
          {roleLabel}
        </Text>
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Today</Text>
        {data ? <Text style={styles.demoLabel}>{data.day}</Text> : null}
      </View>

      <Text style={styles.sectionSubtitle}>
        Your hospital's activity for today (Philippine time).
      </Text>

      {dataError ? (
        <View style={styles.errorBanner}>
          <Ionicons name="warning-outline" size={18} color="#b45309" />
          <Text style={styles.errorBannerText}>{dataError}</Text>
        </View>
      ) : null}

      {!user.hospitalId ? (
        <EmptyState text="Your account is not assigned to a hospital. Contact your administrator." />
      ) : (
        <>
          <View style={styles.statsGrid}>
            {(data?.stats ?? []).map((stat) => (
              <StatCard
                key={stat.key}
                icon={stat.icon as React.ComponentProps<typeof Ionicons>["name"]}
                label={stat.label}
                value={String(stat.value)}
                hint={stat.hint}
              />
            ))}
          </View>

          <SectionTitle
            title="Today's Appointments"
            subtitle="Follow-up visits scheduled for today"
            count={data?.appointments.length ?? 0}
          />
          {data && data.appointments.length > 0 ? (
            data.appointments.map((appointment) => (
              <AppointmentRow key={appointment.id} appointment={appointment} />
            ))
          ) : (
            <EmptyState text="No appointments scheduled for today." />
          )}

          <SectionTitle
            title="Today's Examinations"
            subtitle="Examinations registered today"
            count={data?.examinations.length ?? 0}
          />
          {data && data.examinations.length > 0 ? (
            data.examinations.map((examination) => (
              <ExaminationRow key={examination.id} examination={examination} />
            ))
          ) : (
            <EmptyState text="No examinations registered today yet." />
          )}
        </>
      )}

      <View style={styles.infoCard}>
        <View style={styles.infoIcon}>
          <Ionicons
            name="shield-checkmark-outline"
            size={22}
            color="#2563eb"
          />
        </View>

        <View style={styles.infoTextWrap}>
          <Text style={styles.infoTitle}>
            Clinical decision support
          </Text>
          <Text style={styles.infoText}>
            LungSight supports healthcare professionals. AI results
            should be reviewed by qualified clinical staff.
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}

const STATUS_TONES: Record<string, { bg: string; fg: string }> = {
  Scheduled: { bg: "#dbeafe", fg: "#1d4ed8" },
  Rescheduled: { bg: "#ede9fe", fg: "#6d28d9" },
  Arrived: { bg: "#ccfbf1", fg: "#0f766e" },
  Completed: { bg: "#dcfce7", fg: "#15803d" },
  Cancelled: { bg: "#f1f5f9", fg: "#475569" },
  Missed: { bg: "#fee2e2", fg: "#b91c1c" },
  Pending: { bg: "#fef3c7", fg: "#b45309" },
  "Awaiting X-Ray": { bg: "#e0f2fe", fg: "#0369a1" },
  "X-Ray Ready": { bg: "#dbeafe", fg: "#1d4ed8" },
  Admitted: { bg: "#fce7f3", fg: "#be185d" },
  Discharged: { bg: "#dcfce7", fg: "#15803d" },
};

function StatusPill({ status }: { status: string }) {
  const tone = STATUS_TONES[status] ?? { bg: "#f1f5f9", fg: "#475569" };
  return (
    <View style={[styles.pill, { backgroundColor: tone.bg }]}>
      <Text style={[styles.pillText, { color: tone.fg }]}>{status}</Text>
    </View>
  );
}

function SectionTitle({ title, subtitle, count }: { title: string; subtitle: string; count: number }) {
  return (
    <View style={styles.listHeader}>
      <View style={styles.listHeaderText}>
        <Text style={styles.sectionTitle}>{title}</Text>
        <Text style={styles.sectionSubtitleTight}>{subtitle}</Text>
      </View>
      <View style={styles.countBadge}>
        <Text style={styles.countText}>{count}</Text>
      </View>
    </View>
  );
}

function AppointmentRow({ appointment }: { appointment: TodayAppointment }) {
  const active = isActiveAppointment(appointment.status);
  return (
    <View style={[styles.rowCard, !active && styles.rowCardMuted]}>
      <View style={styles.timeBox}>
        <Ionicons name="time-outline" size={15} color="#2563eb" />
        <Text style={styles.timeText}>{formatTimeOfDay(appointment.time)}</Text>
      </View>
      <View style={styles.rowBody}>
        <Text style={styles.rowTitle} numberOfLines={1}>{appointment.patientName}</Text>
        <Text style={styles.rowMeta} numberOfLines={1}>
          {[appointment.patientCode, appointment.code].filter(Boolean).join(" · ") || "Follow-up appointment"}
        </Text>
      </View>
      <StatusPill status={appointment.status} />
    </View>
  );
}

function ExaminationRow({ examination }: { examination: TodayExamination }) {
  return (
    <View style={styles.rowCard}>
      <View style={styles.timeBox}>
        <Ionicons name="document-text-outline" size={15} color="#2563eb" />
        <Text style={styles.timeText}>{formatManilaTime(examination.time)}</Text>
      </View>
      <View style={styles.rowBody}>
        <Text style={styles.rowTitle} numberOfLines={1}>{examination.patientName}</Text>
        <Text style={styles.rowMeta} numberOfLines={1}>
          {[examination.patientCode, examination.type].filter(Boolean).join(" · ")}
        </Text>
      </View>
      <StatusPill status={examination.status} />
    </View>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <View style={styles.emptyCard}>
      <Text style={styles.emptyText}>{text}</Text>
    </View>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <View style={styles.statCard}>
      <View style={styles.statIcon}>
        <Ionicons name={icon} size={20} color="#2563eb" />
      </View>
      <Text style={styles.statTitle}>{label}</Text>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statHint}>{hint}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f8fafc",
  },
  loadingText: {
    marginTop: 12,
    fontSize: 15,
    color: "#64748b",
  },
  container: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },
  content: {
    padding: 20,
    paddingTop: 56,
    paddingBottom: 28,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  brandIcon: {
    width: 43,
    height: 43,
    borderRadius: 13,
    backgroundColor: "#2563eb",
    alignItems: "center",
    justifyContent: "center",
  },
  brand: {
    fontSize: 19,
    fontWeight: "800",
    color: "#0f172a",
  },
  brandAI: {
    color: "#2563eb",
  },
  brandSubtitle: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 2,
  },
  bellButton: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: "#ffffff",
    borderWidth: 1,
    borderColor: "#e2e8f0",
    alignItems: "center",
    justifyContent: "center",
  },
  welcomeBlock: {
    marginTop: 30,
  },
  welcomeEyebrow: {
    fontSize: 11,
    fontWeight: "800",
    letterSpacing: 1.5,
    color: "#2563eb",
  },
  welcome: {
    fontSize: 25,
    lineHeight: 32,
    fontWeight: "800",
    color: "#0f172a",
    marginTop: 6,
  },
  hospitalRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    marginTop: 8,
  },
  hospital: {
    fontSize: 14,
    color: "#64748b",
    flexShrink: 1,
  },
  roleBadge: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
    marginTop: 17,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "#dbeafe",
  },
  roleText: {
    color: "#1d4ed8",
    fontSize: 12,
    fontWeight: "700",
  },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 30,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: "#0f172a",
  },
  demoLabel: {
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1,
    color: "#64748b",
    backgroundColor: "#e2e8f0",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  sectionSubtitle: {
    fontSize: 13,
    color: "#64748b",
    marginTop: 5,
    marginBottom: 15,
  },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
  },
  statCard: {
    width: "48.3%",
    minHeight: 155,
    backgroundColor: "#ffffff",
    borderRadius: 17,
    borderWidth: 1,
    borderColor: "#edf2f7",
    padding: 15,
    marginBottom: 12,
  },
  statIcon: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: "#eff6ff",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 12,
  },
  statTitle: {
    fontSize: 12,
    lineHeight: 17,
    color: "#64748b",
    minHeight: 34,
  },
  statValue: {
    fontSize: 25,
    fontWeight: "800",
    color: "#0f172a",
    marginTop: 5,
  },
  statHint: {
    fontSize: 10,
    color: "#94a3b8",
    marginTop: 3,
  },
  errorBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    backgroundColor: "#fffbeb",
    borderColor: "#fde68a",
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
  },
  errorBannerText: {
    flex: 1,
    fontSize: 12,
    color: "#92400e",
  },
  listHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 22,
    marginBottom: 10,
  },
  listHeaderText: {
    flex: 1,
  },
  sectionSubtitleTight: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 3,
  },
  countBadge: {
    minWidth: 30,
    height: 30,
    borderRadius: 15,
    paddingHorizontal: 8,
    backgroundColor: "#dbeafe",
    alignItems: "center",
    justifyContent: "center",
  },
  countText: {
    fontSize: 13,
    fontWeight: "800",
    color: "#1d4ed8",
  },
  rowCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#ffffff",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#edf2f7",
    padding: 12,
    marginBottom: 8,
  },
  rowCardMuted: {
    opacity: 0.6,
  },
  timeBox: {
    width: 78,
    alignItems: "center",
    gap: 3,
    paddingVertical: 6,
    borderRadius: 10,
    backgroundColor: "#eff6ff",
  },
  timeText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#1e3a8a",
    textAlign: "center",
  },
  rowBody: {
    flex: 1,
    minWidth: 0,
  },
  rowTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: "#0f172a",
  },
  rowMeta: {
    fontSize: 12,
    color: "#64748b",
    marginTop: 2,
  },
  pill: {
    borderRadius: 999,
    paddingHorizontal: 9,
    paddingVertical: 4,
  },
  pillText: {
    fontSize: 10,
    fontWeight: "800",
  },
  emptyCard: {
    backgroundColor: "#ffffff",
    borderRadius: 14,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: "#cbd5e1",
    padding: 16,
    marginBottom: 8,
  },
  emptyText: {
    fontSize: 13,
    color: "#64748b",
    textAlign: "center",
  },
  infoCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    backgroundColor: "#eff6ff",
    borderRadius: 16,
    padding: 16,
    marginTop: 22,
  },
  infoIcon: {
    width: 38,
    height: 38,
    borderRadius: 12,
    backgroundColor: "#ffffff",
    alignItems: "center",
    justifyContent: "center",
  },
  infoTextWrap: {
    flex: 1,
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: "#1e3a8a",
  },
  infoText: {
    fontSize: 12,
    lineHeight: 18,
    color: "#475569",
    marginTop: 5,
  },
});