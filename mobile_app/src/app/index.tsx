
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { router } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";
import { supabase } from "../lib/supabase";

const COLORS = {
  primary: "#1769AA",
  background: "#F5F8FC",
  white: "#FFFFFF",
  text: "#163A5C",
  secondary: "#64748B",
  border: "#E1E8F0",
};

type DashboardRoute = "/physician" | "/rad_tech" | "/staff";

export default function Index() {
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function checkSessionAndRole() {
      try {
        setLoading(true);
        setErrorMessage("");

        // 1. Check the current authenticated user.
        const {
          data: { user },
          error: authError,
        } = await supabase.auth.getUser();

        if (authError) {
          throw authError;
        }

        // 2. If there is no authenticated user, go to Login.
        if (!user) {
          router.replace("/login");
          return;
        }

        // 3. Get the user's existing profile.
        const { data: profile, error: profileError } =
          await supabase
            .from("user_profiles")
            .select("user_id, role_id, is_active")
            .eq("user_id", user.id)
            .maybeSingle();

        if (profileError) {
          throw profileError;
        }

        if (!profile) {
          throw new Error(
            "Your user profile was not found. Please contact your administrator."
          );
        }

        // 4. Prevent inactive accounts from entering the dashboard.
        if (!profile.is_active) {
          throw new Error(
            "Your account is inactive. Please contact your administrator."
          );
        }

        // 5. Retrieve the user's assigned role.
        const { data: roleRecord, error: roleError } =
          await supabase
            .from("roles")
            .select("role_name")
            .eq("role_id", profile.role_id)
            .maybeSingle();

        if (roleError) {
          throw roleError;
        }

        if (!roleRecord?.role_name) {
          throw new Error(
            "No valid role is assigned to your account."
          );
        }

        // 6. Redirect according to the existing role names.
        let destination: DashboardRoute;

        switch (roleRecord.role_name) {
          case "Radiologist":
            destination = "/physician";
            break;

          case "Radiologic Technologist":
            destination = "/rad_tech";
            break;

          case "Staff":
            destination = "/staff";
            break;

          case "Superadmin":
            throw new Error(
              "Superadmin accounts cannot access the mobile dashboard."
            );

          case "Hospital Admin":
            throw new Error(
              "Hospital Admin accounts cannot access the mobile dashboard."
            );

          default:
            throw new Error(
              `Unsupported account role: ${roleRecord.role_name}`
            );
        }

        if (isMounted) {
          router.replace(destination);
        }
      } catch (error) {
        if (isMounted) {
          setErrorMessage(
            error instanceof Error
              ? error.message
              : "Unable to open your dashboard."
          );
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    checkSessionAndRole();

    return () => {
      isMounted = false;
    };
  }, []);

  async function handleSignOut() {
    const { error } = await supabase.auth.signOut();

    if (error) {
      Alert.alert("Sign Out Failed", error.message);
      return;
    }

    router.replace("/login");
  }

  // Loading screen while checking the session and role.
  if (loading) {
    return (
      <SafeAreaView style={styles.centered}>
        <StatusBar style="dark" />
        <View style={styles.logoBadge}>
          <Ionicons name="pulse" size={32} color="#FFFFFF" />
        </View>
        <Text style={styles.appTitle}>
          LungSight <Text style={styles.aiTag}>AI</Text>
        </Text>
        <Text style={styles.appSubtitle}>Clinical Decision Support System</Text>
        <ActivityIndicator
          size="small"
          color="#1D4ED8"
          style={{ marginTop: 24, marginBottom: 8 }}
        />
        <Text style={styles.loadingText}>
          Verifying practitioner credentials...
        </Text>
      </SafeAreaView>
    );
  }

  // Show an error if the account cannot access a dashboard.
  return (
    <SafeAreaView style={styles.centered}>
      <StatusBar style="dark" />
      <View style={styles.errorCard}>
        <View style={styles.iconCircle}>
          <Ionicons name="alert-circle" size={32} color="#DC2626" />
        </View>

        <Text style={styles.title}>
          Unable to Open Dashboard
        </Text>

        <Text style={styles.message}>
          {errorMessage ||
            "Your account cannot access this mobile dashboard."}
        </Text>

        <TouchableOpacity
          style={styles.button}
          onPress={handleSignOut}
          activeOpacity={0.8}
        >
          <View style={styles.buttonRow}>
            <Ionicons name="log-out-outline" size={18} color="#FFFFFF" />
            <Text style={styles.buttonText}>
              Sign Out & Switch Account
            </Text>
          </View>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    backgroundColor: "#F8FAFC",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },

  logoBadge: {
    width: 68,
    height: 68,
    borderRadius: 20,
    backgroundColor: "#1D4ED8",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#1D4ED8",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.3,
    shadowRadius: 10,
    elevation: 6,
    marginBottom: 16,
  },

  appTitle: {
    fontSize: 26,
    fontWeight: "800",
    color: "#0F172A",
    letterSpacing: -0.5,
  },

  aiTag: {
    color: "#2563EB",
    fontWeight: "900",
  },

  appSubtitle: {
    fontSize: 13,
    color: "#64748B",
    marginTop: 4,
  },

  loadingText: {
    fontSize: 13,
    color: "#94A3B8",
    fontWeight: "500",
  },

  errorCard: {
    width: "100%",
    maxWidth: 400,
    backgroundColor: "#FFFFFF",
    borderRadius: 22,
    padding: 24,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    shadowColor: "#0F172A",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.05,
    shadowRadius: 12,
    elevation: 3,
  },

  iconCircle: {
    width: 58,
    height: 58,
    borderRadius: 18,
    backgroundColor: "#FEF2F2",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 16,
  },

  title: {
    color: "#0F172A",
    fontSize: 20,
    fontWeight: "800",
    textAlign: "center",
    letterSpacing: -0.3,
  },

  message: {
    color: "#64748B",
    fontSize: 14,
    lineHeight: 22,
    textAlign: "center",
    marginTop: 10,
    paddingHorizontal: 8,
  },

  button: {
    width: "100%",
    minHeight: 48,
    borderRadius: 12,
    backgroundColor: "#1D4ED8",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 22,
    shadowColor: "#1D4ED8",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.2,
    shadowRadius: 4,
    elevation: 3,
  },

  buttonRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },

  buttonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "700",
  },
});