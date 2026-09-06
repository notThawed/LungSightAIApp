import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { router } from "expo-router";
import { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";

export default function DashboardScreen() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const getSession = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      setSession(session);
      setLoading(false);
    };

    getSession();
  }, []);

  const handleLogout = async () => {
    const { error } = await supabase.auth.signOut();

    if (error) {
      Alert.alert("Logout failed", error.message);
      return;
    }

    router.replace("/login");
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (!session) {
    return (
      <View style={styles.loadingContainer}>
        <Text>Not authenticated.</Text>

        <TouchableOpacity
          style={styles.button}
          onPress={() => router.replace("/login")}
        >
          <Text style={styles.buttonText}>Go to Login</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Dashboard</Text>

      <Text style={styles.welcome}>
        Welcome to LungSight
      </Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Signed in as:</Text>
        <Text style={styles.email}>
          {session.user.email}
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>
          LungSight Overview
        </Text>

        <Text style={styles.description}>
          AI-assisted chest X-ray analysis and patient
          management system.
        </Text>
      </View>

      <TouchableOpacity
        style={styles.logoutButton}
        onPress={handleLogout}
      >
        <Text style={styles.buttonText}>Sign Out</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },

  container: {
    flex: 1,
    padding: 24,
    paddingTop: 70,
    backgroundColor: "#f8fafc",
  },

  title: {
    fontSize: 32,
    fontWeight: "bold",
    marginBottom: 8,
  },

  welcome: {
    fontSize: 18,
    marginBottom: 30,
    color: "#64748b",
  },

  card: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 20,
    marginBottom: 15,
  },

  cardTitle: {
    fontSize: 16,
    fontWeight: "bold",
    marginBottom: 8,
  },

  email: {
    fontSize: 15,
    color: "#2563eb",
  },

  description: {
    fontSize: 14,
    color: "#64748b",
    lineHeight: 21,
  },

  button: {
    marginTop: 20,
    backgroundColor: "#2563eb",
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 10,
  },

  logoutButton: {
    marginTop: 20,
    backgroundColor: "#dc2626",
    height: 52,
    borderRadius: 10,
    justifyContent: "center",
    alignItems: "center",
  },

  buttonText: {
    color: "#fff",
    fontWeight: "bold",
    fontSize: 16,
  },
});