import { useEffect } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { router } from "expo-router";
import { supabase } from "../lib/supabase";

export default function Index() {
  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    const {
      data: { session },
      error,
    } = await supabase.auth.getSession();

    if (error) {
      console.error("Session check error:", error);
      router.replace("/login");
      return;
    }

    if (session) {
      console.log("Existing session found.");
      router.replace("/role-router");
    } else {
      console.log("No existing session.");
      router.replace("/login");
    }
  };

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" />

      <Text style={styles.text}>
        Checking session...
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  text: {
    marginTop: 15,
    fontSize: 16,
  },
});