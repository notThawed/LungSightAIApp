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
import { supabase } from "../../lib/supabase";

export default function RadTechDashboard() {
  const [loading, setLoading] = useState(true);
  const [fullName, setFullName] = useState("");
  const [hospitalName, setHospitalName] = useState("");

  useEffect(() => {
    loadUserData();
  }, []);

  const loadUserData = async () => {
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError || !user) {
      console.error("User error:", userError);
      router.replace("/login");
      return;
    }

    const { data: profile, error: profileError } =
      await supabase
        .from("profiles")
        .select("full_name, role, hospital_id")
        .eq("id", user.id)
        .single();

    if (profileError) {
      console.error("Profile error:", profileError);
      setLoading(false);
      return;
    }

    setFullName(profile.full_name ?? "");

    const { data: hospital, error: hospitalError } =
      await supabase
        .from("hospitals")
        .select("name")
        .eq("id", profile.hospital_id)
        .single();

    if (hospitalError) {
      console.error("Hospital error:", hospitalError);
      setLoading(false);
      return;
    }

    setHospitalName(hospital.name);

    setLoading(false);
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
            const { error } = await supabase.auth.signOut();

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

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
        <Text>Loading LungSight...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>

      <Text style={styles.welcome}>
        Welcome, {fullName}
      </Text>

      <Text style={styles.hospital}>
        {hospitalName}
      </Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>
          Role
        </Text>

        <Text style={styles.cardValue}>
          Radiologic Technologist
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>
          Today's Examinations
        </Text>

        <Text style={styles.cardValue}>
          0
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>
          Processing
        </Text>

        <Text style={styles.cardValue}>
          0
        </Text>
      </View>

      <TouchableOpacity
        style={styles.logoutButton}
        onPress={handleLogout}
      >
        <Text style={styles.logoutText}>
          Sign Out
        </Text>
      </TouchableOpacity>

    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },

  container: {
    flex: 1,
    padding: 24,
    paddingTop: 60,
    backgroundColor: "#f8fafc",
  },

  welcome: {
    fontSize: 28,
    fontWeight: "bold",
  },

  hospital: {
    fontSize: 16,
    color: "#64748b",
    marginTop: 8,
    marginBottom: 30,
  },

  card: {
    backgroundColor: "#fff",
    padding: 20,
    borderRadius: 12,
    marginBottom: 15,
  },

  cardTitle: {
    fontSize: 14,
    color: "#64748b",
  },

  cardValue: {
    fontSize: 22,
    fontWeight: "bold",
    marginTop: 8,
  },

  logoutButton: {
    height: 52,
    borderRadius: 10,
    backgroundColor: "#dc2626",
    justifyContent: "center",
    alignItems: "center",
    marginTop: 25,
  },

  logoutText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "bold",
  },
});