import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { router } from "expo-router";
import { supabase } from "../../lib/supabase";
import { getCurrentUserProfile, UserProfile } from "../../lib/user";

interface DashboardProps {
  role?: "physician" | "rad_tech";
}

export default function Dashboard({ role }: DashboardProps) {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const profile = await getCurrentUserProfile();

      // Make sure only mobile-supported roles can use this dashboard.
      if (
        profile.role !== "physician" &&
        profile.role !== "rad_tech"
      ) {
        await supabase.auth.signOut();
        router.replace("/login");
        return;
      }

      setUser(profile);
    } catch (error) {
      console.error("Dashboard error:", error);

      Alert.alert(
        "Error",
        "Unable to load your dashboard."
      );

      router.replace("/login");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    Alert.alert(
      "Sign Out",
      "Are you sure you want to sign out?",
      [
        {
          text: "Cancel",
          style: "cancel",
        },
        {
          text: "Sign Out",
          style: "destructive",
          onPress: async () => {
            const { error } =
              await supabase.auth.signOut();

            if (error) {
              Alert.alert(
                "Sign Out Failed",
                error.message
              );
              return;
            }

            router.replace("/login");
          },
        },
      ]
    );
  };

  if (loading || !user) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />

        <Text style={styles.loadingText}>
          Loading LungSight...
        </Text>
      </View>
    );
  }

  const isPhysician =
    user.role === "physician";

  const displayName = isPhysician
    ? `Dr. ${user.fullName}`
    : user.fullName;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerInfo}>
          <Text style={styles.welcome}>
            Welcome, {displayName}
          </Text>

          <Text style={styles.hospital}>
            {user.hospitalName}
          </Text>
        </View>

        <TouchableOpacity
          style={styles.profileButton}
          onPress={() =>
            router.push(
              isPhysician
                ? "/physician/profile"
                : "/rad_tech/profile"
            )
          }
        >
          <Text style={styles.profileButtonText}>
            {user.fullName
              .charAt(0)
              .toUpperCase()}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Role */}
      <View style={styles.roleBadge}>
        <Text style={styles.roleText}>
          {isPhysician
            ? "Physician"
            : "Radiologic Technologist"}
        </Text>
      </View>

      {/* Statistics */}
      <Text style={styles.sectionTitle}>
        Overview
      </Text>

      <View style={styles.statsContainer}>
        <View style={styles.statCard}>
          <Text style={styles.statTitle}>
            {isPhysician
              ? "Today's Cases"
              : "Today's Examinations"}
          </Text>

          <Text style={styles.statValue}>
            0
          </Text>
        </View>

        <View style={styles.statCard}>
          <Text style={styles.statTitle}>
            {isPhysician
              ? "Pending Results"
              : "Pending Uploads"}
          </Text>

          <Text style={styles.statValue}>
            0
          </Text>
        </View>

        <View style={styles.statCard}>
          <Text style={styles.statTitle}>
            {isPhysician
              ? "Reviewed"
              : "Processing"}
          </Text>

          <Text style={styles.statValue}>
            0
          </Text>
        </View>

        <View style={styles.statCard}>
          <Text style={styles.statTitle}>
            {isPhysician
              ? "High Risk"
              : "Completed"}
          </Text>

          <Text style={styles.statValue}>
            0
          </Text>
        </View>
      </View>

      {/* Quick Actions */}
      <Text style={styles.sectionTitle}>
        Quick Actions
      </Text>

      <View style={styles.actionsContainer}>
        <TouchableOpacity
          style={styles.actionCard}
          onPress={() =>
            router.push(
              isPhysician
                ? "/physician/patients"
                : "/rad_tech/patients"
            )
          }
        >
          <Text style={styles.actionTitle}>
            Patients
          </Text>

          <Text style={styles.actionDescription}>
            View and search patient records
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionCard}
          onPress={() =>
            router.push(
              isPhysician
                ? "/physician/examinations"
                : "/rad_tech/examinations"
            )
          }
        >
          <Text style={styles.actionTitle}>
            Examinations
          </Text>

          <Text style={styles.actionDescription}>
            View examination activity
          </Text>
        </TouchableOpacity>

        {isPhysician ? (
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() =>
              router.push("/physician/results")
            }
          >
            <Text style={styles.actionTitle}>
              AI Results
            </Text>

            <Text style={styles.actionDescription}>
              Review pneumonia detection results
            </Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={styles.actionCard}
            onPress={() =>
              router.push("/rad_tech/upload")
            }
          >
            <Text style={styles.actionTitle}>
              Upload X-Ray
            </Text>

            <Text style={styles.actionDescription}>
              Upload a chest X-ray examination
            </Text>
          </TouchableOpacity>
        )}

        <TouchableOpacity
          style={styles.actionCard}
          onPress={() =>
            router.push(
              isPhysician
                ? "/physician/mapping"
                : "/rad_tech/mapping"
            )
          }
        >
          <Text style={styles.actionTitle}>
            Geospatial Mapping
          </Text>

          <Text style={styles.actionDescription}>
            View pneumonia cases by location
          </Text>
        </TouchableOpacity>
      </View>

      {/* Profile and Test */}
      <View style={styles.bottomButtons}>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() =>
            router.push(
              isPhysician
                ? "/physician/profile"
                : "/rad_tech/profile"
            )
          }
        >
          <Text style={styles.secondaryButtonText}>
            My Profile
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() =>
            router.push(
              isPhysician
                ? "/physician/test"
                : "/rad_tech/test"
            )
          }
        >
          <Text style={styles.secondaryButtonText}>
            Test UI
          </Text>
        </TouchableOpacity>
      </View>

      {/* Logout */}
      <TouchableOpacity
        style={styles.logoutButton}
        onPress={handleLogout}
      >
        <Text style={styles.logoutText}>
          Sign Out
        </Text>
      </TouchableOpacity>
    </ScrollView>
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
    fontSize: 16,
    color: "#64748b",
  },

  container: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },

  content: {
    padding: 24,
    paddingTop: 60,
    paddingBottom: 40,
  },

  header: {
    flexDirection: "row",
    alignItems: "flex-start",
  },

  headerInfo: {
    flex: 1,
    minWidth: 0,
    paddingRight: 12,
  },

  welcome: {
    fontSize: 25,
    fontWeight: "bold",
    color: "#0f172a",
    lineHeight: 31,
  },

  hospital: {
    fontSize: 15,
    color: "#64748b",
    marginTop: 6,
  },

  profileButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: "#2563eb",
    justifyContent: "center",
    alignItems: "center",
    flexShrink: 0,
  },

  profileButtonText: {
    color: "#fff",
    fontSize: 20,
    fontWeight: "bold",
  },

  roleBadge: {
    alignSelf: "flex-start",
    backgroundColor: "#e2e8f0",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    marginTop: 15,
  },

  roleText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#475569",
  },

  sectionTitle: {
    fontSize: 20,
    fontWeight: "bold",
    color: "#0f172a",
    marginTop: 30,
    marginBottom: 15,
  },

  statsContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
  },

  statCard: {
    width: "48%",
    backgroundColor: "#fff",
    padding: 18,
    borderRadius: 14,
    marginBottom: 12,
  },

  statTitle: {
    fontSize: 13,
    color: "#64748b",
  },

  statValue: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#0f172a",
    marginTop: 8,
  },

  actionsContainer: {
    gap: 12,
  },

  actionCard: {
    backgroundColor: "#fff",
    padding: 18,
    borderRadius: 14,
  },

  actionTitle: {
    fontSize: 17,
    fontWeight: "bold",
    color: "#0f172a",
  },

  actionDescription: {
    fontSize: 14,
    color: "#64748b",
    marginTop: 5,
  },

  bottomButtons: {
    flexDirection: "row",
    gap: 12,
    marginTop: 30,
  },

  secondaryButton: {
    flex: 1,
    height: 52,
    borderRadius: 10,
    backgroundColor: "#e2e8f0",
    justifyContent: "center",
    alignItems: "center",
  },

  secondaryButtonText: {
    color: "#0f172a",
    fontSize: 15,
    fontWeight: "600",
  },

  logoutButton: {
    height: 52,
    borderRadius: 10,
    backgroundColor: "#dc2626",
    justifyContent: "center",
    alignItems: "center",
    marginTop: 12,
  },

  logoutText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "bold",
  },
});