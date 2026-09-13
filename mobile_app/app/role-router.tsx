import { useEffect } from "react";
import { ActivityIndicator, Text, View } from "react-native";

import { router } from "expo-router";
import { supabase } from "../lib/supabase";

export default function RoleRouter() {
  useEffect(() => {
    const detectRole = async () => {
      const {
        data: { session },
        error: sessionError,
      } = await supabase.auth.getSession();

      if (sessionError || !session) {
        if (sessionError) {
          console.error("Session error:", sessionError);
        } else {
          console.log("No active session.");
        }
        router.replace("/login");
        return;
      }

      const { data: profile, error: profileError } = await supabase
        .from("profiles")
        .select("role")
        .eq("id", session.user.id)
        .single();

      if (profileError) {
        console.error("Profile error:", profileError);
        await supabase.auth.signOut();
        router.replace("/login");
        return;
      }

      console.log("Logged-in user:", session.user.email);
      console.log("Role:", profile.role);

      switch (profile.role) {
        case "physician":
          router.replace("/physician");
          break;
        case "rad_tech":
          router.replace("/rad_tech");
          break;
        default:
          console.error("Unauthorized mobile role:", profile.role);
          await supabase.auth.signOut();
          router.replace("/login");
      }
    };

    void detectRole();
  }, []);

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" />
      <Text style={styles.text}>Loading LungSight...</Text>
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
