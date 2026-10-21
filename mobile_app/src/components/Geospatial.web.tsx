/**
 * Web build of the hospital map screen. react-native-maps has no web
 * implementation, so the browser preview shows the same hospital list
 * without the native map. Device builds use Geospatial.tsx.
 */

import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import Ionicons from "@expo/vector-icons/Ionicons";

import { fetchActiveHospitals, hasValidCoordinates, type Hospital } from "../lib/hospitals";
import { C, Radius, Spacing, Type } from "../constants/theme";
import {
  EmptyState,
  Note,
  PageHeader,
  Screen,
  SectionTitle,
  StatCard,
  StateView,
} from "./ui";

export default function Geospatial() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    fetchActiveHospitals()
      .then((results) => mounted && setHospitals(results))
      .catch((err) =>
        mounted &&
        setError(err instanceof Error ? err.message : "Unable to load hospital locations.")
      )
      .finally(() => mounted && setLoading(false));

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return <StateView kind="loading" title="Loading hospital locations" />;
  }

  if (error) {
    return <StateView kind="error" title="Unable to load the map" message={error} />;
  }

  const mapped = hospitals.filter(hasValidCoordinates);

  return (
    <Screen>
      <PageHeader title="Hospital map" caption="Active LungSightAI partner hospitals." />

      <View style={styles.statsRow}>
        <StatCard icon="business-outline" label="Active hospitals" value={String(hospitals.length)} />
        <StatCard icon="location-outline" label="Mapped locations" value={String(mapped.length)} tone="info" />
      </View>

      <Note tone="info" icon="phone-portrait-outline">
        The interactive map is available in the iOS and Android app.
      </Note>

      <SectionTitle title="Hospital locations" />

      {hospitals.length === 0 ? (
        <EmptyState icon="map-outline" title="No active hospitals yet" />
      ) : (
        hospitals.map((hospital) => (
          <View key={hospital.hospital_id} style={styles.row}>
            <View style={styles.icon}>
              <Ionicons name="business-outline" size={18} color={C.primary} />
            </View>
            <View style={styles.info}>
              <Text style={Type.bodyStrong}>{hospital.hospital_name}</Text>
              <Text style={Type.caption}>{hospital.address}</Text>
            </View>
          </View>
        ))
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  statsRow: {
    flexDirection: "row",
    gap: Spacing[3],
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing[3],
    padding: Spacing[3],
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
  },
  icon: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    backgroundColor: C.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  info: {
    flex: 1,
    gap: 2,
  },
});
