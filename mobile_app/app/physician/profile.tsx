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

export default function PhysicianProfile() {
  const [loading, setLoading] = useState(true);
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("");
  const [hospitalName, setHospitalName] = useState("");

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    const {
      data: { user },
      error: userError,
    } = await supabase.auth.getUser();

    if (userError || !user) {
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
      Alert.alert("Error", "Unable to load profile.");
      setLoading(false);
      return;
    }

    setFullName(profile.full_name ?? "");
    setRole(profile.role ?? "");

    if (profile.hospital_id) {
      const { data: hospital, error: hospitalError } =
        await supabase
          .from("hospitals")
          .select("name")
          .eq("id", profile.hospital_id)
          .single();

      if (!hospitalError && hospital) {
        setHospitalName(hospital.name);
      }
    }

    setLoading(false);
  };

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
        <Text style={styles.loadingText}>
          Loading profile...
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>My Profile</Text>

      <View style={styles.avatar}>
        <Text style={styles.avatarText}>
          {fullName.charAt(0).toUpperCase()}
        </Text>
      </View>

      <Text style={styles.name}>
        Dr. {fullName}
      </Text>

      <Text style={styles.role}>
        Physician
      </Text>

      <View style={styles.card}>
        <Text style={styles.label}>Full Name</Text>
        <Text style={styles.value}>{fullName}</Text>

        <Text style={styles.label}>Role</Text>
        <Text style={styles.value}>{role}</Text>

        <Text style={styles.label}>Hospital</Text>
        <Text style={styles.value}>{hospitalName}</Text>
      </View>

      <TouchableOpacity
        style={styles.backButton}
        onPress={() => router.back()}
      >
        <Text style={styles.backButtonText}>
          Back
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

  loadingText: {
    marginTop: 10,
    color: "#64748b",
  },

  container: {
    flex: 1,
    padding: 24,
    paddingTop: 60,
    backgroundColor: "#f8fafc",
    alignItems: "center",
  },

  title: {
    alignSelf: "flex-start",
    fontSize: 28,
    fontWeight: "bold",
    marginBottom: 30,
  },

  avatar: {
    width: 90,
    height: 90,
    borderRadius: 45,
    backgroundColor: "#2563eb",
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 15,
  },

  avatarText: {
    color: "#fff",
    fontSize: 36,
    fontWeight: "bold",
  },

  name: {
    fontSize: 24,
    fontWeight: "bold",
  },

  role: {
    fontSize: 16,
    color: "#64748b",
    marginTop: 5,
    marginBottom: 30,
  },

  card: {
    width: "100%",
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 20,
  },

  label: {
    fontSize: 13,
    color: "#64748b",
    marginTop: 10,
  },

  value: {
    fontSize: 17,
    fontWeight: "600",
    marginTop: 4,
    marginBottom: 10,
  },

  backButton: {
    width: "100%",
    height: 52,
    borderRadius: 10,
    backgroundColor: "#2563eb",
    justifyContent: "center",
    alignItems: "center",
    marginTop: 20,
  },

  backButtonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "bold",
  },
});