
import { useEffect, useState } from "react";
import { Alert } from "react-native";
import { router } from "expo-router";
import { supabase } from "../lib/supabase";
import { StateView } from "../components/ui";

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
      <StateView
        kind="loading"
        title="Checking your account"
        message="Verifying your session and role."
      />
    );
  }

  // Show an error if the account cannot access a dashboard.
  return (
    <StateView
      kind="error"
      title="Unable to open your dashboard"
      message={errorMessage || "Your account cannot access this dashboard."}
      actionLabel="Sign out"
      onAction={() => void handleSignOut()}
    />
  );
}
