import { useCallback, useEffect, useState, useMemo } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { router } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";

import { supabase } from "../lib/supabase";
import { getCurrentUserProfile, UserProfile } from "../lib/user";
import {
  getLiveDashboardData,
  LiveClinicalCase,
  DashboardSummary,
  getCaseWorkflowSteps,
  ScanWorkflowStep,
} from "../lib/scans";
import { Palette, Radius, Shadows, Spacing, Typography } from "../constants/theme";

type DashboardRole = "staff" | "radiologist" | "radiologic_technologist";

interface DashboardProps {
  role?: DashboardRole;
}

export default function Dashboard({ role }: DashboardProps) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [cases, setCases] = useState<LiveClinicalCase[]>([]);
  const [summary, setSummary] = useState<DashboardSummary>({
    totalScans: 0,
    pendingReviews: 0,
    normalScans: 0,
    criticalScans: 0,
    scansCompletedToday: 0,
    pendingSignOffs: 0,
    highRiskFlagsLast24h: 0,
  });
  const [filter, setFilter] = useState<"all" | "critical" | "normal">("all");
  const [selectedCase, setSelectedCase] = useState<LiveClinicalCase | null>(null);

  // Read-only X-Ray Zoom & Contrast State
  const [zoomScale, setZoomScale] = useState(1);
  const [contrastFilter, setContrastFilter] = useState<"standard" | "high" | "inverted">("standard");

  const activeRole = role ?? user?.role;

  const loadDashboard = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const profile = await getCurrentUserProfile();

      if (
        profile.role !== "radiologist" &&
        profile.role !== "radiologic_technologist" &&
        profile.role !== "staff"
      ) {
        await supabase.auth.signOut();
        router.replace("/login");
        return;
      }

      setUser(profile);

      // Fetch live scan cases and metrics from Supabase
      const liveData = await getLiveDashboardData(profile.hospitalId);
      setCases(liveData.cases);
      setSummary(liveData.summary);
    } catch (error) {
      console.error("Dashboard error:", error);

      if (isRefresh) {
        Alert.alert(
          "Refresh failed",
          "Unable to refresh your dashboard. Please check your connection and try again."
        );
      } else {
        Alert.alert("Error", "Unable to load your dashboard.");
        router.replace("/login");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const onRefresh = useCallback(() => {
    void loadDashboard(true);
  }, [loadDashboard]);

  const handleNotifications = () => {
    if (activeRole === "radiologist") {
      router.push("/physician/notifications");
    } else if (activeRole === "radiologic_technologist") {
      router.push("/rad_tech/notifications");
    } else {
      router.push("/staff/notifications");
    }
  };

  const handleGeospatial = () => {
    if (activeRole === "radiologist") {
      router.push("/physician/geospatial");
    } else if (activeRole === "radiologic_technologist") {
      router.push("/rad_tech/geospatial");
    } else {
      router.push("/staff/geospatial");
    }
  };

  const handleTracker = () => {
    if (activeRole === "radiologist") {
      router.push("/physician/tracker");
    } else if (activeRole === "radiologic_technologist") {
      router.push("/rad_tech/tracker");
    } else {
      router.push("/staff/tracker");
    }
  };

  const handleProfile = () => {
    if (activeRole === "radiologist") {
      router.push("/physician/profile");
    } else if (activeRole === "radiologic_technologist") {
      router.push("/rad_tech/profile");
    } else {
      router.push("/staff/profile");
    }
  };

  const criticalPagerAlert = useMemo(() => {
    return (
      cases.find(
        (c) =>
          (c.status === "critical" || c.hasHighRiskFlag) &&
          (c.confidenceRaw >= 0.8 || c.confidenceRaw === 0)
      ) ||
      cases.find((c) => c.status === "critical") ||
      null
    );
  }, [cases]);

  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      if (filter === "critical") return c.status === "critical" || c.status === "warning";
      if (filter === "normal") return c.status === "normal";
      return true;
    });
  }, [cases, filter]);

  const unreadAlertsCount = useMemo(() => {
    return cases.filter((c) => c.status === "critical" || c.status === "warning").length;
  }, [cases]);

  if (loading || !user) {
    return (
      <View style={styles.center}>
        <StatusBar style="dark" />
        <View style={styles.loadingLogoBadge}>
          <Ionicons name="pulse" size={32} color="#FFFFFF" />
        </View>
        <ActivityIndicator size="large" color={Palette.primary} style={{ marginTop: 16 }} />
        <Text style={styles.loadingText}>Syncing Clinical Worklist...</Text>
      </View>
    );
  }

  const isPhysician = user.role === "radiologist";
  const isRadTech = user.role === "radiologic_technologist";
  const displayName = isPhysician ? `Dr. ${user.fullName}` : user.fullName;

  const roleTitle = isPhysician
    ? "Radiologist / Physician"
    : isRadTech
    ? "Radiologic Technologist"
    : "Clinical Support Staff";

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            colors={[Palette.primary]}
            tintColor={Palette.primary}
            progressBackgroundColor="#FFFFFF"
          />
        }
      >
        {/* App Top Bar */}
        <View style={styles.header}>
          <View style={styles.brandRow}>
            <View style={styles.brandIcon}>
              <Ionicons name="pulse" size={22} color="#FFFFFF" />
            </View>
            <View>
              <Text style={styles.brand}>
                LungSight <Text style={styles.brandAI}>AI</Text>
              </Text>
              <Text style={styles.brandSubtitle}>Clinical Decision Support</Text>
            </View>
          </View>

          <TouchableOpacity
            accessibilityRole="button"
            accessibilityLabel="Open notifications"
            style={styles.bellButton}
            onPress={handleNotifications}
            activeOpacity={0.7}
          >
            <Ionicons name="notifications-outline" size={22} color={Palette.slate[900]} />
            {unreadAlertsCount > 0 && (
              <View style={styles.notificationBadge}>
                <Text style={styles.notificationBadgeText}>
                  {unreadAlertsCount > 9 ? "9+" : unreadAlertsCount}
                </Text>
              </View>
            )}
          </TouchableOpacity>
        </View>

        {/* 2. 🚨 Critical Case Pager / High-Priority Alert Banner */}
        {criticalPagerAlert && (
          <TouchableOpacity
            style={styles.pagerBanner}
            onPress={() => setSelectedCase(criticalPagerAlert)}
            activeOpacity={0.88}
          >
            <View style={styles.pagerPillRow}>
              <View style={styles.pagerPulsingDot} />
              <Text style={styles.pagerPillText}>CRITICAL CASE PAGER • ICU / ER PRIORITY</Text>
            </View>
            <View style={styles.pagerContent}>
              <View style={styles.pagerIconWrap}>
                <Ionicons name="warning" size={22} color="#FFFFFF" />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.pagerTitle}>
                  High-Risk Finding: {criticalPagerAlert.finding}
                </Text>
                <Text style={styles.pagerSubtitle}>
                  Patient {criticalPagerAlert.patientName} ({criticalPagerAlert.patientId}) • AI Conf: {criticalPagerAlert.confidence}
                </Text>
                <View style={styles.pagerActionLink}>
                  <Text style={styles.pagerActionText}>Inspect CXR directly on rounds</Text>
                  <Ionicons name="arrow-forward" size={12} color="#FFFFFF" />
                </View>
              </View>
            </View>
          </TouchableOpacity>
        )}

        {/* Hero Practitioner Card */}
        <View style={styles.welcomeCard}>
          <View style={styles.welcomeTopRow}>
            <View style={styles.avatarCircle}>
              <Text style={styles.avatarInitials}>
                {(user.fullName?.charAt(0) || "U").toUpperCase()}
              </Text>
            </View>
            <View style={styles.welcomeNameCol}>
              <Text style={styles.welcomeEyebrow}>CURRENT PRACTITIONER</Text>
              <Text style={styles.welcomeName} numberOfLines={1}>
                {displayName}
              </Text>
            </View>
          </View>

          <View style={styles.hospitalRow}>
            <Ionicons name="business" size={15} color={Palette.primary} />
            <Text style={styles.hospitalText} numberOfLines={1}>
              {user.hospitalName || "Registered Medical Center"}
            </Text>
          </View>

          <View style={styles.roleBadgeRow}>
            <View style={styles.roleBadge}>
              <Ionicons
                name={isPhysician ? "medkit" : isRadTech ? "scan" : "people"}
                size={14}
                color={Palette.primary}
              />
              <Text style={styles.roleText}>{roleTitle}</Text>
            </View>

            <View style={styles.statusOnlineBadge}>
              <View style={styles.greenPulseDot} />
              <Text style={styles.statusOnlineText}>DenseNet-121 Active</Text>
            </View>
          </View>
        </View>

        {/* Real-time KPI Metric Highlights */}
        <View style={styles.kpiBanner}>
          <View style={styles.kpiItem}>
            <Ionicons name="speedometer-outline" size={16} color={Palette.primary} />
            <Text style={styles.kpiValue}>180ms</Text>
            <Text style={styles.kpiLabel}>Inference</Text>
          </View>
          <View style={styles.kpiSeparator} />
          <View style={styles.kpiItem}>
            <Ionicons name="checkmark-done-circle-outline" size={16} color={Palette.success} />
            <Text style={styles.kpiValue}>96.4%</Text>
            <Text style={styles.kpiLabel}>Sensitivity</Text>
          </View>
          <View style={styles.kpiSeparator} />
          <View style={styles.kpiItem}>
            <Ionicons name="server-outline" size={16} color={Palette.slate[600]} />
            <Text style={styles.kpiValue}>Supabase</Text>
            <Text style={styles.kpiLabel}>Connected</Text>
          </View>
        </View>

        {/* Unified Live Facility Metrics (from Supabase) */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Facility Screening Metrics</Text>
          <View style={styles.liveBadge}>
            <Text style={styles.liveBadgeText}>LIVE SUPABASE</Text>
          </View>
        </View>

        <View style={styles.statsGrid}>
          <StatCard
            icon="calendar"
            iconColor={Palette.primary}
            iconBg={Palette.primaryLight}
            label="Scans Today"
            value={summary.scansCompletedToday.toString()}
            hint="Hospital facility today"
          />
          <StatCard
            icon="time"
            iconColor={Palette.warning}
            iconBg={Palette.warningLight}
            label="Pending Review"
            value={summary.pendingReviews.toString()}
            hint="Awaiting physician"
          />
          <StatCard
            icon="warning"
            iconColor={Palette.danger}
            iconBg={Palette.dangerLight}
            label="High-Risk (24h)"
            value={summary.highRiskFlagsLast24h.toString()}
            hint="Pneumonia flags"
          />
          <StatCard
            icon="checkmark-circle"
            iconColor={Palette.success}
            iconBg={Palette.successLight}
            label="Normal / Cleared"
            value={summary.normalScans.toString()}
            hint="Negative findings"
          />
        </View>

        {/* Live Worklist Section */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Live Examination Queue</Text>
          <Text style={styles.viewAllText}>Tap scan to inspect</Text>
        </View>

        {/* Filters */}
        <View style={styles.filterRow}>
          <TouchableOpacity
            style={[styles.filterChip, filter === "all" && styles.filterChipActive]}
            onPress={() => setFilter("all")}
          >
            <Text style={[styles.filterChipText, filter === "all" && styles.filterChipTextActive]}>
              All ({cases.length})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.filterChip, filter === "critical" && styles.filterChipActive]}
            onPress={() => setFilter("critical")}
          >
            <Text style={[styles.filterChipText, filter === "critical" && styles.filterChipTextActive]}>
              Pneumonia ({summary.criticalScans})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.filterChip, filter === "normal" && styles.filterChipActive]}
            onPress={() => setFilter("normal")}
          >
            <Text style={[styles.filterChipText, filter === "normal" && styles.filterChipTextActive]}>
              Cleared ({summary.normalScans})
            </Text>
          </TouchableOpacity>
        </View>

        {/* Worklist Card / List */}
        <View style={styles.worklistCard}>
          {filteredCases.length === 0 ? (
            <View style={styles.emptyWorklist}>
              <Ionicons name="folder-open-outline" size={36} color={Palette.slate[400]} />
              <Text style={styles.emptyWorklistTitle}>No examination records</Text>
              <Text style={styles.emptyWorklistText}>
                {filter === "all"
                  ? "No X-ray examination records have been submitted for your facility yet."
                  : `No ${filter} scans currently match this filter.`}
              </Text>
            </View>
          ) : (
            filteredCases.map((item, index) => (
              <View key={item.caseId}>
                <TouchableOpacity
                  style={styles.worklistItem}
                  onPress={() => setSelectedCase(item)}
                  activeOpacity={0.7}
                >
                  <View style={styles.worklistLeft}>
                    <View style={styles.caseIdRow}>
                      <Text style={styles.caseIdText}>{item.caseId}</Text>
                      <Text style={styles.caseTimeText}>• {item.time}</Text>
                    </View>
                    <Text style={styles.patientNameText} numberOfLines={1}>
                      {item.patientName}
                    </Text>
                    <Text style={styles.patientDemographicsText}>{item.demographics}</Text>
                  </View>

                  <View style={styles.worklistRight}>
                    <View
                      style={[
                        styles.findingBadge,
                        item.status === "critical" && styles.badgeCritical,
                        item.status === "normal" && styles.badgeNormal,
                        item.status === "warning" && styles.badgeWarning,
                        item.status === "pending" && styles.badgePending,
                      ]}
                    >
                      <Text
                        style={[
                          styles.findingBadgeText,
                          item.status === "critical" && styles.textCritical,
                          item.status === "normal" && styles.textNormal,
                          item.status === "warning" && styles.textWarning,
                          item.status === "pending" && styles.textPending,
                        ]}
                      >
                        {item.finding}
                      </Text>
                    </View>
                    <Text style={styles.confidenceText}>
                      {item.confidence !== "Pending" ? `Conf: ${item.confidence}` : "Awaiting AI"}
                    </Text>
                  </View>
                </TouchableOpacity>
                {index < filteredCases.length - 1 && <View style={styles.divider} />}
              </View>
            ))
          )}
        </View>

        {/* Clinical Disclaimer */}
        <View style={styles.infoCard}>
          <View style={styles.infoIcon}>
            <Ionicons name="shield-checkmark" size={22} color={Palette.primary} />
          </View>
          <View style={styles.infoTextWrap}>
            <Text style={styles.infoTitle}>Clinical Companion App</Text>
            <Text style={styles.infoText}>
              LungSight AI assists radiologic screening. All AI-generated
              predictions require confirmatory review by a certified physician.
            </Text>
          </View>
        </View>
      </ScrollView>

      {/* Case Details Inspection Modal */}
      {selectedCase && (
        <Modal
          animationType="slide"
          transparent
          visible={!!selectedCase}
          onRequestClose={() => setSelectedCase(null)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <View>
                  <Text style={styles.modalTitle}>{selectedCase.caseId}</Text>
                  <Text style={styles.modalSubtitle}>{selectedCase.ward}</Text>
                </View>
                <TouchableOpacity
                  style={styles.modalCloseBtn}
                  onPress={() => setSelectedCase(null)}
                >
                  <Ionicons name="close" size={20} color={Palette.slate[600]} />
                </TouchableOpacity>
              </View>

              <ScrollView showsVerticalScrollIndicator={false}>
                {/* 4. 🖼️ Read-Only X-Ray Preview with Pinch-to-Zoom & Contrast Toggle */}
                {selectedCase.imageUrl ? (
                  <View style={styles.cxrViewerContainer}>
                    {/* Contrast & Zoom Control Bar */}
                    <View style={styles.cxrControlsHeader}>
                      <View style={styles.cxrPillsRow}>
                        <TouchableOpacity
                          style={[
                            styles.cxrModePill,
                            contrastFilter === "standard" && styles.cxrModePillActive,
                          ]}
                          onPress={() => setContrastFilter("standard")}
                        >
                          <Text
                            style={[
                              styles.cxrModePillText,
                              contrastFilter === "standard" && styles.cxrModePillTextActive,
                            ]}
                          >
                            Standard
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          style={[
                            styles.cxrModePill,
                            contrastFilter === "high" && styles.cxrModePillActive,
                          ]}
                          onPress={() => setContrastFilter("high")}
                        >
                          <Text
                            style={[
                              styles.cxrModePillText,
                              contrastFilter === "high" && styles.cxrModePillTextActive,
                            ]}
                          >
                            High Contrast
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          style={[
                            styles.cxrModePill,
                            contrastFilter === "inverted" && styles.cxrModePillActive,
                          ]}
                          onPress={() => setContrastFilter("inverted")}
                        >
                          <Text
                            style={[
                              styles.cxrModePillText,
                              contrastFilter === "inverted" && styles.cxrModePillTextActive,
                            ]}
                          >
                            Bone Filter
                          </Text>
                        </TouchableOpacity>
                      </View>

                      {/* Zoom Scale Buttons */}
                      <View style={styles.cxrZoomRow}>
                        <TouchableOpacity
                          style={[styles.cxrZoomBtn, zoomScale === 1 && styles.cxrZoomBtnActive]}
                          onPress={() => setZoomScale(1)}
                        >
                          <Text style={styles.cxrZoomBtnText}>1x</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={[styles.cxrZoomBtn, zoomScale === 1.5 && styles.cxrZoomBtnActive]}
                          onPress={() => setZoomScale(1.5)}
                        >
                          <Text style={styles.cxrZoomBtnText}>1.5x</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={[styles.cxrZoomBtn, zoomScale === 2 && styles.cxrZoomBtnActive]}
                          onPress={() => setZoomScale(2)}
                        >
                          <Text style={styles.cxrZoomBtnText}>2x</Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={styles.cxrZoomBtn}
                          onPress={() => {
                            setZoomScale(1);
                            setContrastFilter("standard");
                          }}
                        >
                          <Ionicons name="refresh" size={12} color={Palette.slate[600]} />
                        </TouchableOpacity>
                      </View>
                    </View>

                    {/* Zoomable Image View */}
                    <ScrollView
                      horizontal
                      nestedScrollEnabled
                      showsHorizontalScrollIndicator={false}
                      contentContainerStyle={{ flexGrow: 1, justifyContent: "center", alignItems: "center" }}
                    >
                      <ScrollView
                        nestedScrollEnabled
                        maximumZoomScale={3}
                        minimumZoomScale={1}
                        centerContent
                        showsVerticalScrollIndicator={false}
                      >
                        <View
                          style={[
                            styles.cxrCanvas,
                            contrastFilter === "inverted" && styles.canvasInverted,
                            contrastFilter === "high" && styles.canvasHighContrast,
                          ]}
                        >
                          <Image
                            source={{ uri: selectedCase.imageUrl }}
                            style={[
                              styles.imagePreview,
                              {
                                transform: [{ scale: zoomScale }],
                                opacity: contrastFilter === "high" ? 0.95 : 1,
                              },
                            ]}
                            resizeMode="contain"
                          />
                        </View>
                      </ScrollView>
                    </ScrollView>

                    <View style={styles.imageBadge}>
                      <Ionicons name="scan" size={12} color="#FFFFFF" />
                      <Text style={styles.imageBadgeText}>
                        Chest PA View • {contrastFilter.toUpperCase()} • {zoomScale}x
                      </Text>
                    </View>
                  </View>
                ) : null}

                {/* Finding Highlight Card */}
                <View
                  style={[
                    styles.findingHeroCard,
                    selectedCase.status === "critical" && styles.findingHeroCritical,
                    selectedCase.status === "normal" && styles.findingHeroNormal,
                    selectedCase.status === "warning" && styles.findingHeroWarning,
                    selectedCase.status === "pending" && styles.findingHeroPending,
                  ]}
                >
                  <Ionicons
                    name={
                      selectedCase.status === "critical"
                        ? "alert-circle"
                        : selectedCase.status === "normal"
                        ? "checkmark-circle"
                        : selectedCase.status === "warning"
                        ? "warning"
                        : "time"
                    }
                    size={28}
                    color={
                      selectedCase.status === "critical"
                        ? Palette.danger
                        : selectedCase.status === "normal"
                        ? Palette.success
                        : selectedCase.status === "warning"
                        ? Palette.warning
                        : Palette.slate[600]
                    }
                  />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.findingHeroTitle}>{selectedCase.finding}</Text>
                    <Text style={styles.findingHeroConfidence}>
                      AI Confidence Score: {selectedCase.confidence}
                    </Text>
                  </View>
                </View>

                {/* Case Parameters */}
                <View style={styles.caseDetailsCard}>
                  <DetailItem label="Patient Name" value={selectedCase.patientName} />
                  <DetailItem label="Patient ID" value={selectedCase.patientId} />
                  <DetailItem label="Demographics" value={selectedCase.demographics} />
                  <DetailItem label="Clinical Indication" value={selectedCase.ward} />
                  <DetailItem label="Suspected Region" value={selectedCase.infiltrateLocation} />
                  <DetailItem label="Radiologic Notes" value={selectedCase.notes} />
                </View>

                {/* 4-Step Ward Rounds Status in Modal */}
                <View style={styles.modalTrackerSection}>
                  <Text style={styles.modalTrackerHeading}>WARD ROUNDS SCAN STATUS</Text>
                  <View style={styles.modalStepperList}>
                    {getCaseWorkflowSteps(selectedCase).map((st, idx, arr) => (
                      <View key={st.stepNumber} style={styles.modalStepRow}>
                        <View style={styles.modalStepLeftCol}>
                          <View
                            style={[
                              styles.modalStepDot,
                              st.completed && styles.stepperDotCompleted,
                              st.current && styles.stepperDotCurrent,
                            ]}
                          >
                            {st.completed ? (
                              <Ionicons name="checkmark" size={10} color="#FFFFFF" />
                            ) : (
                              <Text
                                style={[
                                  styles.stepperDotNum,
                                  st.current && styles.stepperDotNumCurrent,
                                  { fontSize: 10 },
                                ]}
                              >
                                {st.stepNumber}
                              </Text>
                            )}
                          </View>
                          {idx < arr.length - 1 && (
                            <View
                              style={[
                                styles.modalStepLine,
                                st.completed && styles.stepperLineCompleted,
                              ]}
                            />
                          )}
                        </View>
                        <View style={styles.modalStepRightCol}>
                          <View style={styles.modalStepTitleRow}>
                            <Text
                              style={[
                                styles.modalStepTitle,
                                st.completed && styles.stepperStepTitleCompleted,
                              ]}
                            >
                              {st.title}
                            </Text>
                            <Text style={styles.modalStepTime}>{st.timestamp}</Text>
                          </View>
                          <Text style={styles.modalStepSub}>{st.subtitle}</Text>
                        </View>
                      </View>
                    ))}
                  </View>
                </View>

                {/* Action Button */}
                <View style={styles.modalActionRow}>
                  <TouchableOpacity
                    style={styles.signOffButton}
                    onPress={() => {
                      Alert.alert(
                        "Clinical Review",
                        `Full diagnostic evaluation and formal report signing can be completed on your desktop workstation.`
                      );
                      setSelectedCase(null);
                    }}
                  >
                    <Ionicons name="checkmark-done" size={18} color="#FFFFFF" />
                    <Text style={styles.signOffButtonText}>Review on Workstation</Text>
                  </TouchableOpacity>
                </View>
              </ScrollView>
            </View>
          </View>
        </Modal>
      )}
    </SafeAreaView>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailItemRow}>
      <Text style={styles.detailItemLabel}>{label}</Text>
      <Text style={styles.detailItemValue}>{value}</Text>
    </View>
  );
}

function StatCard({
  icon,
  iconColor,
  iconBg,
  label,
  value,
  hint,
}: {
  icon: React.ComponentProps<typeof Ionicons>["name"];
  iconColor: string;
  iconBg: string;
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <View style={styles.statCard}>
      <View style={[styles.statIcon, { backgroundColor: iconBg }]}>
        <Ionicons name={icon} size={20} color={iconColor} />
      </View>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statTitle}>{label}</Text>
      <Text style={styles.statHint}>{hint}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: Palette.slate[50],
  },
  container: {
    flex: 1,
  },
  content: {
    paddingHorizontal: Spacing.lg,
    paddingTop: Spacing.sm,
    paddingBottom: Spacing.xxxl,
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: Palette.slate[50],
    padding: Spacing.xxl,
  },
  loadingLogoBadge: {
    width: 64,
    height: 64,
    borderRadius: Radius.xl,
    backgroundColor: Palette.primary,
    justifyContent: "center",
    alignItems: "center",
    ...Shadows.md,
  },
  loadingText: {
    fontSize: 14,
    color: Palette.slate[500],
    fontWeight: "600",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: Spacing.lg,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },
  brandIcon: {
    width: 44,
    height: 44,
    borderRadius: Radius.md,
    backgroundColor: Palette.primary,
    justifyContent: "center",
    alignItems: "center",
    ...Shadows.md,
  },
  brand: {
    fontSize: 20,
    fontWeight: "800",
    color: Palette.slate[900],
    letterSpacing: -0.3,
  },
  brandAI: {
    color: Palette.primary,
    fontWeight: "900",
  },
  brandSubtitle: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 1,
  },
  bellButton: {
    width: 42,
    height: 42,
    borderRadius: Radius.md,
    backgroundColor: Palette.white,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    justifyContent: "center",
    alignItems: "center",
    position: "relative",
    ...Shadows.sm,
  },
  notificationBadge: {
    position: "absolute",
    top: 5,
    right: 5,
    minWidth: 17,
    height: 17,
    borderRadius: 9,
    backgroundColor: Palette.danger,
    borderWidth: 1.5,
    borderColor: Palette.white,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 2,
  },
  notificationBadgeText: {
    fontSize: 9,
    fontWeight: "800",
    color: "#FFFFFF",
    lineHeight: 11,
  },
  welcomeCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    ...Shadows.md,
    marginBottom: Spacing.md,
  },
  welcomeTopRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },
  avatarCircle: {
    width: 48,
    height: 48,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryLight,
    borderWidth: 1.5,
    borderColor: Palette.primaryBorder,
    justifyContent: "center",
    alignItems: "center",
  },
  avatarInitials: {
    fontSize: 20,
    fontWeight: "800",
    color: Palette.primary,
  },
  welcomeNameCol: {
    flex: 1,
  },
  welcomeEyebrow: {
    ...Typography.label,
  },
  welcomeName: {
    fontSize: 18,
    fontWeight: "700",
    color: Palette.slate[900],
    marginTop: 2,
  },
  hospitalRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    marginTop: Spacing.md,
  },
  hospitalText: {
    fontSize: 13,
    color: Palette.slate[600],
    fontWeight: "500",
  },
  roleBadgeRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: Spacing.md,
    paddingTop: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Palette.slate[100],
  },
  roleBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: Palette.primaryLight,
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: Radius.pill,
  },
  roleText: {
    fontSize: 12,
    fontWeight: "700",
    color: Palette.primary,
  },
  statusOnlineBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  greenPulseDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: Palette.success,
  },
  statusOnlineText: {
    fontSize: 11,
    fontWeight: "600",
    color: Palette.success,
  },
  kpiBanner: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    paddingVertical: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.lg,
    ...Shadows.sm,
  },
  kpiItem: {
    alignItems: "center",
    gap: 2,
  },
  kpiValue: {
    fontSize: 14,
    fontWeight: "800",
    color: Palette.slate[900],
    marginTop: 2,
  },
  kpiLabel: {
    fontSize: 11,
    color: Palette.slate[400],
    fontWeight: "600",
  },
  kpiSeparator: {
    width: 1,
    height: 28,
    backgroundColor: Palette.slate[200],
  },
  quickActionsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: Spacing.xxl,
    gap: Spacing.sm,
  },
  quickActionItem: {
    flex: 1,
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    paddingVertical: 14,
    alignItems: "center",
    borderWidth: 1,
    borderColor: Palette.slate[200],
    ...Shadows.sm,
  },
  quickActionIcon: {
    width: 40,
    height: 40,
    borderRadius: Radius.md,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 8,
  },
  quickActionLabel: {
    fontSize: 12,
    fontWeight: "600",
    color: Palette.slate[700],
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: Spacing.md,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: Palette.slate[900],
    letterSpacing: -0.2,
  },
  liveBadge: {
    backgroundColor: Palette.primaryLight,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: Radius.sm,
    borderWidth: 1,
    borderColor: Palette.primaryBorder,
  },
  liveBadgeText: {
    fontSize: 10,
    fontWeight: "800",
    color: Palette.primary,
    letterSpacing: 0.5,
  },
  viewAllText: {
    fontSize: 12,
    fontWeight: "600",
    color: Palette.primary,
  },
  filterRow: {
    flexDirection: "row",
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  filterChip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: Radius.pill,
    backgroundColor: Palette.slate[200],
  },
  filterChipActive: {
    backgroundColor: Palette.primary,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: "600",
    color: Palette.slate[600],
  },
  filterChipTextActive: {
    color: Palette.white,
  },
  statsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    marginBottom: Spacing.lg,
  },
  statCard: {
    width: "48.2%",
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.md,
    ...Shadows.sm,
  },
  statIcon: {
    width: 38,
    height: 38,
    borderRadius: Radius.md,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: Spacing.sm,
  },
  statValue: {
    fontSize: 26,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  statTitle: {
    fontSize: 13,
    fontWeight: "600",
    color: Palette.slate[600],
    marginTop: 2,
  },
  statHint: {
    fontSize: 11,
    color: Palette.slate[400],
    marginTop: 4,
  },
  worklistCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.xl,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    paddingVertical: 4,
    marginBottom: Spacing.xl,
    ...Shadows.sm,
  },
  worklistItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  worklistLeft: {
    flex: 1,
  },
  caseIdRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  caseIdText: {
    fontSize: 14,
    fontWeight: "700",
    color: Palette.slate[900],
  },
  caseTimeText: {
    fontSize: 12,
    color: Palette.slate[400],
  },
  patientNameText: {
    fontSize: 14,
    fontWeight: "700",
    color: Palette.slate[900],
    marginTop: 2,
  },
  patientDemographicsText: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 1,
  },
  worklistRight: {
    marginLeft: 10,
    alignItems: "flex-end",
  },
  findingBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: Radius.sm,
  },
  findingBadgeText: {
    fontSize: 11,
    fontWeight: "700",
  },
  confidenceText: {
    fontSize: 11,
    color: Palette.slate[400],
    marginTop: 4,
    fontWeight: "500",
  },
  badgeCritical: {
    backgroundColor: Palette.dangerLight,
  },
  textCritical: {
    color: Palette.danger,
  },
  badgeNormal: {
    backgroundColor: Palette.successLight,
  },
  textNormal: {
    color: Palette.success,
  },
  badgeWarning: {
    backgroundColor: Palette.warningLight,
  },
  textWarning: {
    color: Palette.warning,
  },
  badgePending: {
    backgroundColor: Palette.slate[100],
  },
  textPending: {
    color: Palette.slate[600],
  },
  divider: {
    height: 1,
    backgroundColor: Palette.slate[100],
    marginHorizontal: Spacing.lg,
  },
  emptyWorklist: {
    padding: Spacing.xxl,
    alignItems: "center",
  },
  emptyWorklistTitle: {
    fontSize: 16,
    fontWeight: "700",
    color: Palette.slate[800],
    marginTop: 8,
  },
  emptyWorklistText: {
    fontSize: 13,
    color: Palette.slate[500],
    textAlign: "center",
    marginTop: 4,
    lineHeight: 18,
  },
  infoCard: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: Spacing.md,
    backgroundColor: Palette.primaryLight,
    borderWidth: 1,
    borderColor: Palette.primaryBorder,
    borderRadius: Radius.lg,
    padding: Spacing.lg,
  },
  infoIcon: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    backgroundColor: Palette.white,
    alignItems: "center",
    justifyContent: "center",
  },
  infoTextWrap: {
    flex: 1,
  },
  infoTitle: {
    fontSize: 14,
    fontWeight: "700",
    color: Palette.primaryHover,
  },
  infoText: {
    fontSize: 12,
    lineHeight: 18,
    color: Palette.primary,
    marginTop: 4,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.6)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: Palette.white,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    padding: Spacing.xl,
    maxHeight: "85%",
    ...Shadows.lg,
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: Spacing.lg,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  modalSubtitle: {
    fontSize: 13,
    color: Palette.slate[500],
    marginTop: 2,
  },
  modalCloseBtn: {
    width: 36,
    height: 36,
    borderRadius: Radius.pill,
    backgroundColor: Palette.slate[100],
    justifyContent: "center",
    alignItems: "center",
  },
  imagePreviewWrapper: {
    height: 180,
    borderRadius: Radius.lg,
    overflow: "hidden",
    marginBottom: Spacing.lg,
    backgroundColor: "#000000",
    position: "relative",
  },
  imagePreview: {
    width: "100%",
    height: "100%",
  },
  imageBadge: {
    position: "absolute",
    bottom: 8,
    left: 8,
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(15, 23, 42, 0.75)",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: Radius.sm,
  },
  imageBadgeText: {
    color: "#FFFFFF",
    fontSize: 11,
    fontWeight: "600",
  },
  findingHeroCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    padding: Spacing.lg,
    borderRadius: Radius.lg,
    marginBottom: Spacing.lg,
  },
  findingHeroCritical: {
    backgroundColor: Palette.dangerLight,
    borderWidth: 1,
    borderColor: Palette.dangerBorder,
  },
  findingHeroNormal: {
    backgroundColor: Palette.successLight,
    borderWidth: 1,
    borderColor: Palette.successBorder,
  },
  findingHeroWarning: {
    backgroundColor: Palette.warningLight,
    borderWidth: 1,
    borderColor: Palette.warningBorder,
  },
  findingHeroPending: {
    backgroundColor: Palette.slate[100],
    borderWidth: 1,
    borderColor: Palette.slate[200],
  },
  findingHeroTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  findingHeroConfidence: {
    fontSize: 13,
    color: Palette.slate[600],
    marginTop: 2,
  },
  caseDetailsCard: {
    backgroundColor: Palette.slate[50],
    borderRadius: Radius.lg,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.xl,
  },
  detailItemRow: {
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: Palette.slate[200],
  },
  detailItemLabel: {
    fontSize: 11,
    fontWeight: "700",
    color: Palette.slate[400],
    textTransform: "uppercase",
  },
  detailItemValue: {
    fontSize: 14,
    fontWeight: "600",
    color: Palette.slate[900],
    marginTop: 2,
  },
  modalActionRow: {
    flexDirection: "row",
    gap: Spacing.md,
    marginBottom: Spacing.md,
  },
  signOffButton: {
    flex: 1.4,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    height: 50,
    borderRadius: Radius.md,
    backgroundColor: Palette.primary,
    ...Shadows.sm,
  },
  signOffButtonText: {
    color: Palette.white,
    fontSize: 14,
    fontWeight: "700",
  },
  secondaryModalBtn: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    height: 50,
    borderRadius: Radius.md,
    backgroundColor: Palette.slate[100],
    borderWidth: 1,
    borderColor: Palette.slate[200],
  },
  secondaryModalBtnText: {
    color: Palette.slate[700],
    fontSize: 14,
    fontWeight: "600",
  },

  /* 2. 🚨 Critical Case Pager / High-Priority Alert Banner */
  pagerBanner: {
    backgroundColor: "#DC2626",
    borderRadius: Radius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    ...Shadows.md,
  },
  pagerPillRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(0,0,0,0.22)",
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: Radius.pill,
    alignSelf: "flex-start",
    marginBottom: 8,
  },
  pagerPulsingDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#FDE047",
  },
  pagerPillText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: "800",
    letterSpacing: 0.8,
  },
  pagerContent: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
  },
  pagerIconWrap: {
    width: 40,
    height: 40,
    borderRadius: Radius.md,
    backgroundColor: "rgba(255,255,255,0.2)",
    justifyContent: "center",
    alignItems: "center",
  },
  pagerTitle: {
    color: "#FFFFFF",
    fontSize: 15,
    fontWeight: "800",
  },
  pagerSubtitle: {
    color: "#FEE2E2",
    fontSize: 12,
    marginTop: 2,
  },
  pagerActionLink: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    marginTop: 6,
  },
  pagerActionText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "700",
    textDecorationLine: "underline",
  },

  /* 3. 📊 Live Ward & Department Glance Stats */
  glanceRow: {
    flexDirection: "row",
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  glanceCard: {
    flex: 1,
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    ...Shadows.sm,
  },
  glanceIconCircle: {
    width: 30,
    height: 30,
    borderRadius: Radius.md,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: 6,
  },
  glanceNumber: {
    fontSize: 22,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  glanceTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: Palette.slate[700],
    marginTop: 2,
  },
  glanceSub: {
    fontSize: 9,
    color: Palette.slate[400],
    marginTop: 1,
  },

  /* 1. 🔍 Live Patient Scan Status Tracker ("Ward Rounds" Mode) */
  trackerCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.lg,
    ...Shadows.sm,
  },
  trackerInstruction: {
    fontSize: 12,
    color: Palette.slate[500],
    marginBottom: Spacing.sm,
  },
  trackerSearchInputWrap: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Palette.slate[100],
    borderRadius: Radius.md,
    paddingHorizontal: Spacing.md,
    height: 42,
    gap: 8,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.sm,
  },
  trackerInput: {
    flex: 1,
    fontSize: 13,
    color: Palette.slate[900],
    height: "100%",
  },
  patientPillList: {
    gap: 6,
    paddingBottom: Spacing.xs,
    marginBottom: Spacing.sm,
  },
  patientChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: Radius.pill,
    backgroundColor: Palette.slate[100],
    borderWidth: 1,
    borderColor: Palette.slate[200],
  },
  patientChipActive: {
    backgroundColor: Palette.primaryLight,
    borderColor: Palette.primary,
  },
  patientChipText: {
    fontSize: 11,
    fontWeight: "600",
    color: Palette.slate[600],
  },
  patientChipTextActive: {
    color: Palette.primary,
    fontWeight: "700",
  },
  activePatientStepper: {
    backgroundColor: Palette.slate[50],
    borderRadius: Radius.md,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
  },
  stepperPatientBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderBottomColor: Palette.slate[200],
    paddingBottom: Spacing.sm,
    marginBottom: Spacing.sm,
  },
  stepperPatientName: {
    fontSize: 14,
    fontWeight: "700",
    color: Palette.slate[900],
  },
  stepperPatientSub: {
    fontSize: 11,
    color: Palette.slate[500],
    marginTop: 1,
  },
  stepperPeekBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: Palette.primary,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: Radius.sm,
  },
  stepperPeekText: {
    fontSize: 11,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  stepperItemsWrap: {
    marginTop: Spacing.xs,
  },
  stepperRow: {
    flexDirection: "row",
    minHeight: 46,
  },
  stepperTrackCol: {
    width: 24,
    alignItems: "center",
    marginRight: 10,
  },
  stepperDot: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: Palette.slate[200],
    justifyContent: "center",
    alignItems: "center",
    zIndex: 1,
  },
  stepperDotCompleted: {
    backgroundColor: Palette.success,
  },
  stepperDotCurrent: {
    backgroundColor: Palette.primary,
  },
  stepperDotNum: {
    fontSize: 10,
    fontWeight: "700",
    color: Palette.slate[600],
  },
  stepperDotNumCurrent: {
    color: "#FFFFFF",
  },
  stepperLine: {
    width: 2,
    flex: 1,
    backgroundColor: Palette.slate[200],
    marginVertical: 2,
  },
  stepperLineCompleted: {
    backgroundColor: Palette.success,
  },
  stepperTextCol: {
    flex: 1,
    paddingBottom: 8,
  },
  stepperStepHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  stepperStepTitle: {
    fontSize: 12,
    fontWeight: "700",
    color: Palette.slate[600],
  },
  stepperStepTitleCompleted: {
    color: Palette.slate[900],
  },
  stepperStepTime: {
    fontSize: 10,
    fontWeight: "600",
    color: Palette.slate[400],
  },
  stepperStepSub: {
    fontSize: 11,
    color: Palette.slate[500],
    marginTop: 1,
  },
  stepperStepDetail: {
    fontSize: 10,
    color: Palette.primary,
    fontWeight: "600",
    marginTop: 2,
  },
  emptyTrackerState: {
    padding: Spacing.md,
    alignItems: "center",
  },
  emptyTrackerStateText: {
    fontSize: 12,
    color: Palette.slate[400],
    marginTop: 4,
    textAlign: "center",
  },

  /* 4. 🖼️ Read-Only X-Ray Preview with Pinch-to-Zoom & Contrast Toggle */
  cxrViewerContainer: {
    backgroundColor: "#0F172A",
    borderRadius: Radius.lg,
    overflow: "hidden",
    marginBottom: Spacing.md,
  },
  cxrControlsHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: Spacing.sm,
    paddingVertical: 6,
    backgroundColor: "#1E293B",
    borderBottomWidth: 1,
    borderBottomColor: "#334155",
  },
  cxrPillsRow: {
    flexDirection: "row",
    gap: 4,
  },
  cxrModePill: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: Radius.sm,
    backgroundColor: "rgba(255,255,255,0.08)",
  },
  cxrModePillActive: {
    backgroundColor: Palette.primary,
  },
  cxrModePillText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#94A3B8",
  },
  cxrModePillTextActive: {
    color: "#FFFFFF",
  },
  cxrZoomRow: {
    flexDirection: "row",
    gap: 4,
    alignItems: "center",
  },
  cxrZoomBtn: {
    paddingHorizontal: 6,
    paddingVertical: 4,
    borderRadius: Radius.sm,
    backgroundColor: "rgba(255,255,255,0.08)",
  },
  cxrZoomBtnActive: {
    backgroundColor: Palette.primary,
  },
  cxrZoomBtnText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#E2E8F0",
  },
  cxrCanvas: {
    width: "100%",
    height: 260,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#000000",
  },
  canvasInverted: {
    backgroundColor: "#FFFFFF",
  },
  canvasHighContrast: {
    backgroundColor: "#000000",
  },

  /* Modal Tracker Section */
  modalTrackerSection: {
    backgroundColor: Palette.slate[50],
    borderRadius: Radius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.lg,
  },
  modalTrackerHeading: {
    fontSize: 10,
    fontWeight: "800",
    color: Palette.slate[400],
    letterSpacing: 0.8,
    marginBottom: Spacing.sm,
  },
  modalStepperList: {
    marginTop: 2,
  },
  modalStepRow: {
    flexDirection: "row",
    minHeight: 38,
  },
  modalStepLeftCol: {
    width: 20,
    alignItems: "center",
    marginRight: 8,
  },
  modalStepDot: {
    width: 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: Palette.slate[200],
    justifyContent: "center",
    alignItems: "center",
  },
  modalStepLine: {
    width: 2,
    flex: 1,
    backgroundColor: Palette.slate[200],
    marginVertical: 2,
  },
  modalStepRightCol: {
    flex: 1,
    paddingBottom: 6,
  },
  modalStepTitleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  modalStepTitle: {
    fontSize: 11,
    fontWeight: "700",
    color: Palette.slate[600],
  },
  modalStepTime: {
    fontSize: 10,
    color: Palette.slate[400],
  },
  modalStepSub: {
    fontSize: 10,
    color: Palette.slate[500],
    marginTop: 1,
  },

  /* Ward Rounds Launcher Banner */
  roundsLauncherCard: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.lg,
    ...Shadows.sm,
  },
  roundsLauncherLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    flex: 1,
    paddingRight: Spacing.sm,
  },
  roundsLauncherIconCircle: {
    width: 42,
    height: 42,
    borderRadius: Radius.md,
    backgroundColor: Palette.primary,
    justifyContent: "center",
    alignItems: "center",
    ...Shadows.sm,
  },
  roundsLauncherTagRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 2,
  },
  roundsLauncherTag: {
    fontSize: 9,
    fontWeight: "800",
    color: Palette.primary,
    letterSpacing: 0.6,
  },
  roundsLauncherTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  roundsLauncherSub: {
    fontSize: 11,
    color: Palette.slate[500],
    marginTop: 2,
  },
});