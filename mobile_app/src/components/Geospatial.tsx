import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import Ionicons from "@expo/vector-icons/Ionicons";
import { WebView } from "react-native-webview";

import { supabase } from "../lib/supabase";
import { Palette, Radius, Shadows, Spacing } from "../constants/theme";

type Hospital = {
  hospital_id: string;
  hospital_name: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  contact_number?: string;
  email?: string;
  radiologyExt?: string;
  emergencyExt?: string;
};

type GeospatialProps = {
  role?: string;
};

const SAMPLE_HOSPITALS: Hospital[] = [
  {
    hospital_id: "hosp-pgh-01",
    hospital_name: "Philippine General Hospital (PGH)",
    address: "Taft Avenue, Ermita, Manila, 1000 Metro Manila",
    contact_number: "+63285548400",
    email: "radiology@pgh.gov.ph",
    radiologyExt: "104",
    emergencyExt: "101",
    latitude: 14.5772,
    longitude: 120.9856,
  },
  {
    hospital_id: "hosp-lcp-02",
    hospital_name: "Lung Center of the Philippines",
    address: "Quezon Avenue, Diliman, Quezon City, 1100 Metro Manila",
    contact_number: "+63289246101",
    email: "pulmonary@lcp.gov.ph",
    radiologyExt: "104",
    emergencyExt: "101",
    latitude: 14.6469,
    longitude: 121.045,
  },
  {
    hospital_id: "hosp-slmc-03",
    hospital_name: "St. Luke's Medical Center - Global City",
    address: "32nd Street, Bonifacio Global City, Taguig, 1634 Metro Manila",
    contact_number: "+63287897700",
    email: "info@stlukes.com.ph",
    radiologyExt: "104",
    emergencyExt: "101",
    latitude: 14.5539,
    longitude: 121.0483,
  },
  {
    hospital_id: "hosp-eamc-04",
    hospital_name: "East Avenue Medical Center",
    address: "East Avenue, Diliman, Quezon City, 1100 Metro Manila",
    contact_number: "+63289280611",
    email: "radtech@eamc.doh.gov.ph",
    radiologyExt: "104",
    emergencyExt: "101",
    latitude: 14.6416,
    longitude: 121.0477,
  },
  {
    hospital_id: "hosp-nkti-05",
    hospital_name: "National Kidney and Transplant Institute",
    address: "East Avenue, Quezon City, 1100 Metro Manila",
    contact_number: "+63289810300",
    email: "triage@nkti.gov.ph",
    radiologyExt: "104",
    emergencyExt: "101",
    latitude: 14.6441,
    longitude: 121.0475,
  },
];

/**
 * Generate standalone interactive Leaflet HTML with CartoDB Voyager tiles
 * Runs seamlessly on Android and iOS without requiring a Google Maps API Key or credit card.
 */
function generateLeafletMapHtml(hospitals: Hospital[], selectedId: string | null): string {
  const serialized = JSON.stringify(
    hospitals.map((h) => ({
      id: h.hospital_id,
      name: h.hospital_name,
      address: h.address,
      lat: Number(h.latitude),
      lng: Number(h.longitude),
      isSelected: h.hospital_id === selectedId,
    }))
  );

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body, #map { width: 100%; height: 100%; background: #F1F5F9; }
    .hospital-pin {
      background: #1D4ED8;
      color: #FFFFFF;
      border: 2px solid #FFFFFF;
      border-radius: 50%;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 3px 6px rgba(15, 23, 42, 0.35);
      font-size: 15px;
      cursor: pointer;
      transition: transform 0.2s ease;
    }
    .hospital-pin-selected {
      background: #DC2626 !important;
      transform: scale(1.22);
      box-shadow: 0 4px 10px rgba(220, 38, 38, 0.5);
      z-index: 1000 !important;
    }
    .leaflet-popup-content-wrapper {
      border-radius: 12px;
      padding: 4px;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.16);
    }
    .popup-title {
      font-weight: 800;
      font-size: 13px;
      color: #0F172A;
      margin-bottom: 2px;
    }
    .popup-sub {
      font-size: 11px;
      color: #64748B;
      line-height: 14px;
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <script>
    const hospitals = ${serialized};
    const defaultCenter = [14.5995, 121.0000];

    const map = L.map('map', {
      zoomControl: true,
      attributionControl: false
    }).setView(defaultCenter, 12);

    // CartoDB Voyager tiles (Crisp, modern, Google-Maps style with zero API key requirement)
    L.tileLayer('https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png', {
      maxZoom: 19
    }).addTo(map);

    const markers = {};
    const boundsGroup = [];

    hospitals.forEach(h => {
      if (isNaN(h.lat) || isNaN(h.lng) || h.lat === 0) return;

      const customIcon = L.divIcon({
        className: 'leaflet-custom-marker',
        html: '<div class="hospital-pin ' + (h.isSelected ? 'hospital-pin-selected' : '') + '">🏥</div>',
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        popupAnchor: [0, -18]
      });

      const marker = L.marker([h.lat, h.lng], { icon: customIcon }).addTo(map);
      marker.bindPopup('<div class="popup-title">' + h.name + '</div><div class="popup-sub">' + h.address + '</div>');

      marker.on('click', () => {
        if (window.ReactNativeWebView) {
          window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'SELECT_HOSPITAL', id: h.id }));
        }
      });

      markers[h.id] = marker;
      boundsGroup.push([h.lat, h.lng]);

      if (h.isSelected) {
        marker.openPopup();
      }
    });

    if (boundsGroup.length > 0) {
      map.fitBounds(boundsGroup, { padding: [35, 35], maxZoom: 13 });
    }

    // Handle messages sent from React Native
    window.addEventListener('message', (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'FOCUS' && msg.lat && msg.lng) {
          map.flyTo([msg.lat, msg.lng], 15, { animate: true, duration: 1 });
          if (markers[msg.id]) {
            markers[msg.id].openPopup();
          }
        }
      } catch (err) {}
    });
  </script>
</body>
</html>
  `;
}

export default function Geospatial({ role }: GeospatialProps = {}) {
  const webViewRef = useRef<WebView | null>(null);

  const [hospitals, setHospitals] = useState<Hospital[]>(SAMPLE_HOSPITALS);
  const [loading, setLoading] = useState(true);
  const [selectedHospital, setSelectedHospital] = useState<Hospital | null>(SAMPLE_HOSPITALS[1]); // Default to Lung Center
  const [searchQuery, setSearchQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "mapped" | "unmapped">("all");

  const handleCall = async (phone: string, department: string, ext = "104") => {
    const rawDigits = phone.replace(/[^\d+]/g, "");
    if (!rawDigits) {
      Alert.alert(
        "Direct Contact Unavailable",
        `No primary telephone registered for ${department}.`
      );
      return;
    }

    const telUrl = `tel:${rawDigits}`;
    try {
      const supported = await Linking.canOpenURL(telUrl);
      if (supported) {
        await Linking.openURL(telUrl);
      } else {
        Alert.alert(
          `Direct Extension: ${department}`,
          `Facility Phone: ${phone}\nLocal Extension: Ext. ${ext}\n\n(Native dialing requires a physical device)`
        );
      }
    } catch {
      Alert.alert(
        `Direct Extension: ${department}`,
        `Facility Line: ${phone}\nLocal Extension: Ext. ${ext}`
      );
    }
  };

  useEffect(() => {
    let mounted = true;

    async function loadHospitals() {
      try {
        setLoading(true);

        const { data, error } = await supabase
          .from("hospitals")
          .select("hospital_id, hospital_name, address, latitude, longitude, contact_number, email")
          .order("hospital_name", { ascending: true });

        let validHospitals: Hospital[] = [];

        if (!error && data && data.length > 0) {
          validHospitals = data.map((h) => ({
            hospital_id: String(h.hospital_id),
            hospital_name: String(h.hospital_name || "Unnamed Hospital"),
            address: String(h.address || "No address provided"),
            contact_number: String(h.contact_number || "+639942715118"),
            email: String(h.email || "radiology@hospital.ph"),
            radiologyExt: "104",
            emergencyExt: "101",
            latitude:
              h.latitude !== null && !isNaN(Number(h.latitude))
                ? Number(h.latitude)
                : null,
            longitude:
              h.longitude !== null && !isNaN(Number(h.longitude))
                ? Number(h.longitude)
                : null,
          }));
        } else {
          validHospitals = SAMPLE_HOSPITALS;
        }

        if (mounted) {
          setHospitals(validHospitals);
          if (!selectedHospital && validHospitals.length > 0) {
            setSelectedHospital(validHospitals[0]);
          }
        }
      } catch (err) {
        console.warn("Using sample hospitals dataset:", err);
        if (mounted) {
          setHospitals(SAMPLE_HOSPITALS);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void loadHospitals();

    return () => {
      mounted = false;
    };
  }, []);

  const mappedHospitals = hospitals.filter(
    (h) =>
      h.latitude !== null &&
      h.longitude !== null &&
      Number.isFinite(Number(h.latitude)) &&
      Number.isFinite(Number(h.longitude)) &&
      Math.abs(Number(h.latitude)) <= 90 &&
      Math.abs(Number(h.longitude)) <= 180
  );

  const unmappedHospitals = hospitals.filter(
    (h) => !mappedHospitals.includes(h)
  );

  const searchedHospitals = (
    filter === "mapped"
      ? mappedHospitals
      : filter === "unmapped"
      ? unmappedHospitals
      : hospitals
  ).filter(
    (h) =>
      h.hospital_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      h.address.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const focusHospital = (hospital: Hospital) => {
    setSelectedHospital(hospital);

    if (
      hospital.latitude !== null &&
      hospital.longitude !== null &&
      Number.isFinite(Number(hospital.latitude)) &&
      Number.isFinite(Number(hospital.longitude))
    ) {
      webViewRef.current?.postMessage(
        JSON.stringify({
          type: "FOCUS",
          id: hospital.hospital_id,
          lat: Number(hospital.latitude),
          lng: Number(hospital.longitude),
        })
      );
    }
  };

  const handleMapMessage = (event: any) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === "SELECT_HOSPITAL" && data.id) {
        const found = hospitals.find((h) => h.hospital_id === data.id);
        if (found) {
          setSelectedHospital(found);
        }
      }
    } catch (e) {
      console.warn("Map message parsing error:", e);
    }
  };

  if (loading && hospitals.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={Palette.primary} />
        <Text style={styles.loadingText}>Syncing Hospital Geospatial Data...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView
        style={styles.screen}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.headerRow}>
          <Text style={styles.title}>Geospatial Intelligence</Text>
          <Text style={styles.subtitle}>
            Registered screening centers & PACS deployment network
          </Text>
        </View>

        {/* Search Input */}
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={Palette.slate[400]} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search facility name or district..."
            placeholderTextColor={Palette.slate[400]}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCorrect={false}
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery("")}>
              <Ionicons name="close-circle" size={18} color={Palette.slate[400]} />
            </TouchableOpacity>
          )}
        </View>

        {/* Filter Pills */}
        <View style={styles.filterRow}>
          <TouchableOpacity
            style={[styles.filterPill, filter === "all" && styles.filterPillActive]}
            onPress={() => setFilter("all")}
          >
            <Text style={[styles.filterPillText, filter === "all" && styles.filterPillTextActive]}>
              All ({hospitals.length})
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.filterPill, filter === "mapped" && styles.filterPillActive]}
            onPress={() => setFilter("mapped")}
          >
            <Text style={[styles.filterPillText, filter === "mapped" && styles.filterPillTextActive]}>
              Mapped ({mappedHospitals.length})
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.filterPill, filter === "unmapped" && styles.filterPillActive]}
            onPress={() => setFilter("unmapped")}
          >
            <Text style={[styles.filterPillText, filter === "unmapped" && styles.filterPillTextActive]}>
              Pending GPS ({unmappedHospitals.length})
            </Text>
          </TouchableOpacity>
        </View>

        {/* Interactive Live Map View (CartoDB Voyager Tiles via Leaflet) */}
        {Platform.OS === "web" ? (
          <View style={styles.webMapFallback}>
            <View style={styles.webMapIconWrap}>
              <Ionicons name="map" size={32} color={Palette.primary} />
            </View>
            <Text style={styles.webMapTitle}>Interactive Facility Directory</Text>
            <Text style={styles.webMapSubtitle}>
              Interactive vector map is rendered natively on mobile devices. Tap any facility from the directory below to view coordinates and dial departments directly.
            </Text>
            {selectedHospital && (
              <TouchableOpacity
                style={styles.openExternalMapBtn}
                onPress={() => {
                  const url = `https://www.google.com/maps/search/?api=1&query=${selectedHospital.latitude},${selectedHospital.longitude}`;
                  void Linking.openURL(url);
                }}
                activeOpacity={0.8}
              >
                <Ionicons name="navigate" size={14} color="#FFFFFF" />
                <Text style={styles.openExternalMapText}>
                  View {selectedHospital.hospital_name} on Maps
                </Text>
              </TouchableOpacity>
            )}
          </View>
        ) : (
          <View style={styles.mapCard}>
            <WebView
              ref={webViewRef}
              originWhitelist={["*"]}
              source={{
                html: generateLeafletMapHtml(mappedHospitals, selectedHospital?.hospital_id || null),
              }}
              style={styles.map}
              onMessage={handleMapMessage}
              scrollEnabled={false}
              javaScriptEnabled={true}
              domStorageEnabled={true}
              startInLoadingState={true}
              renderLoading={() => (
                <View style={styles.mapLoadingContainer}>
                  <ActivityIndicator size="small" color={Palette.primary} />
                  <Text style={styles.mapLoadingText}>Loading Live Hospital Map...</Text>
                </View>
              )}
            />
          </View>
        )}

        {/* Selected Hospital Highlight Card */}
        {selectedHospital && (
          <View style={styles.selectedCard}>
            <View style={styles.selectedHeaderRow}>
              <View style={styles.selectedIcon}>
                <Ionicons name="business" size={20} color={Palette.primary} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.selectedHospitalName}>
                  {selectedHospital.hospital_name}
                </Text>
                <Text style={styles.selectedHospitalAddress}>
                  {selectedHospital.address}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.closeSelectedBtn}
                onPress={() => setSelectedHospital(null)}
              >
                <Ionicons name="close" size={18} color={Palette.slate[500]} />
              </TouchableOpacity>
            </View>

            <View style={styles.selectedCoordRow}>
              <View style={styles.coordPill}>
                <Ionicons name="navigate-outline" size={13} color={Palette.primary} />
                <Text style={styles.coordText}>
                  {selectedHospital.latitude?.toFixed(4)}, {selectedHospital.longitude?.toFixed(4)}
                </Text>
              </View>
              <View style={styles.statusPill}>
                <View style={styles.greenDot} />
                <Text style={styles.statusText}>X-Ray Scanner Ready</Text>
              </View>
            </View>

            {/* Direct Department Extension Dialer */}
            <View style={styles.deptDialerContainer}>
              <Text style={styles.deptDialerHeading}>DIRECT DEPARTMENT EXTENSIONS</Text>
              <View style={styles.deptDialerRow}>
                <TouchableOpacity
                  style={styles.deptDialBtn}
                  onPress={() =>
                    handleCall(
                      selectedHospital.contact_number || "+639942715118",
                      `${selectedHospital.hospital_name} Radiology`,
                      "104"
                    )
                  }
                  activeOpacity={0.8}
                >
                  <View style={styles.deptIconBadge}>
                    <Ionicons name="call" size={14} color="#FFFFFF" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.deptLabel}>Radiology Dept</Text>
                    <Text style={styles.deptExt}>Ext. 104 • Reading Room</Text>
                  </View>
                  <View style={styles.deptCallTag}>
                    <Text style={styles.deptCallTagText}>DIAL</Text>
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.deptDialBtn, styles.deptDialBtnTriage]}
                  onPress={() =>
                    handleCall(
                      selectedHospital.contact_number || "+639942715118",
                      `${selectedHospital.hospital_name} Emergency Triage`,
                      "101"
                    )
                  }
                  activeOpacity={0.8}
                >
                  <View style={[styles.deptIconBadge, { backgroundColor: Palette.danger }]}>
                    <Ionicons name="flash" size={14} color="#FFFFFF" />
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.deptLabel}>Emergency Triage</Text>
                    <Text style={styles.deptExt}>Ext. 101 • ICU / ER</Text>
                  </View>
                  <View style={[styles.deptCallTag, { backgroundColor: Palette.dangerLight }]}>
                    <Text style={[styles.deptCallTagText, { color: Palette.danger }]}>DIAL</Text>
                  </View>
                </TouchableOpacity>
              </View>
            </View>

            {/* Get Driving Directions in Native Maps */}
            <TouchableOpacity
              style={styles.directionsBtn}
              onPress={() => {
                if (selectedHospital.latitude && selectedHospital.longitude) {
                  const url = `https://www.google.com/maps/dir/?api=1&destination=${selectedHospital.latitude},${selectedHospital.longitude}`;
                  void Linking.openURL(url);
                }
              }}
              activeOpacity={0.8}
            >
              <Ionicons name="navigate-outline" size={15} color={Palette.primary} />
              <Text style={styles.directionsBtnText}>Get Directions in Google Maps</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Facilities Directory List */}
        <View style={styles.listSection}>
          <Text style={styles.sectionTitle}>Healthcare Facilities Directory</Text>

          {searchedHospitals.length === 0 ? (
            <View style={styles.emptyCard}>
              <Ionicons name="search-outline" size={32} color={Palette.slate[400]} />
              <Text style={styles.emptyTitle}>No facilities found</Text>
              <Text style={styles.emptyText}>
                No facilities match "{searchQuery}". Try a different keyword.
              </Text>
            </View>
          ) : (
            searchedHospitals.map((hospital) => {
              const hasCoordinates =
                hospital.latitude !== null &&
                hospital.longitude !== null &&
                Number.isFinite(Number(hospital.latitude)) &&
                Number.isFinite(Number(hospital.longitude));

              const isSelected = selectedHospital?.hospital_id === hospital.hospital_id;

              return (
                <Pressable
                  key={hospital.hospital_id}
                  style={[
                    styles.card,
                    isSelected && styles.cardSelected,
                    !hasCoordinates && styles.cardDimmed,
                  ]}
                  onPress={() => focusHospital(hospital)}
                >
                  <View style={styles.cardHeader}>
                    <View style={styles.cardIconBox}>
                      <Ionicons
                        name="business"
                        size={18}
                        color={isSelected ? Palette.primary : Palette.slate[600]}
                      />
                    </View>
                    <View style={styles.cardHeaderText}>
                      <Text style={styles.hospitalName} numberOfLines={1}>
                        {hospital.hospital_name}
                      </Text>
                      <Text style={styles.hospitalAddress} numberOfLines={1}>
                        {hospital.address}
                      </Text>
                    </View>
                  </View>

                  <View style={styles.cardFooter}>
                    <View style={styles.coordBox}>
                      <Ionicons name="navigate-outline" size={12} color={Palette.slate[400]} />
                      <Text style={styles.coordLabel}>
                        {hasCoordinates
                          ? `${hospital.latitude?.toFixed(4)}, ${hospital.longitude?.toFixed(4)}`
                          : "Pending GPS Coordinates"}
                      </Text>
                    </View>

                    {hasCoordinates ? (
                      <View style={styles.badgeMapped}>
                        <View style={styles.greenPulseDot} />
                        <Text style={styles.badgeMappedText}>On Live Map</Text>
                      </View>
                    ) : (
                      <View style={styles.badgeUnmapped}>
                        <Text style={styles.badgeUnmappedText}>No GPS</Text>
                      </View>
                    )}
                  </View>
                </Pressable>
              );
            })
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Palette.slate[50],
  },
  screen: {
    flex: 1,
  },
  content: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxxl,
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: Spacing.xxl,
    backgroundColor: Palette.slate[50],
  },
  loadingText: {
    marginTop: Spacing.md,
    color: Palette.slate[500],
    fontSize: 14,
  },
  headerRow: {
    marginBottom: Spacing.md,
  },
  title: {
    fontSize: 24,
    fontWeight: "800",
    color: Palette.slate[900],
    letterSpacing: -0.4,
  },
  subtitle: {
    fontSize: 13,
    color: Palette.slate[500],
    marginTop: 4,
    lineHeight: 18,
  },
  searchBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Palette.white,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    borderRadius: Radius.md,
    paddingHorizontal: 12,
    height: 46,
    marginBottom: Spacing.md,
    ...Shadows.sm,
  },
  searchInput: {
    flex: 1,
    marginLeft: 8,
    fontSize: 14,
    color: Palette.slate[900],
  },
  filterRow: {
    flexDirection: "row",
    gap: 8,
    marginBottom: Spacing.md,
  },
  filterPill: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: Radius.pill,
    backgroundColor: Palette.slate[200],
  },
  filterPillActive: {
    backgroundColor: Palette.primary,
  },
  filterPillText: {
    fontSize: 12,
    fontWeight: "600",
    color: Palette.slate[600],
  },
  filterPillTextActive: {
    color: Palette.white,
  },
  webMapFallback: {
    backgroundColor: Palette.white,
    borderRadius: Radius.xl,
    padding: Spacing.xl,
    alignItems: "center",
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.lg,
    ...Shadows.sm,
  },
  webMapIconWrap: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: Spacing.sm,
  },
  webMapTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: Palette.slate[900],
    marginBottom: 4,
  },
  webMapSubtitle: {
    fontSize: 12,
    color: Palette.slate[500],
    textAlign: "center",
    lineHeight: 18,
    marginBottom: Spacing.md,
  },
  openExternalMapBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: Palette.primary,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: Radius.md,
  },
  openExternalMapText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  mapCard: {
    height: 280,
    borderRadius: Radius.xl,
    overflow: "hidden",
    backgroundColor: Palette.slate[100],
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.lg,
    ...Shadows.md,
  },
  map: {
    flex: 1,
    backgroundColor: "#F1F5F9",
  },
  mapLoadingContainer: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: Palette.slate[100],
    justifyContent: "center",
    alignItems: "center",
    gap: 8,
  },
  mapLoadingText: {
    fontSize: 12,
    fontWeight: "600",
    color: Palette.slate[500],
  },
  selectedCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    borderWidth: 1.5,
    borderColor: Palette.primaryBorder,
    marginBottom: Spacing.lg,
    ...Shadows.md,
  },
  selectedHeaderRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: Spacing.sm,
  },
  selectedIcon: {
    width: 44,
    height: 44,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
    marginRight: Spacing.md,
  },
  selectedHospitalName: {
    fontSize: 16,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  selectedHospitalAddress: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 2,
  },
  closeSelectedBtn: {
    padding: 4,
  },
  selectedCoordRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  coordPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primaryLight,
  },
  coordText: {
    fontSize: 11,
    fontWeight: "700",
    color: Palette.primary,
  },
  statusPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: Radius.sm,
    backgroundColor: Palette.successLight,
  },
  greenDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Palette.success,
  },
  statusText: {
    fontSize: 11,
    fontWeight: "700",
    color: Palette.success,
  },
  deptDialerContainer: {
    borderTopWidth: 1,
    borderTopColor: Palette.slate[100],
    paddingTop: Spacing.md,
  },
  deptDialerHeading: {
    fontSize: 10,
    fontWeight: "800",
    color: Palette.slate[400],
    letterSpacing: 0.8,
    marginBottom: Spacing.sm,
  },
  deptDialerRow: {
    flexDirection: "column",
    gap: Spacing.sm,
  },
  deptDialBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
    padding: Spacing.sm,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryLight,
    borderWidth: 1,
    borderColor: Palette.primaryBorder,
  },
  deptDialBtnTriage: {
    backgroundColor: Palette.dangerLight,
    borderColor: "#FECACA",
  },
  deptIconBadge: {
    width: 32,
    height: 32,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primary,
    justifyContent: "center",
    alignItems: "center",
  },
  deptLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: Palette.slate[900],
  },
  deptExt: {
    fontSize: 11,
    color: Palette.slate[600],
    marginTop: 1,
  },
  deptCallTag: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: Radius.sm,
    backgroundColor: Palette.primary,
  },
  deptCallTagText: {
    fontSize: 10,
    fontWeight: "800",
    color: "#FFFFFF",
  },
  directionsBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    height: 40,
    borderRadius: Radius.md,
    backgroundColor: Palette.slate[100],
    marginTop: Spacing.md,
  },
  directionsBtnText: {
    fontSize: 12,
    fontWeight: "700",
    color: Palette.primary,
  },
  listSection: {
    marginTop: Spacing.xs,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: Palette.slate[900],
    marginBottom: Spacing.md,
  },
  emptyCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.xl,
    padding: Spacing.xl,
    alignItems: "center",
    borderWidth: 1,
    borderColor: Palette.slate[200],
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: Palette.slate[700],
    marginTop: 8,
  },
  emptyText: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 4,
  },
  card: {
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    ...Shadows.sm,
  },
  cardSelected: {
    borderColor: Palette.primary,
    borderWidth: 1.5,
  },
  cardDimmed: {
    opacity: 0.6,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: Spacing.sm,
  },
  cardIconBox: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    backgroundColor: Palette.slate[100],
    justifyContent: "center",
    alignItems: "center",
    marginRight: Spacing.sm,
  },
  cardHeaderText: {
    flex: 1,
  },
  hospitalName: {
    fontSize: 14,
    fontWeight: "700",
    color: Palette.slate[900],
  },
  hospitalAddress: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 1,
  },
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderTopWidth: 1,
    borderTopColor: Palette.slate[100],
    paddingTop: Spacing.xs,
  },
  coordBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  coordLabel: {
    fontSize: 11,
    color: Palette.slate[500],
  },
  badgeMapped: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  greenPulseDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Palette.success,
  },
  badgeMappedText: {
    fontSize: 11,
    fontWeight: "700",
    color: Palette.success,
  },
  badgeUnmapped: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: Radius.sm,
    backgroundColor: Palette.slate[100],
  },
  badgeUnmappedText: {
    fontSize: 10,
    color: Palette.slate[400],
  },
});
