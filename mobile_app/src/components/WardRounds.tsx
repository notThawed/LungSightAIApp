import { useCallback, useEffect, useMemo, useState } from "react";
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

import { getCurrentUserProfile, UserProfile } from "../lib/user";
import {
  getCaseWorkflowSteps,
  getLiveDashboardData,
  LiveClinicalCase,
  ScanWorkflowStep,
} from "../lib/scans";
import { Palette, Radius, Shadows, Spacing } from "../constants/theme";

type WardRoundsProps = {
  role?: string;
};

export default function WardRounds({ role }: WardRoundsProps = {}) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [cases, setCases] = useState<LiveClinicalCase[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "critical" | "pending" | "cleared">("all");

  // Inspect Modal State
  const [inspectCase, setInspectCase] = useState<LiveClinicalCase | null>(null);
  const [zoomScale, setZoomScale] = useState(1);
  const [contrastMode, setContrastMode] = useState<"standard" | "high" | "inverted">("standard");

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const profile = await getCurrentUserProfile();
      setUser(profile);

      const { cases: liveCases } = await getLiveDashboardData(profile.hospitalId);
      setCases(liveCases);
      if (liveCases.length > 0 && !selectedCaseId) {
        setSelectedCaseId(liveCases[0].caseId);
      }
    } catch (err) {
      console.error("WardRounds load error:", err);
      if (isRefresh) {
        Alert.alert("Refresh failed", "Unable to refresh ward scans.");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const onRefresh = useCallback(() => {
    void loadData(true);
  }, [loadData]);

  // Filtered cases by search query and filter chip
  const filteredCases = useMemo(() => {
    return cases.filter((c) => {
      // Filter by category
      if (statusFilter === "critical" && c.status !== "critical" && c.status !== "warning") {
        return false;
      }
      if (statusFilter === "pending" && c.physicianSignOffStatus !== "Pending") {
        return false;
      }
      if (statusFilter === "cleared" && c.status !== "normal") {
        return false;
      }

      // Filter by search query
      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase().trim();
      return (
        c.patientName.toLowerCase().includes(q) ||
        c.patientId.toLowerCase().includes(q) ||
        c.caseId.toLowerCase().includes(q) ||
        c.ward.toLowerCase().includes(q)
      );
    });
  }, [cases, searchQuery, statusFilter]);

  // Selected Active Patient in Ward Rounds
  const activeCase = useMemo(() => {
    if (selectedCaseId) {
      const found = cases.find((c) => c.caseId === selectedCaseId);
      if (found) return found;
    }
    return filteredCases[0] || cases[0] || null;
  }, [cases, selectedCaseId, filteredCases]);

  // 4-Step Stepper for the active patient
  const workflowSteps = useMemo(() => {
    if (!activeCase) return [];
    return getCaseWorkflowSteps(activeCase);
  }, [activeCase]);

  // Inspect CXR modal helper
  const handleInspect = (c: LiveClinicalCase) => {
    setInspectCase(c);
    setZoomScale(1);
    setContrastMode("standard");
  };

  if (loading && !refreshing) {
    return (
      <View style={styles.center}>
        <StatusBar style="dark" />
        <View style={styles.loadingLogoBadge}>
          <Ionicons name="walk" size={32} color="#FFFFFF" />
        </View>
        <ActivityIndicator size="large" color={Palette.primary} style={{ marginTop: 16 }} />
        <Text style={styles.loadingText}>Syncing Ward Rounds Data...</Text>
      </View>
    );
  }

  const criticalCount = cases.filter(
    (c) => c.status === "critical" || c.status === "warning"
  ).length;
  const pendingCount = cases.filter(
    (c) => c.physicianSignOffStatus === "Pending"
  ).length;
  const normalCount = cases.filter((c) => c.status === "normal").length;

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
          />
        }
      >
        {/* Top Header */}
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <View style={styles.headerIconWrap}>
              <Ionicons name="walk" size={20} color="#FFFFFF" />
            </View>
            <View>
              <Text style={styles.headerTitle}>Ward Rounds Tracker</Text>
              <Text style={styles.headerSubtitle}>
                {user?.hospitalName || "Hospital Rounds Mode"}
              </Text>
            </View>
          </View>

          <TouchableOpacity
            style={styles.refreshBtn}
            onPress={onRefresh}
            activeOpacity={0.7}
          >
            <Ionicons name="sync" size={18} color={Palette.primary} />
          </TouchableOpacity>
        </View>

        {/* Live Search Input */}
        <View style={styles.searchBarWrap}>
          <Ionicons name="search" size={18} color={Palette.slate[400]} />
          <TextInput
            style={styles.searchInput}
            placeholder="Search patient code, name, CXR #, or ward..."
            placeholderTextColor={Palette.slate[400]}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCapitalize="none"
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery("")}>
              <Ionicons name="close-circle" size={18} color={Palette.slate[400]} />
            </TouchableOpacity>
          )}
        </View>

        {/* Status Filter Chips */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterChipRow}
        >
          <TouchableOpacity
            style={[
              styles.filterChip,
              statusFilter === "all" && styles.filterChipActive,
            ]}
            onPress={() => setStatusFilter("all")}
          >
            <Text
              style={[
                styles.filterChipText,
                statusFilter === "all" && styles.filterChipTextActive,
              ]}
            >
              All ({cases.length})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.filterChip,
              statusFilter === "critical" && styles.filterChipActiveCritical,
            ]}
            onPress={() => setStatusFilter("critical")}
          >
            <Text
              style={[
                styles.filterChipText,
                statusFilter === "critical" && styles.filterChipTextActive,
              ]}
            >
              High Risk ({criticalCount})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.filterChip,
              statusFilter === "pending" && styles.filterChipActive,
            ]}
            onPress={() => setStatusFilter("pending")}
          >
            <Text
              style={[
                styles.filterChipText,
                statusFilter === "pending" && styles.filterChipTextActive,
              ]}
            >
              Pending Sign-Off ({pendingCount})
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.filterChip,
              statusFilter === "cleared" && styles.filterChipActive,
            ]}
            onPress={() => setStatusFilter("cleared")}
          >
            <Text
              style={[
                styles.filterChipText,
                statusFilter === "cleared" && styles.filterChipTextActive,
              ]}
            >
              Normal ({normalCount})
            </Text>
          </TouchableOpacity>
        </ScrollView>

        {/* 1. 🔍 Active Patient 4-Step Stepper Focus Card */}
        {activeCase ? (
          <View style={styles.focusCard}>
            <View style={styles.focusHeader}>
              <View style={{ flex: 1 }}>
                <View style={styles.activePillTag}>
                  <View style={styles.activePillDot} />
                  <Text style={styles.activePillText}>SELECTED ROUNDS PATIENT</Text>
                </View>
                <Text style={styles.focusPatientName}>{activeCase.patientName}</Text>
                <Text style={styles.focusPatientMeta}>
                  {activeCase.patientId} • {activeCase.caseId} • {activeCase.demographics}
                </Text>
                <Text style={styles.focusWard}>Location: {activeCase.ward}</Text>
              </View>

              <TouchableOpacity
                style={styles.focusInspectBtn}
                onPress={() => handleInspect(activeCase)}
                activeOpacity={0.8}
              >
                <Ionicons name="scan" size={16} color="#FFFFFF" />
                <Text style={styles.focusInspectText}>Inspect CXR</Text>
              </TouchableOpacity>
            </View>

            {/* 4-Step Visual Progression */}
            <View style={styles.stepperContainer}>
              {workflowSteps.map((step, idx) => {
                const isLast = idx === workflowSteps.length - 1;
                return (
                  <View key={step.stepNumber} style={styles.stepRow}>
                    <View style={styles.stepTrackCol}>
                      <View
                        style={[
                          styles.stepCircle,
                          step.completed && styles.stepCircleCompleted,
                          step.current && styles.stepCircleCurrent,
                        ]}
                      >
                        {step.completed ? (
                          <Ionicons name="checkmark" size={12} color="#FFFFFF" />
                        ) : (
                          <Text
                            style={[
                              styles.stepNum,
                              step.current && styles.stepNumCurrent,
                            ]}
                          >
                            {step.stepNumber}
                          </Text>
                        )}
                      </View>
                      {!isLast && (
                        <View
                          style={[
                            styles.stepConnector,
                            step.completed && styles.stepConnectorCompleted,
                          ]}
                        />
                      )}
                    </View>

                    <View style={styles.stepContentCol}>
                      <View style={styles.stepHeaderRow}>
                        <Text
                          style={[
                            styles.stepTitle,
                            step.completed && styles.stepTitleCompleted,
                          ]}
                        >
                          {step.title}
                        </Text>
                        <Text style={styles.stepTime}>{step.timestamp}</Text>
                      </View>
                      <Text style={styles.stepSubtitle}>{step.subtitle}</Text>
                      {step.detail && (
                        <Text style={styles.stepDetail}>{step.detail}</Text>
                      )}
                    </View>
                  </View>
                );
              })}
            </View>
          </View>
        ) : (
          <View style={styles.emptyCard}>
            <Ionicons name="person-outline" size={36} color={Palette.slate[400]} />
            <Text style={styles.emptyTitle}>No patients found</Text>
            <Text style={styles.emptyText}>
              No patient records match "{searchQuery}".
            </Text>
          </View>
        )}

        {/* Bedside Patient Worklist Section */}
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>Ward Examination Worklist</Text>
          <Text style={styles.sectionHint}>Tap patient to switch stepper</Text>
        </View>

        <View style={styles.worklistWrap}>
          {filteredCases.map((item) => {
            const isSelected = activeCase?.caseId === item.caseId;
            const isCritical = item.status === "critical" || item.status === "warning";
            const isSignedOff = item.physicianSignOffStatus === "Approved";

            return (
              <TouchableOpacity
                key={item.caseId}
                style={[
                  styles.patientCard,
                  isSelected && styles.patientCardActive,
                ]}
                onPress={() => setSelectedCaseId(item.caseId)}
                activeOpacity={0.75}
              >
                <View style={styles.patientCardTop}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.patientCardName}>{item.patientName}</Text>
                    <Text style={styles.patientCardMeta}>
                      {item.patientId} • {item.demographics} • {item.ward}
                    </Text>
                  </View>

                  <View
                    style={[
                      styles.findingPill,
                      isCritical && styles.findingPillCritical,
                      item.status === "normal" && styles.findingPillNormal,
                      item.status === "pending" && styles.findingPillPending,
                    ]}
                  >
                    <Text
                      style={[
                        styles.findingPillText,
                        isCritical && styles.textDanger,
                        item.status === "normal" && styles.textSuccess,
                      ]}
                    >
                      {item.finding}
                    </Text>
                  </View>
                </View>

                {/* Progress Pill Bar */}
                <View style={styles.progressRow}>
                  <View style={styles.progressBadge}>
                    <Ionicons
                      name={isSignedOff ? "checkmark-done-circle" : "hourglass-outline"}
                      size={13}
                      color={isSignedOff ? Palette.success : Palette.primary}
                    />
                    <Text style={styles.progressBadgeText}>
                      {isSignedOff
                        ? "Step 4/4 • Signed Off"
                        : "Step 3/4 • AI Screened"}
                    </Text>
                  </View>

                  <View style={styles.cardChevronWrap}>
                    <Ionicons name="chevron-forward" size={15} color={Palette.slate[400]} />
                  </View>
                </View>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>

      {/* 4. 🖼️ Read-Only X-Ray Preview with Pinch-to-Zoom & Contrast Toggle */}
      {inspectCase && (
        <Modal
          animationType="slide"
          transparent
          visible={Boolean(inspectCase)}
          onRequestClose={() => setInspectCase(null)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.modalTitle}>{inspectCase.patientName}</Text>
                  <Text style={styles.modalSubtitle}>
                    {inspectCase.patientId} • {inspectCase.caseId} • {inspectCase.ward}
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.modalCloseBtn}
                  onPress={() => setInspectCase(null)}
                >
                  <Ionicons name="close" size={20} color={Palette.slate[600]} />
                </TouchableOpacity>
              </View>

              <ScrollView showsVerticalScrollIndicator={false}>
                {inspectCase.imageUrl ? (
                  <View style={styles.cxrViewerContainer}>
                    {/* Contrast & Zoom Control Bar */}
                    <View style={styles.cxrControlsHeader}>
                      <View style={styles.cxrPillsRow}>
                        <TouchableOpacity
                          style={[
                            styles.cxrModePill,
                            contrastMode === "standard" && styles.cxrModePillActive,
                          ]}
                          onPress={() => setContrastMode("standard")}
                        >
                          <Text
                            style={[
                              styles.cxrModePillText,
                              contrastMode === "standard" && styles.cxrModePillTextActive,
                            ]}
                          >
                            Standard
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          style={[
                            styles.cxrModePill,
                            contrastMode === "high" && styles.cxrModePillActive,
                          ]}
                          onPress={() => setContrastMode("high")}
                        >
                          <Text
                            style={[
                              styles.cxrModePillText,
                              contrastMode === "high" && styles.cxrModePillTextActive,
                            ]}
                          >
                            High Contrast
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          style={[
                            styles.cxrModePill,
                            contrastMode === "inverted" && styles.cxrModePillActive,
                          ]}
                          onPress={() => setContrastMode("inverted")}
                        >
                          <Text
                            style={[
                              styles.cxrModePillText,
                              contrastMode === "inverted" && styles.cxrModePillTextActive,
                            ]}
                          >
                            Bone Filter
                          </Text>
                        </TouchableOpacity>
                      </View>

                      {/* Zoom Controls */}
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
                            setContrastMode("standard");
                          }}
                        >
                          <Ionicons name="refresh" size={12} color={Palette.slate[600]} />
                        </TouchableOpacity>
                      </View>
                    </View>

                    {/* Image View */}
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
                            contrastMode === "inverted" && styles.canvasInverted,
                            contrastMode === "high" && styles.canvasHighContrast,
                          ]}
                        >
                          <Image
                            source={{ uri: inspectCase.imageUrl }}
                            style={[
                              styles.imagePreview,
                              {
                                transform: [{ scale: zoomScale }],
                                opacity: contrastMode === "high" ? 0.95 : 1,
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
                        Chest PA View • {contrastMode.toUpperCase()} • {zoomScale}x
                      </Text>
                    </View>
                  </View>
                ) : (
                  <View style={styles.noImageBox}>
                    <Ionicons name="image-outline" size={32} color={Palette.slate[400]} />
                    <Text style={styles.noImageText}>X-Ray Image in Acquisition</Text>
                  </View>
                )}

                {/* Finding Highlight Card */}
                <View
                  style={[
                    styles.modalFindingCard,
                    (inspectCase.status === "critical" || inspectCase.status === "warning") &&
                      styles.modalFindingCritical,
                    inspectCase.status === "normal" && styles.modalFindingNormal,
                  ]}
                >
                  <Ionicons
                    name={
                      inspectCase.status === "critical" || inspectCase.status === "warning"
                        ? "alert-circle"
                        : "checkmark-circle"
                    }
                    size={24}
                    color={
                      inspectCase.status === "critical" || inspectCase.status === "warning"
                        ? Palette.danger
                        : Palette.success
                    }
                  />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.modalFindingTitle}>{inspectCase.finding}</Text>
                    <Text style={styles.modalFindingSub}>
                      AI Confidence Score: {inspectCase.confidence}
                    </Text>
                  </View>
                </View>

                {/* Clinical Notes */}
                <View style={styles.notesCard}>
                  <Text style={styles.notesLabel}>RADIOLOGIC EVALUATION</Text>
                  <Text style={styles.notesText}>{inspectCase.notes}</Text>
                  <Text style={styles.notesRegion}>
                    Region: {inspectCase.infiltrateLocation}
                  </Text>
                </View>

                {/* Primary Action Button (Desktop Hand-off) */}
                <View style={styles.modalActionRow}>
                  <TouchableOpacity
                    style={styles.modalWorkstationBtn}
                    onPress={() => {
                      Alert.alert(
                        "Clinical Review",
                        "Full diagnostic sign-off can be completed on your desktop PACS workstation."
                      );
                      setInspectCase(null);
                    }}
                  >
                    <Ionicons name="desktop-outline" size={16} color="#FFFFFF" />
                    <Text style={styles.modalWorkstationBtnText}>
                      Sign on Desktop Workstation
                    </Text>
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
    paddingTop: Spacing.md,
    paddingBottom: Spacing.xxxl,
  },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: Palette.slate[50],
  },
  loadingLogoBadge: {
    width: 60,
    height: 60,
    borderRadius: Radius.lg,
    backgroundColor: Palette.primary,
    justifyContent: "center",
    alignItems: "center",
    ...Shadows.md,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: Palette.slate[600],
    fontWeight: "600",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: Spacing.md,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.sm,
  },
  headerIconWrap: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    backgroundColor: Palette.primary,
    justifyContent: "center",
    alignItems: "center",
    ...Shadows.sm,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  headerSubtitle: {
    fontSize: 12,
    color: Palette.slate[500],
  },
  refreshBtn: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    backgroundColor: Palette.white,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: Palette.slate[200],
    ...Shadows.sm,
  },
  searchBarWrap: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    paddingHorizontal: Spacing.md,
    height: 44,
    gap: 8,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.sm,
    ...Shadows.sm,
  },
  searchInput: {
    flex: 1,
    fontSize: 13,
    color: Palette.slate[900],
    height: "100%",
  },
  filterChipRow: {
    gap: 6,
    paddingBottom: Spacing.sm,
    marginBottom: Spacing.md,
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: Radius.pill,
    backgroundColor: Palette.slate[200],
  },
  filterChipActive: {
    backgroundColor: Palette.primary,
  },
  filterChipActiveCritical: {
    backgroundColor: Palette.danger,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: "600",
    color: Palette.slate[600],
  },
  filterChipTextActive: {
    color: "#FFFFFF",
  },
  focusCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.xl,
    padding: Spacing.lg,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.lg,
    ...Shadows.md,
  },
  focusHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    borderBottomWidth: 1,
    borderBottomColor: Palette.slate[100],
    paddingBottom: Spacing.md,
    marginBottom: Spacing.md,
  },
  activePillTag: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    backgroundColor: Palette.primaryLight,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: Radius.pill,
    alignSelf: "flex-start",
    marginBottom: 6,
  },
  activePillDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: Palette.primary,
  },
  activePillText: {
    fontSize: 9,
    fontWeight: "800",
    color: Palette.primary,
    letterSpacing: 0.5,
  },
  focusPatientName: {
    fontSize: 17,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  focusPatientMeta: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 2,
  },
  focusWard: {
    fontSize: 12,
    fontWeight: "600",
    color: Palette.primary,
    marginTop: 2,
  },
  focusInspectBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: Palette.primary,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: Radius.md,
    ...Shadows.sm,
  },
  focusInspectText: {
    fontSize: 12,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  stepperContainer: {
    paddingTop: Spacing.xs,
  },
  stepRow: {
    flexDirection: "row",
    minHeight: 52,
  },
  stepTrackCol: {
    width: 24,
    alignItems: "center",
    marginRight: 10,
  },
  stepCircle: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: Palette.slate[200],
    justifyContent: "center",
    alignItems: "center",
    zIndex: 1,
  },
  stepCircleCompleted: {
    backgroundColor: Palette.success,
  },
  stepCircleCurrent: {
    backgroundColor: Palette.primary,
  },
  stepNum: {
    fontSize: 11,
    fontWeight: "700",
    color: Palette.slate[600],
  },
  stepNumCurrent: {
    color: "#FFFFFF",
  },
  stepConnector: {
    width: 2,
    flex: 1,
    backgroundColor: Palette.slate[200],
    marginVertical: 2,
  },
  stepConnectorCompleted: {
    backgroundColor: Palette.success,
  },
  stepContentCol: {
    flex: 1,
    paddingBottom: 10,
  },
  stepHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  stepTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: Palette.slate[600],
  },
  stepTitleCompleted: {
    color: Palette.slate[900],
  },
  stepTime: {
    fontSize: 11,
    color: Palette.slate[400],
  },
  stepSubtitle: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 1,
  },
  stepDetail: {
    fontSize: 11,
    color: Palette.primary,
    fontWeight: "600",
    marginTop: 2,
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: Spacing.sm,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  sectionHint: {
    fontSize: 11,
    color: Palette.slate[500],
  },
  worklistWrap: {
    gap: Spacing.sm,
  },
  patientCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    ...Shadows.sm,
  },
  patientCardActive: {
    borderColor: Palette.primary,
    backgroundColor: "#F8FAFC",
  },
  patientCardTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: Spacing.sm,
  },
  patientCardName: {
    fontSize: 14,
    fontWeight: "700",
    color: Palette.slate[900],
  },
  patientCardMeta: {
    fontSize: 11,
    color: Palette.slate[500],
    marginTop: 2,
  },
  findingPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: Radius.sm,
    backgroundColor: Palette.slate[100],
  },
  findingPillCritical: {
    backgroundColor: Palette.dangerLight,
  },
  findingPillNormal: {
    backgroundColor: Palette.successLight,
  },
  findingPillPending: {
    backgroundColor: Palette.warningLight,
  },
  findingPillText: {
    fontSize: 10,
    fontWeight: "700",
    color: Palette.slate[600],
  },
  textDanger: {
    color: Palette.danger,
  },
  textSuccess: {
    color: Palette.success,
  },
  progressRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderTopWidth: 1,
    borderTopColor: Palette.slate[100],
    paddingTop: Spacing.xs,
  },
  progressBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  progressBadgeText: {
    fontSize: 11,
    color: Palette.slate[600],
    fontWeight: "600",
  },
  cardChevronWrap: {
    padding: 4,
    justifyContent: "center",
    alignItems: "center",
  },
  emptyCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    padding: Spacing.xl,
    alignItems: "center",
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.md,
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

  /* Modal Styles */
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(15, 23, 42, 0.65)",
    justifyContent: "flex-end",
  },
  modalContent: {
    backgroundColor: Palette.white,
    borderTopLeftRadius: Radius.xl,
    borderTopRightRadius: Radius.xl,
    padding: Spacing.lg,
    maxHeight: "88%",
  },
  modalHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    borderBottomWidth: 1,
    borderBottomColor: Palette.slate[200],
    paddingBottom: Spacing.sm,
    marginBottom: Spacing.md,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  modalSubtitle: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 2,
  },
  modalCloseBtn: {
    width: 32,
    height: 32,
    borderRadius: Radius.pill,
    backgroundColor: Palette.slate[100],
    justifyContent: "center",
    alignItems: "center",
  },
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
  imagePreview: {
    width: 250,
    height: 250,
  },
  imageBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    backgroundColor: "rgba(0,0,0,0.6)",
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  imageBadgeText: {
    color: "#FFFFFF",
    fontSize: 10,
    fontWeight: "600",
  },
  noImageBox: {
    height: 140,
    backgroundColor: Palette.slate[100],
    borderRadius: Radius.md,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: Spacing.md,
  },
  noImageText: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 6,
  },
  modalFindingCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: Spacing.md,
    padding: Spacing.md,
    borderRadius: Radius.lg,
    backgroundColor: Palette.slate[100],
    marginBottom: Spacing.md,
  },
  modalFindingCritical: {
    backgroundColor: Palette.dangerLight,
  },
  modalFindingNormal: {
    backgroundColor: Palette.successLight,
  },
  modalFindingTitle: {
    fontSize: 15,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  modalFindingSub: {
    fontSize: 12,
    color: Palette.slate[600],
    marginTop: 1,
  },
  notesCard: {
    backgroundColor: Palette.slate[50],
    borderRadius: Radius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.lg,
  },
  notesLabel: {
    fontSize: 10,
    fontWeight: "800",
    color: Palette.slate[400],
    letterSpacing: 0.8,
    marginBottom: 4,
  },
  notesText: {
    fontSize: 13,
    color: Palette.slate[700],
    lineHeight: 18,
  },
  notesRegion: {
    fontSize: 11,
    fontWeight: "600",
    color: Palette.primary,
    marginTop: 6,
  },
  modalActionRow: {
    marginBottom: Spacing.md,
  },
  modalWorkstationBtn: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    height: 48,
    borderRadius: Radius.md,
    backgroundColor: Palette.primary,
  },
  modalWorkstationBtnText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
});
