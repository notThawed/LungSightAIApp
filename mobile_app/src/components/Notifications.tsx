import { useEffect, useState } from "react";
import { router } from "expo-router";

import { getCurrentUserProfile } from "../lib/user";
import { Button, EmptyState, PageHeader, Screen, StateView } from "./ui";

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
    return <StateView kind="loading" title="Loading notifications" />;
  }

  if (error) {
    return (
      <StateView
        kind="error"
        title="Unable to load notifications"
        message={error}
        actionLabel="Go back"
        onAction={() => router.back()}
      />
    );
  }

  return (
    <Screen>
      <PageHeader
        title="Notifications"
        caption="Updates about your LungSightAI activity."
      />

      <EmptyState
        icon="notifications-off-outline"
        title="No notifications yet"
        message="Notifications are not available on mobile yet. Check your dashboard for current workload."
      />

      <Button
        label="Back to dashboard"
        icon="arrow-back"
        variant="secondary"
        onPress={() => router.back()}
      />
    </Screen>
  );
}
