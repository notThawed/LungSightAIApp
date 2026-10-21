import { useCallback, useEffect, useState, type ComponentProps } from "react";
import { StyleSheet, Text, View } from "react-native";
import { router, type Href } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";

import { supabase } from "../lib/supabase";
import { getCurrentUserProfile, UserProfile } from "../lib/user";
import { getDashboardMetrics, type DashboardMetric, type MetricKey } from "../lib/dashboard";
import { AI_DISCLAIMER } from "../constants/ai";
import { C, Spacing, Type } from "../constants/theme";
import {
  BrandBar,
  IconButton,
  Note,
  Pill,
  Screen,
  SectionTitle,
  StatCard,
  StateView,
  type Tone,
} from "./ui";

type DashboardRole = "staff" | "radiologist" | "radiologic_technologist";

interface DashboardProps {
  role?: DashboardRole;
}

/** Roles that may use the mobile companion app. */
const MOBILE_ROLES: UserProfile["role"][] = [
  "radiologist",
  "radiologic_technologist",
  "staff",
];

const ROLE_INFO: Record<
  DashboardRole,
  { label: string; icon: ComponentProps<typeof Ionicons>["name"]; notifications: Href }
> = {
  radiologist: { label: "Radiologist", icon: "medkit-outline", notifications: "/physician/notifications" },
  radiologic_technologist: { label: "Radiologic Technologist", icon: "scan-outline", notifications: "/rad_tech/notifications" },
  staff: { label: "Staff", icon: "people-outline", notifications: "/staff/notifications" },
};

/** Same icon/tone per metric as the web dashboard (METRIC_ICONS). */
const METRIC_STYLE: Record<MetricKey, { icon: ComponentProps<typeof Ionicons>["name"]; tone: Tone }> = {
  pending_exams: { icon: "hourglass-outline", tone: "warning" },
  xray_ready: { icon: "scan-outline", tone: "info" },
  awaiting_xray: { icon: "time-outline", tone: "primary" },
  completed_exams: { icon: "checkmark-done-outline", tone: "success" },
  followups_today: { icon: "calendar-outline", tone: "primary" },
  followups_upcoming: { icon: "calendar-number-outline", tone: "info" },
  followups_missed: { icon: "calendar-clear-outline", tone: "danger" },
};

/**
 * Load the signed-in user and their metrics. Returns null (after signing
 * out) when the role is not allowed on mobile — admin roles use the web app.
 */
async function fetchDashboardData(): Promise<{
  profile: UserProfile;
  metrics: DashboardMetric[];
} | null> {
  const profile = await getCurrentUserProfile();

  if (!MOBILE_ROLES.includes(profile.role)) {
    await supabase.auth.signOut();
    router.replace("/login");
    return null;
  }

  const metrics = profile.hospitalId
    ? await getDashboardMetrics(profile.role, profile.hospitalId)
    : [];

  return { profile, metrics };
}

export default function Dashboard({ role }: DashboardProps) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [metrics, setMetrics] = useState<DashboardMetric[]>([]);
  const [loadError, setLoadError] = useState("");

  // Callers set `loading` / `refreshing` before calling. State is only
  // updated in promise callbacks, so this is safe to start from an effect.
  const loadDashboard = useCallback(
    () =>
      fetchDashboardData()
        .then((data) => {
          if (!data) return;

          setUser(data.profile);
          setMetrics(data.metrics);
          setLoadError("");
        })
        .catch((error) => {
          console.error("Dashboard error:", error);
          setLoadError(
            error instanceof Error ? error.message : "Unable to load your dashboard."
          );
        })
        .finally(() => {
          setLoading(false);
          setRefreshing(false);
        }),
    []
  );

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  if (loading) {
    return <StateView kind="loading" title="Loading your dashboard" />;
  }

  if (!user) {
    return (
      <StateView
        kind="error"
        title="Unable to load your dashboard"
        message={loadError || "Check your connection and try again."}
        actionLabel="Try again"
        onAction={() => {
          setLoading(true);
          void loadDashboard();
        }}
        secondaryLabel="Back to sign in"
        onSecondary={() => router.replace("/login")}
      />
    );
  }

  const activeRole = (role ?? user.role) as DashboardRole;
  const info = ROLE_INFO[activeRole] ?? ROLE_INFO.staff;
  const displayName =
    user.role === "radiologist" ? `Dr. ${user.fullName}` : user.fullName;
  const someUnavailable = metrics.some((metric) => metric.value === null);

  return (
    <Screen
      refreshing={refreshing}
      onRefresh={() => {
        setRefreshing(true);
        void loadDashboard();
      }}
    >
      <BrandBar
        right={
          <IconButton
            icon="notifications-outline"
            label="Open notifications"
            onPress={() => router.push(info.notifications)}
          />
        }
      />

      <View style={styles.welcome}>
        <Text style={Type.label}>WELCOME BACK</Text>
        <Text style={Type.display}>{displayName}</Text>
        <View style={styles.metaRow}>
          <Ionicons name="business-outline" size={16} color={C.muted} />
          <Text style={[Type.body, styles.hospital]} numberOfLines={1}>
            {user.hospitalName || "Hospital not assigned"}
          </Text>
        </View>
        <Pill label={info.label} icon={info.icon} tone="primary" />
      </View>

      <SectionTitle
        title="Overview"
        caption="Live counts for your hospital. Pull down to refresh."
      />

      {loadError ? (
        <Note tone="danger" icon="alert-circle-outline">
          Refresh failed: {loadError}
        </Note>
      ) : null}

      {!user.hospitalId ? (
        <Note tone="warning" icon="information-circle-outline">
          Your account is not linked to a hospital, so there is no workload to show.
        </Note>
      ) : (
        <View style={styles.statsGrid}>
          {metrics.map((metric) => (
            <StatCard
              key={metric.key}
              icon={METRIC_STYLE[metric.key].icon}
              tone={METRIC_STYLE[metric.key].tone}
              label={metric.label}
              value={metric.value === null ? "—" : metric.value.toLocaleString()}
              hint={metric.hint}
            />
          ))}
        </View>
      )}

      {someUnavailable ? (
        <Note tone="warning" icon="cloud-offline-outline">
          Some numbers could not be loaded and are shown as “—”. Pull down to try again.
        </Note>
      ) : null}

      {activeRole !== "staff" ? (
        <Note tone="info" icon="shield-checkmark-outline">
          {AI_DISCLAIMER}
        </Note>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  welcome: {
    gap: Spacing[1],
    marginTop: Spacing[2],
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginBottom: Spacing[2],
  },
  hospital: {
    flexShrink: 1,
  },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: Spacing[3],
  },
});
