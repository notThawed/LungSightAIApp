import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Text,
  View,
  Pressable,
} from "react-native";
import MapView, { Callout, Marker } from "react-native-maps";

import { supabase } from "../lib/supabase";

type Hospital = {
  hospital_id: string;
  hospital_name: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
};

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
        const { data, error: queryError } = await supabase
          .from("hospitals")
          .select(
            "hospital_id, hospital_name, address, latitude, longitude"
          )
          .eq("is_active", true)
          .order("hospital_name", { ascending: true });

        if (queryError) {
          throw new Error(queryError.message);
        }

        if (!mounted) return;

        const results = (data ?? []) as Hospital[];
        setHospitals(results);

        const mapped = results.filter(
          (hospital) =>
            hospital.latitude !== null &&
            hospital.longitude !== null &&
            Number.isFinite(Number(hospital.latitude)) &&
            Number.isFinite(Number(hospital.longitude)) &&
            Math.abs(Number(hospital.latitude)) <= 90 &&
            Math.abs(Number(hospital.longitude)) <= 180
        );

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

  const mappedHospitals = hospitals.filter(
    (hospital) =>
      hospital.latitude !== null &&
      hospital.longitude !== null &&
      Number.isFinite(Number(hospital.latitude)) &&
      Number.isFinite(Number(hospital.longitude)) &&
      Math.abs(Number(hospital.latitude)) <= 90 &&
      Math.abs(Number(hospital.longitude)) <= 180
  );

  const unmappedHospitals = hospitals.filter(
    (hospital) => !mappedHospitals.includes(hospital)
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#2563eb" />
        <Text style={styles.loadingText}>
          Loading hospital locations...
        </Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorTitle}>
          Unable to Load Map
        </Text>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={styles.content}
    >
      <Text style={styles.title}>Geospatial Mapping</Text>

      <Text style={styles.subtitle}>
        Explore registered LungSight hospital locations.
      </Text>

      <View style={styles.statsRow}>
        <View style={styles.statCard}>
          <Text style={styles.statNumber}>
            {hospitals.length}
          </Text>
          <Text style={styles.statLabel}>
            Active Hospitals
          </Text>
        </View>

        <View style={styles.statCard}>
          <Text style={styles.statNumber}>
            {mappedHospitals.length}
          </Text>
          <Text style={styles.statLabel}>
            Mapped Locations
          </Text>
        </View>
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
              pinColor="#2563eb"
              onPress={() => setSelectedHospital(hospital)}
            >
              <Callout
                onPress={() => setSelectedHospital(hospital)}
              >
                <View style={styles.callout}>
                  <Text style={styles.calloutTitle}>
                    {hospital.hospital_name}
                  </Text>
                  <Text style={styles.calloutAddress}>
                    {hospital.address}
                  </Text>
                  <Text style={styles.calloutHint}>
                    Tap to view details
                  </Text>
                </View>
              </Callout>
            </Marker>
          ))}
        </MapView>
      </View>

      {selectedHospital && (
        <View style={styles.selectedCard}>
          <Text style={styles.sectionTitle}>
            Selected Hospital
          </Text>

          <Text style={styles.hospitalName}>
            {selectedHospital.hospital_name}
          </Text>

          <Text style={styles.address}>
            {selectedHospital.address}
          </Text>

          <Text style={styles.coordinates}>
            Latitude: {selectedHospital.latitude}
          </Text>

          <Text style={styles.coordinates}>
            Longitude: {selectedHospital.longitude}
          </Text>

          <Pressable
            style={styles.clearButton}
            onPress={() => setSelectedHospital(null)}
          >
            <Text style={styles.clearButtonText}>
              Clear Selection
            </Text>
          </Pressable>
        </View>
      )}

      <View style={styles.listSection}>
        <Text style={styles.sectionTitle}>
          Hospital Locations
        </Text>

        {mappedHospitals.length === 0 ? (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyTitle}>
              No mapped hospitals yet
            </Text>
            <Text style={styles.emptyText}>
              Active hospitals need valid latitude and
              longitude values in Supabase to appear
              on the map.
            </Text>
          </View>
        ) : (
          mappedHospitals.map((hospital) => (
            <Pressable
              key={hospital.hospital_id}
              style={styles.hospitalCard}
              onPress={() => {
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
              }}
            >
              <View style={styles.markerIcon}>
                <Text style={styles.markerIconText}>
                  H
                </Text>
              </View>

              <View style={styles.hospitalInfo}>
                <Text style={styles.hospitalName}>
                  {hospital.hospital_name}
                </Text>
                <Text style={styles.address}>
                  {hospital.address}
                </Text>
              </View>

              <Text style={styles.viewText}>View</Text>
            </Pressable>
          ))
        )}
      </View>

      {unmappedHospitals.length > 0 && (
        <View style={styles.listSection}>
          <Text style={styles.sectionTitle}>
            Locations Not Yet Mapped
          </Text>

          <Text style={styles.warningText}>
            These hospitals have missing or invalid
            coordinates.
          </Text>

          {unmappedHospitals.map((hospital) => (
            <View
              key={hospital.hospital_id}
              style={styles.unmappedCard}
            >
              <Text style={styles.hospitalName}>
                {hospital.hospital_name}
              </Text>
              <Text style={styles.address}>
                {hospital.address}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: "#f8fafc",
  },

  content: {
    padding: 20,
    paddingTop: 55,
    paddingBottom: 36,
  },

  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
    backgroundColor: "#f8fafc",
  },

  loadingText: {
    marginTop: 12,
    color: "#64748b",
  },

  title: {
    fontSize: 27,
    fontWeight: "bold",
    color: "#0f172a",
  },

  subtitle: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 21,
    color: "#64748b",
  },

  statsRow: {
    flexDirection: "row",
    gap: 12,
    marginTop: 22,
    marginBottom: 18,
  },

  statCard: {
    flex: 1,
    padding: 16,
    borderRadius: 12,
    backgroundColor: "#ffffff",
    elevation: 2,
  },

  statNumber: {
    fontSize: 26,
    fontWeight: "bold",
    color: "#2563eb",
  },

  statLabel: {
    marginTop: 4,
    fontSize: 12,
    color: "#64748b",
  },

  mapCard: {
    overflow: "hidden",
    borderRadius: 14,
    backgroundColor: "#e2e8f0",
    elevation: 2,
  },

  map: {
    width: "100%",
    height: 340,
  },

  callout: {
    width: 200,
    padding: 6,
  },

  calloutTitle: {
    fontSize: 14,
    fontWeight: "bold",
    color: "#0f172a",
  },

  calloutAddress: {
    marginTop: 4,
    fontSize: 12,
    color: "#64748b",
  },

  calloutHint: {
    marginTop: 6,
    fontSize: 11,
    color: "#2563eb",
  },

  selectedCard: {
    marginTop: 18,
    padding: 18,
    borderRadius: 12,
    backgroundColor: "#ffffff",
    elevation: 2,
  },

  listSection: {
    marginTop: 26,
  },

  sectionTitle: {
    fontSize: 19,
    fontWeight: "bold",
    color: "#0f172a",
    marginBottom: 12,
  },

  hospitalCard: {
    flexDirection: "row",
    alignItems: "center",
    padding: 14,
    marginBottom: 10,
    borderRadius: 12,
    backgroundColor: "#ffffff",
    elevation: 1,
  },

  markerIcon: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: "#dbeafe",
    justifyContent: "center",
    alignItems: "center",
    marginRight: 12,
  },

  markerIconText: {
    fontSize: 17,
    fontWeight: "bold",
    color: "#2563eb",
  },

  hospitalInfo: {
    flex: 1,
  },

  hospitalName: {
    fontSize: 15,
    fontWeight: "bold",
    color: "#0f172a",
  },

  address: {
    marginTop: 5,
    fontSize: 12,
    lineHeight: 18,
    color: "#64748b",
  },

  viewText: {
    marginLeft: 8,
    fontSize: 13,
    fontWeight: "600",
    color: "#2563eb",
  },

  coordinates: {
    marginTop: 8,
    fontSize: 13,
    color: "#475569",
  },

  clearButton: {
    alignSelf: "flex-start",
    marginTop: 16,
    paddingVertical: 9,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: "#eff6ff",
  },

  clearButtonText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#2563eb",
  },

  emptyCard: {
    padding: 20,
    borderRadius: 12,
    backgroundColor: "#ffffff",
  },

  emptyTitle: {
    fontSize: 16,
    fontWeight: "bold",
    color: "#0f172a",
  },

  emptyText: {
    marginTop: 8,
    fontSize: 14,
    lineHeight: 21,
    color: "#64748b",
  },

  warningText: {
    marginBottom: 12,
    fontSize: 13,
    lineHeight: 20,
    color: "#92400e",
  },

  unmappedCard: {
    padding: 14,
    marginBottom: 10,
    borderRadius: 12,
    backgroundColor: "#fff7ed",
  },

  errorTitle: {
    fontSize: 18,
    fontWeight: "bold",
    color: "#b91c1c",
    marginBottom: 8,
  },

  errorText: {
    textAlign: "center",
    color: "#64748b",
  },
});
