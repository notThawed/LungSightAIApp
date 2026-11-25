
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

type DashboardRole = "staff" | "radiologist" | "radiologic_technologist";

interface DashboardProps {
  role?: DashboardRole;
}

export default function Dashboard({ role }: DashboardProps) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);

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

      // Preserve the mobile role restriction.
      if (
        profile.role !== "radiologist" &&
        profile.role !== "radiologic_technologist"
      ) {
        await supabase.auth.signOut();
        router.replace("/login");
        return;
      }

      setUser(profile);
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
    const isPhysician = (activeRole ?? "radiologist") === "radiologist";

    router.push(
      isPhysician
        ? "/physician/notifications"
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
            {user.hospitalName || "Hospital not assigned"}
          </Text>
        </View>
      </View>

      <View style={styles.roleBadge}>
        <Ionicons
          name={isPhysician ? "medkit-outline" : "scan-outline"}
          size={15}
          color="#1d4ed8"
        />
        <Text style={styles.roleText}>
          {isPhysician
            ? "Radiologist / Physician"
            : "Radiologic Technologist"}
        </Text>
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Overview</Text>
        <Text style={styles.demoLabel}>PLACEHOLDER</Text>
      </View>

      <Text style={styles.sectionSubtitle}>
        Your clinical activity at a glance.
      </Text>

      <View style={styles.statsGrid}>
        <StatCard
          icon="calendar-outline"
          label={
            isPhysician ? "Today's Cases" : "Today's Examinations"
          }
          value="—"
          hint="Not connected yet"
        />
        <StatCard
          icon="time-outline"
          label={
            isPhysician ? "Pending Results" : "Pending Uploads"
          }
          value="—"
          hint="Not connected yet"
        />
        <StatCard
          icon="checkmark-circle-outline"
          label={isPhysician ? "Reviewed" : "Processing"}
          value="—"
          hint="Not connected yet"
        />
        <StatCard
          icon="alert-circle-outline"
          label={isPhysician ? "High Risk" : "Completed"}
          value="—"
          hint="Not connected yet"
        />
      </View>

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
  infoCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    backgroundColor: "#eff6ff",
    borderRadius: 16,
    padding: 16,
    marginTop: 9,
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