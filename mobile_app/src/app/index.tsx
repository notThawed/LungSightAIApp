
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
import { router } from "expo-router";
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
        <ActivityIndicator
          size="large"
          color={COLORS.primary}
        />
        <Text style={styles.loadingText}>
          Checking your account...
        </Text>
      </SafeAreaView>
    );
  }

  // Show an error if the account cannot access a dashboard.
  return (
    <SafeAreaView style={styles.centered}>
      <View style={styles.errorCard}>
        <View style={styles.iconCircle}>
          <Text style={styles.iconText}>!</Text>
        </View>

        <Text style={styles.title}>
          Unable to Open Dashboard
        </Text>

        <Text style={styles.message}>
          {errorMessage ||
            "Your account cannot access this dashboard."}
        </Text>

        <TouchableOpacity
          style={styles.button}
          onPress={handleSignOut}
          activeOpacity={0.8}
        >
          <Text style={styles.buttonText}>
            Sign Out
          </Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    backgroundColor: COLORS.background,
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },

  errorCard: {
    width: "100%",
    maxWidth: 420,
    backgroundColor: COLORS.white,
    borderRadius: 20,
    padding: 24,
    alignItems: "center",
    borderWidth: 1,
    borderColor: COLORS.border,
  },

  iconCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: "#FDECEC",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 18,
  },

  iconText: {
    color: "#B42318",
    fontSize: 34,
    fontWeight: "700",
  },

  title: {
    color: COLORS.text,
    fontSize: 21,
    fontWeight: "800",
    textAlign: "center",
  },

  message: {
    color: COLORS.secondary,
    fontSize: 14,
    lineHeight: 21,
    textAlign: "center",
    marginTop: 12,
  },

  button: {
    width: "100%",
    minHeight: 48,
    borderRadius: 12,
    backgroundColor: COLORS.primary,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 24,
  },

  buttonText: {
    color: COLORS.white,
    fontSize: 15,
    fontWeight: "700",
  },

  loadingText: {
    color: COLORS.secondary,
    marginTop: 12,
  },
});