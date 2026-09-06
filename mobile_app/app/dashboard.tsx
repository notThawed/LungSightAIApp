import { useEffect } from "react";
import {
  ActivityIndicator,
  Text,
  View,
} from "react-native";

import { router } from "expo-router";
import { supabase } from "../lib/supabase";

export default function Dashboard() {
  useEffect(() => {
    detectRole();
  }, []);

  const detectRole = async () => {
    // Get logged-in user
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError) {
      console.error("User error:", userError);
      router.replace("/login");
      return;
    }

    if (!user) {
      router.replace("/login");
      return;
    }

    // Get user's role
    const { data: profile, error: profileError } =
      await supabase
        .from("profiles")
        .select("role")
        .eq("id", user.id)
        .single();

    if (profileError) {
      console.error("Profile error:", profileError);

      await supabase.auth.signOut();

      router.replace("/login");
      return;
    }

    console.log("Logged-in user:", user.email);
    console.log("Role:", profile.role);

    // Send user to the correct application
    switch (profile.role) {
      case "physician":
        router.replace("/physician");
        break;

      case "rad_tech":
        router.replace("/rad_tech");
        break;

      default:
        console.error(
          "Unauthorized mobile role:",
          profile.role
        );

        await supabase.auth.signOut();

        router.replace("/login");
    }
  };

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" />

      <Text style={styles.text}>
        Loading LungSight...
      </Text>
    </View>
  );
}

const styles = {
  container: {
    flex: 1,
    justifyContent: "center" as const,
    alignItems: "center" as const,
  },

  text: {
    marginTop: 15,
    fontSize: 16,
  },
};