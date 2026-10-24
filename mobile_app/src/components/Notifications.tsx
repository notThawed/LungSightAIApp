import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { router } from "expo-router";
import Ionicons from "@expo/vector-icons/Ionicons";

import { getCurrentUserProfile, UserProfile } from "../lib/user";
import {
  getLiveNotifications,
  LiveNotificationItem,
  LiveClinicalCase,
  getCaseWorkflowSteps,
} from "../lib/scans";
import { Palette, Radius, Shadows, Spacing } from "../constants/theme";

type NotificationsProps = {
  role?: string;
};

export default function Notifications({ role }: NotificationsProps = {}) {
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [filter, setFilter] = useState<"all" | "unread" | "critical">("all");
  const [items, setItems] = useState<LiveNotificationItem[]>([]);
  const [selectedCase, setSelectedCase] = useState<LiveClinicalCase | null>(null);

  // CXR viewer controls inside notification modal
  const [zoomScale, setZoomScale] = useState(1);
  const [contrastMode, setContrastMode] = useState<"standard" | "high" | "inverted">("standard");

  const effectiveRole = currentUser?.role || role || "radiologist";

  const fetchNotifications = useCallback(async () => {
    try {
      const profile = await getCurrentUserProfile();
      setCurrentUser(profile);
      const liveItems = await getLiveNotifications(profile?.hospitalId);
      setItems(liveItems || []);
    } catch (err) {
      console.error("Notifications fetch error:", err);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const init = async () => {
      await fetchNotifications();
      if (mounted) setLoading(false);
    };
    void init();
    return () => {
      mounted = false;
    };
  }, [fetchNotifications]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchNotifications();
    setRefreshing(false);
  }, [fetchNotifications]);

  const handleBack = () => {
    if (router.canGoBack()) {
      router.back();
    } else {
      if (effectiveRole === "radiologist") {
        router.replace("/physician");
      } else if (effectiveRole === "radiologic_technologist" || effectiveRole === "rad_tech") {
        router.replace("/rad_tech");
      } else {
        router.replace("/staff");
      }
    }
  };

  const handleMarkAllRead = () => {
    setItems((prev) => prev.map((item) => ({ ...item, read: true })));
  };

  const handleNotificationPress = (item: LiveNotificationItem) => {
    // Mark this item as read
    setItems((prev) =>
      prev.map((i) => (i.id === item.id ? { ...i, read: true } : i))
    );

    if (item.clinicalCase) {
      setZoomScale(1);
      setContrastMode("standard");
      setSelectedCase(item.clinicalCase);
    } else if (item.type === "system") {
      Alert.alert(
        "System Connectivity Status",
        "DenseNet-121 v2.1 model pipeline is active. Mobile companion is continuously synchronized with the central hospital PACS and Supabase database.",
        [{ text: "OK" }]
      );
    }
  };

  const handleOpenInWardRounds = (c: LiveClinicalCase) => {
    setSelectedCase(null);
    if (effectiveRole === "radiologist") {
      router.push("/physician/tracker");
    } else if (effectiveRole === "radiologic_technologist" || effectiveRole === "rad_tech") {
      router.push("/rad_tech/tracker");
    } else {
      router.push("/staff/tracker");
    }
  };

  const unreadCount = useMemo(() => items.filter((i) => !i.read).length, [items]);
  const criticalCount = useMemo(
    () => items.filter((i) => i.type === "alert").length,
    [items]
  );

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (filter === "unread") return !item.read;
      if (filter === "critical") return item.type === "alert";
      return true;
    });
  }, [items, filter]);

  if (loading && !refreshing) {
    return (
      <View style={styles.center}>
        <StatusBar style="dark" />
        <View style={styles.loadingLogoBadge}>
          <Ionicons name="notifications" size={30} color="#FFFFFF" />
        </View>
        <ActivityIndicator size="large" color={Palette.primary} style={{ marginTop: 16 }} />
        <Text style={styles.loadingText}>Syncing Clinical Notifications...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />

      {/* Top Header */}
      <View style={styles.header}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={handleBack}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          activeOpacity={0.7}
        >
          <Ionicons name="arrow-back" size={22} color={Palette.slate[900]} />
        </TouchableOpacity>

        <View style={styles.headerCenter}>
          <Text style={styles.headerTitle}>Notifications</Text>
          <Text style={styles.headerSubtitle}>
            {currentUser?.hospitalName || "Hospital AI Alerts & Updates"}
          </Text>
        </View>

        <TouchableOpacity
          style={[styles.markReadButton, unreadCount === 0 && { opacity: 0.5 }]}
          onPress={handleMarkAllRead}
          disabled={unreadCount === 0}
          accessibilityRole="button"
          accessibilityLabel="Mark all as read"
          activeOpacity={0.7}
        >
          <Ionicons name="checkmark-done" size={20} color={Palette.primary} />
        </TouchableOpacity>
      </View>

      {/* Filter Tabs */}
      <View style={styles.filterRow}>
        <TouchableOpacity
          style={[styles.filterChip, filter === "all" && styles.filterChipActive]}
          onPress={() => setFilter("all")}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.filterChipText,
              filter === "all" && styles.filterChipTextActive,
            ]}
          >
            All ({items.length})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.filterChip,
            filter === "unread" && styles.filterChipActive,
          ]}
          onPress={() => setFilter("unread")}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.filterChipText,
              filter === "unread" && styles.filterChipTextActive,
            ]}
          >
            Unread ({unreadCount})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[
            styles.filterChip,
            filter === "critical" && styles.filterChipActiveCritical,
          ]}
          onPress={() => setFilter("critical")}
          activeOpacity={0.7}
        >
          <Text
            style={[
              styles.filterChipText,
              filter === "critical" && styles.filterChipTextActive,
            ]}
          >
            High Risk ({criticalCount})
          </Text>
        </TouchableOpacity>
      </View>

      {/* Notifications List */}
      <ScrollView
        contentContainerStyle={styles.scrollList}
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
        {filteredItems.length === 0 ? (
          <View style={styles.emptyCard}>
            <View style={styles.emptyIconCircle}>
              <Ionicons
                name="notifications-off-outline"
                size={36}
                color={Palette.slate[400]}
              />
            </View>
            <Text style={styles.emptyTitle}>All caught up!</Text>
            <Text style={styles.emptyText}>
              {filter === "unread"
                ? "No unread alerts. You have reviewed all notifications."
                : filter === "critical"
                ? "No active high-risk clinical alerts at this time."
                : "No notifications found for this facility."}
            </Text>
          </View>
        ) : (
          filteredItems.map((item) => {
            const isAlert = item.type === "alert";
            const isScan = item.type === "scan";
            const hasCase = Boolean(item.clinicalCase);

            return (
              <TouchableOpacity
                key={item.id}
                style={[
                  styles.notificationCard,
                  !item.read && styles.unreadCard,
                  isAlert && !item.read && styles.unreadAlertCard,
                ]}
                activeOpacity={0.82}
                onPress={() => handleNotificationPress(item)}
              >
                <View style={styles.cardHeaderRow}>
                  <View style={styles.iconTitleRow}>
                    <View
                      style={[
                        styles.iconBadge,
                        isAlert && styles.alertBadge,
                        isScan && styles.scanBadge,
                      ]}
                    >
                      <Ionicons
                        name={
                          isAlert
                            ? "warning"
                            : isScan
                            ? "scan"
                            : "cloud-done"
                        }
                        size={18}
                        color={
                          isAlert
                            ? Palette.danger
                            : isScan
                            ? Palette.primary
                            : Palette.slate[600]
                        }
                      />
                    </View>
                    <View style={styles.titleColumn}>
                      <Text style={styles.itemTitle}>{item.title}</Text>
                      <Text style={styles.itemTime}>{item.time}</Text>
                    </View>
                  </View>

                  {!item.read && (
                    <View
                      style={[
                        styles.unreadDot,
                        isAlert && { backgroundColor: Palette.danger },
                      ]}
                    />
                  )}
                </View>

                <Text style={styles.itemMessage}>{item.message}</Text>

                {hasCase && item.clinicalCase && (
                  <View style={styles.caseFooterHint}>
                    <View style={styles.caseBadge}>
                      <Ionicons name="person-outline" size={12} color={Palette.slate[600]} />
                      <Text style={styles.caseBadgeText}>
                        {item.clinicalCase.patientId} • {item.clinicalCase.ward}
                      </Text>
                    </View>
                    <View style={styles.inspectHint}>
                      <Text style={styles.inspectHintText}>Inspect scan</Text>
                      <Ionicons name="chevron-forward" size={13} color={Palette.primary} />
                    </View>
                  </View>
                )}
              </TouchableOpacity>
            );
          })
        )}
      </ScrollView>

      {/* Case Details Inspection Modal (Launched from Notification) */}
      {selectedCase && (
        <Modal
          animationType="slide"
          transparent
          visible={Boolean(selectedCase)}
          onRequestClose={() => setSelectedCase(null)}
        >
          <View style={styles.modalOverlay}>
            <View style={styles.modalContent}>
              <View style={styles.modalHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.modalTitle}>{selectedCase.patientName}</Text>
                  <Text style={styles.modalSubtitle}>
                    {selectedCase.patientId} • {selectedCase.caseId} • {selectedCase.ward}
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.modalCloseBtn}
                  onPress={() => setSelectedCase(null)}
                  activeOpacity={0.7}
                >
                  <Ionicons name="close" size={20} color={Palette.slate[600]} />
                </TouchableOpacity>
              </View>

              <ScrollView showsVerticalScrollIndicator={false}>
                {/* Read-Only X-Ray Preview with Contrast & Zoom */}
                {selectedCase.imageUrl ? (
                  <View style={styles.cxrViewerContainer}>
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

                      <View style={styles.zoomActionsRow}>
                        <TouchableOpacity
                          style={styles.zoomActionBtn}
                          onPress={() => setZoomScale((z) => Math.max(1, Number((z - 0.25).toFixed(2))))}
                        >
                          <Ionicons name="remove" size={14} color={Palette.slate[700]} />
                        </TouchableOpacity>
                        <Text style={styles.zoomIndicatorText}>{zoomScale}x</Text>
                        <TouchableOpacity
                          style={styles.zoomActionBtn}
                          onPress={() => setZoomScale((z) => Math.min(3, Number((z + 0.25).toFixed(2))))}
                        >
                          <Ionicons name="add" size={14} color={Palette.slate[700]} />
                        </TouchableOpacity>
                      </View>
                    </View>

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
                            source={{ uri: selectedCase.imageUrl }}
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
                    (selectedCase.status === "critical" || selectedCase.status === "warning") &&
                      styles.modalFindingCritical,
                    selectedCase.status === "normal" && styles.modalFindingNormal,
                  ]}
                >
                  <Ionicons
                    name={
                      selectedCase.status === "critical" || selectedCase.status === "warning"
                        ? "alert-circle"
                        : "checkmark-circle"
                    }
                    size={24}
                    color={
                      selectedCase.status === "critical" || selectedCase.status === "warning"
                        ? Palette.danger
                        : Palette.success
                    }
                  />
                  <View style={{ flex: 1 }}>
                    <Text style={styles.modalFindingTitle}>{selectedCase.finding}</Text>
                    <Text style={styles.modalFindingSub}>
                      AI Confidence Score: {selectedCase.confidence}
                    </Text>
                  </View>
                </View>

                {/* 4-Step Ward Progression Stepper */}
                <View style={styles.modalTrackerSection}>
                  <Text style={styles.modalTrackerHeading}>WARD ROUNDS SCAN STATUS</Text>
                  <View style={styles.modalStepperList}>
                    {getCaseWorkflowSteps(selectedCase).map((st) => (
                      <View key={st.stepNumber} style={styles.modalStepItem}>
                        <View
                          style={[
                            styles.modalStepCircle,
                            st.completed && styles.modalStepCircleDone,
                          ]}
                        >
                          {st.completed ? (
                            <Ionicons name="checkmark" size={11} color="#FFFFFF" />
                          ) : (
                            <Text style={styles.modalStepNumText}>{st.stepNumber}</Text>
                          )}
                        </View>
                        <View style={{ flex: 1 }}>
                          <View style={styles.modalStepTitleRow}>
                            <Text
                              style={[
                                styles.modalStepTitle,
                                st.completed && styles.modalStepTitleDone,
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

                {/* Hand-off / Navigation Buttons */}
                <View style={styles.modalActionCol}>
                  <TouchableOpacity
                    style={styles.openTrackerBtn}
                    onPress={() => handleOpenInWardRounds(selectedCase)}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="walk-outline" size={16} color="#FFFFFF" />
                    <Text style={styles.openTrackerBtnText}>Open in Ward Rounds Tracker</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.workstationNoticeBtn}
                    onPress={() => {
                      Alert.alert(
                        "Clinical Review",
                        "Diagnostic evaluation and formal signing can be completed on your desktop PACS workstation."
                      );
                      setSelectedCase(null);
                    }}
                    activeOpacity={0.8}
                  >
                    <Ionicons name="desktop-outline" size={16} color={Palette.primary} />
                    <Text style={styles.workstationNoticeBtnText}>Sign on Desktop Workstation</Text>
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
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: Spacing.xl,
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
    color: Palette.slate[500],
    fontWeight: "600",
  },
  container: {
    flex: 1,
    backgroundColor: Palette.slate[50],
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
    backgroundColor: Palette.white,
    borderBottomWidth: 1,
    borderBottomColor: Palette.slate[200],
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: Radius.md,
    backgroundColor: Palette.slate[100],
    justifyContent: "center",
    alignItems: "center",
  },
  headerCenter: {
    alignItems: "center",
  },
  headerTitle: {
    fontSize: 17,
    fontWeight: "800",
    color: Palette.slate[900],
    letterSpacing: -0.3,
  },
  headerSubtitle: {
    fontSize: 12,
    color: Palette.slate[500],
    marginTop: 1,
  },
  markReadButton: {
    width: 40,
    height: 40,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryLight,
    justifyContent: "center",
    alignItems: "center",
  },
  filterRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: Spacing.lg,
    paddingVertical: Spacing.md,
  },
  filterChip: {
    paddingVertical: 6,
    paddingHorizontal: 14,
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
    fontWeight: "700",
    color: Palette.slate[700],
  },
  filterChipTextActive: {
    color: "#FFFFFF",
  },
  scrollList: {
    paddingHorizontal: Spacing.lg,
    paddingBottom: Spacing.xxl,
  },
  notificationCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.lg,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    ...Shadows.sm,
  },
  unreadCard: {
    borderLeftWidth: 4,
    borderLeftColor: Palette.primary,
    backgroundColor: "#FBFDFF",
  },
  unreadAlertCard: {
    borderLeftWidth: 4,
    borderLeftColor: Palette.danger,
    backgroundColor: "#FFFBFB",
  },
  cardHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 8,
  },
  iconTitleRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    flex: 1,
  },
  iconBadge: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    backgroundColor: Palette.slate[100],
    justifyContent: "center",
    alignItems: "center",
  },
  alertBadge: {
    backgroundColor: Palette.dangerLight,
  },
  scanBadge: {
    backgroundColor: Palette.primaryLight,
  },
  titleColumn: {
    flex: 1,
  },
  itemTitle: {
    fontSize: 14,
    fontWeight: "800",
    color: Palette.slate[900],
  },
  itemTime: {
    fontSize: 11,
    color: Palette.slate[400],
    marginTop: 1,
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: Palette.primary,
    marginTop: 4,
    marginLeft: 6,
  },
  itemMessage: {
    fontSize: 13,
    color: Palette.slate[600],
    lineHeight: 18,
  },
  caseFooterHint: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: Spacing.sm,
    paddingTop: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Palette.slate[100],
  },
  caseBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  caseBadgeText: {
    fontSize: 11,
    fontWeight: "600",
    color: Palette.slate[600],
  },
  inspectHint: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
  },
  inspectHintText: {
    fontSize: 11,
    fontWeight: "700",
    color: Palette.primary,
  },
  emptyCard: {
    backgroundColor: Palette.white,
    borderRadius: Radius.xl,
    padding: Spacing.xl,
    alignItems: "center",
    marginTop: Spacing.xl,
    borderWidth: 1,
    borderColor: Palette.slate[200],
  },
  emptyIconCircle: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: Palette.slate[100],
    justifyContent: "center",
    alignItems: "center",
    marginBottom: Spacing.md,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: "800",
    color: Palette.slate[900],
    marginBottom: 4,
  },
  emptyText: {
    fontSize: 12,
    color: Palette.slate[500],
    textAlign: "center",
    lineHeight: 17,
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
    borderRadius: 16,
    backgroundColor: Palette.slate[100],
    justifyContent: "center",
    alignItems: "center",
  },
  cxrViewerContainer: {
    backgroundColor: "#0A0F1D",
    borderRadius: Radius.lg,
    padding: Spacing.sm,
    marginBottom: Spacing.md,
    overflow: "hidden",
  },
  cxrControlsHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: Spacing.sm,
  },
  cxrPillsRow: {
    flexDirection: "row",
    gap: 4,
  },
  cxrModePill: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: Radius.sm,
    backgroundColor: "rgba(255,255,255,0.12)",
  },
  cxrModePillActive: {
    backgroundColor: Palette.primary,
  },
  cxrModePillText: {
    fontSize: 10,
    fontWeight: "700",
    color: Palette.slate[300],
  },
  cxrModePillTextActive: {
    color: "#FFFFFF",
  },
  zoomActionsRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "rgba(255,255,255,0.12)",
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: Radius.sm,
  },
  zoomActionBtn: {
    padding: 2,
  },
  zoomIndicatorText: {
    fontSize: 10,
    fontWeight: "700",
    color: "#FFFFFF",
    minWidth: 24,
    textAlign: "center",
  },
  cxrCanvas: {
    width: 280,
    height: 220,
    justifyContent: "center",
    alignItems: "center",
  },
  canvasInverted: {
    backgroundColor: "#E2E8F0",
  },
  canvasHighContrast: {
    backgroundColor: "#000000",
  },
  imagePreview: {
    width: 270,
    height: 210,
  },
  imageBadge: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    marginTop: 6,
  },
  imageBadgeText: {
    fontSize: 10,
    color: Palette.slate[400],
  },
  noImageBox: {
    height: 120,
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
  modalTrackerSection: {
    backgroundColor: Palette.slate[50],
    borderRadius: Radius.lg,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: Palette.slate[200],
    marginBottom: Spacing.md,
  },
  modalTrackerHeading: {
    fontSize: 11,
    fontWeight: "800",
    color: Palette.slate[500],
    letterSpacing: 0.8,
    marginBottom: Spacing.sm,
  },
  modalStepperList: {
    gap: 8,
  },
  modalStepItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
  },
  modalStepCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: Palette.slate[200],
    justifyContent: "center",
    alignItems: "center",
    marginTop: 1,
  },
  modalStepCircleDone: {
    backgroundColor: Palette.success,
  },
  modalStepNumText: {
    fontSize: 10,
    fontWeight: "700",
    color: Palette.slate[600],
  },
  modalStepTitleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  modalStepTitle: {
    fontSize: 13,
    fontWeight: "700",
    color: Palette.slate[700],
  },
  modalStepTitleDone: {
    color: Palette.slate[900],
  },
  modalStepTime: {
    fontSize: 11,
    color: Palette.slate[400],
  },
  modalStepSub: {
    fontSize: 11,
    color: Palette.slate[500],
  },
  modalActionCol: {
    gap: Spacing.sm,
    marginBottom: Spacing.md,
  },
  openTrackerBtn: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    height: 48,
    borderRadius: Radius.md,
    backgroundColor: Palette.primary,
  },
  openTrackerBtnText: {
    fontSize: 14,
    fontWeight: "700",
    color: "#FFFFFF",
  },
  workstationNoticeBtn: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    height: 44,
    borderRadius: Radius.md,
    backgroundColor: Palette.primaryLight,
  },
  workstationNoticeBtnText: {
    fontSize: 13,
    fontWeight: "700",
    color: Palette.primary,
  },
});
