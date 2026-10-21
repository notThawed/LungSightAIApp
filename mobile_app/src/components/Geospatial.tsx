import { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import MapView, { Callout, Marker } from "react-native-maps";
import Ionicons from "@expo/vector-icons/Ionicons";

import { fetchActiveHospitals, hasValidCoordinates, type Hospital } from "../lib/hospitals";
import { C, Radius, Spacing, Type } from "../constants/theme";
import {
  Button,
  Card,
  EmptyState,
  PageHeader,
  Screen,
  SectionTitle,
  StatCard,
  StateView,
} from "./ui";

const DEFAULT_REGION = {
  latitude: 10.3157,
  longitude: 123.8854,
  latitudeDelta: 0.5,
  longitudeDelta: 0.5,
};

export default function Geospatial() {
  const mapRef = useRef<MapView | null>(null);

  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedHospital, setSelectedHospital] =
    useState<Hospital | null>(null);

  useEffect(() => {
    let mounted = true;

    async function loadHospitals() {
      try {
        const results = await fetchActiveHospitals();

        if (!mounted) return;

        setHospitals(results);

        const mapped = results.filter(hasValidCoordinates);

        if (mapped.length > 0) {
          const coordinates = mapped.map((hospital) => ({
            latitude: Number(hospital.latitude),
            longitude: Number(hospital.longitude),
          }));

          if (coordinates.length === 1) {
            mapRef.current?.animateToRegion(
              {
                ...coordinates[0],
                latitudeDelta: 0.08,
                longitudeDelta: 0.08,
              },
              500
            );
          } else {
            mapRef.current?.fitToCoordinates(coordinates, {
              edgePadding: {
                top: 60,
                right: 60,
                bottom: 60,
                left: 60,
              },
              animated: true,
            });
          }
        }
      } catch (err) {
        console.error("Geospatial loading error:", err);

        if (mounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load hospital locations."
          );
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadHospitals();

    return () => {
      mounted = false;
    };
  }, []);

  const mappedHospitals = hospitals.filter(hasValidCoordinates);

  const unmappedHospitals = hospitals.filter(
    (hospital) => !mappedHospitals.includes(hospital)
  );

  if (loading) {
    return <StateView kind="loading" title="Loading hospital locations" />;
  }

  if (error) {
    return (
      <StateView kind="error" title="Unable to load the map" message={error} />
    );
  }

  const focusHospital = (hospital: Hospital) => {
    setSelectedHospital(hospital);

    mapRef.current?.animateToRegion(
      {
        latitude: Number(hospital.latitude),
        longitude: Number(hospital.longitude),
        latitudeDelta: 0.04,
        longitudeDelta: 0.04,
      },
      500
    );
  };

  return (
    <Screen>
      <PageHeader
        title="Hospital map"
        caption="Active LungSightAI partner hospitals."
      />

      <View style={styles.statsRow}>
        <StatCard
          icon="business-outline"
          label="Active hospitals"
          value={String(hospitals.length)}
        />
        <StatCard
          icon="location-outline"
          label="Mapped locations"
          value={String(mappedHospitals.length)}
          tone="info"
        />
      </View>

      <View style={styles.mapCard}>
        <MapView
          ref={mapRef}
          style={styles.map}
          initialRegion={DEFAULT_REGION}
          onMapReady={() => {
            if (mappedHospitals.length > 1) {
              mapRef.current?.fitToCoordinates(
                mappedHospitals.map((hospital) => ({
                  latitude: Number(hospital.latitude),
                  longitude: Number(hospital.longitude),
                })),
                {
                  edgePadding: {
                    top: 60,
                    right: 60,
                    bottom: 60,
                    left: 60,
                  },
                  animated: false,
                }
              );
            }
          }}
        >
          {mappedHospitals.map((hospital) => (
            <Marker
              key={hospital.hospital_id}
              coordinate={{
                latitude: Number(hospital.latitude),
                longitude: Number(hospital.longitude),
              }}
              pinColor={C.primary}
              onPress={() => setSelectedHospital(hospital)}
            >
              <Callout onPress={() => setSelectedHospital(hospital)}>
                <View style={styles.callout}>
                  <Text style={Type.bodyStrong}>{hospital.hospital_name}</Text>
                  <Text style={Type.caption}>{hospital.address}</Text>
                </View>
              </Callout>
            </Marker>
          ))}
        </MapView>
      </View>

      {selectedHospital && (
        <Card>
          <Text style={Type.label}>SELECTED HOSPITAL</Text>
          <Text style={Type.title}>{selectedHospital.hospital_name}</Text>
          <Text style={Type.body}>{selectedHospital.address}</Text>
          <Text style={Type.caption}>
            {Number(selectedHospital.latitude).toFixed(5)},{" "}
            {Number(selectedHospital.longitude).toFixed(5)}
          </Text>
          <Button
            label="Clear selection"
            variant="secondary"
            onPress={() => setSelectedHospital(null)}
          />
        </Card>
      )}

      <SectionTitle title="Hospital locations" />

      {mappedHospitals.length === 0 ? (
        <EmptyState
          icon="map-outline"
          title="No mapped hospitals yet"
          message="Active hospitals need valid latitude and longitude values to appear on the map."
        />
      ) : (
        mappedHospitals.map((hospital) => (
          <Pressable
            key={hospital.hospital_id}
            accessibilityRole="button"
            accessibilityLabel={`Show ${hospital.hospital_name} on the map`}
            style={({ pressed }) => [
              styles.hospitalRow,
              selectedHospital?.hospital_id === hospital.hospital_id &&
                styles.hospitalRowSelected,
              pressed && styles.pressed,
            ]}
            onPress={() => focusHospital(hospital)}
          >
            <View style={styles.markerIcon}>
              <Ionicons name="business-outline" size={18} color={C.primary} />
            </View>

            <View style={styles.hospitalInfo}>
              <Text style={Type.bodyStrong} numberOfLines={1}>
                {hospital.hospital_name}
              </Text>
              <Text style={Type.caption} numberOfLines={2}>
                {hospital.address}
              </Text>
            </View>

            <Ionicons name="chevron-forward" size={18} color={C.muted} />
          </Pressable>
        ))
      )}

      {unmappedHospitals.length > 0 && (
        <Card>
          <Text style={Type.heading}>Not yet mapped</Text>
          <Text style={Type.caption}>
            These hospitals have missing or invalid coordinates.
          </Text>
          {unmappedHospitals.map((hospital) => (
            <Text key={hospital.hospital_id} style={Type.body}>
              • {hospital.hospital_name}
            </Text>
          ))}
        </Card>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  statsRow: {
    flexDirection: "row",
    gap: Spacing[3],
  },
  mapCard: {
    height: 320,
    borderRadius: Radius.lg,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
  },
  map: {
    flex: 1,
  },
  callout: {
    maxWidth: 220,
    gap: 2,
    padding: 4,
  },
  hospitalRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing[3],
    minHeight: 64,
    padding: Spacing[3],
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: C.border,
    backgroundColor: C.surface,
  },
  hospitalRowSelected: {
    borderColor: C.primary,
    backgroundColor: C.primarySoft,
  },
  pressed: {
    opacity: 0.85,
  },
  markerIcon: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    backgroundColor: C.primarySoft,
    alignItems: "center",
    justifyContent: "center",
  },
  hospitalInfo: {
    flex: 1,
    gap: 2,
  },
});
