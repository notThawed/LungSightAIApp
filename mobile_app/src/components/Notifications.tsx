import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { getCurrentUserProfile } from "../lib/user";

export default function Notifications() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    const loadProfile = async () => {
      try {
        await getCurrentUserProfile();
      } catch (err) {
        console.error("Notifications profile error:", err);

        if (mounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load notifications."
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadProfile();

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={styles.loadingText}>
          Loading notifications...
        </Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorTitle}>
          Unable to Load Notifications
        </Text>

        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Notifications</Text>

      <Text style={styles.subtitle}>
        Stay updated on your LungSight activities.
      </Text>

      <View style={styles.card}>
        <Text style={styles.emptyTitle}>
          No notifications yet
        </Text>

        <Text style={styles.emptyText}>
          New updates and alerts will appear here when
          notification functionality is implemented.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: "#f8fafc",
  },

  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: "#64748b",
  },

  container: {
    flex: 1,
    padding: 24,
    paddingTop: 60,
    backgroundColor: "#f8fafc",
  },

  title: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#0f172a",
  },

  subtitle: {
    marginTop: 8,
    fontSize: 15,
    color: "#64748b",
  },

  card: {
    marginTop: 28,
    padding: 24,
    borderRadius: 12,
    backgroundColor: "#ffffff",
    alignItems: "center",
    elevation: 2,
  },

  emptyTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#0f172a",
  },

  emptyText: {
    marginTop: 10,
    fontSize: 14,
    lineHeight: 21,
    color: "#64748b",
    textAlign: "center",
  },

  errorTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#b91c1c",
    marginBottom: 8,
  },

  errorText: {
    color: "#64748b",
    textAlign: "center",
  },
});
