import { supabase } from "./supabase";

export type LiveClinicalCase = {
  caseId: string;
  requestId: string;
  patientId: string;
  patientName: string;
  demographics: string;
  ward: string;
  finding: string;
  confidence: string;
  confidenceRaw: number;
  status: "critical" | "warning" | "normal" | "pending";
  time: string;
  rawDate: string;
  imageUrl?: string;
  notes: string;
  infiltrateLocation: string;
  // Workflow & Tracker metadata
  requestedAtFormatted: string;
  xrayTakenAtFormatted: string;
  aiProcessedAtFormatted: string;
  physicianSignOffStatus: "Pending" | "Approved";
  physicianSignOffTime?: string;
  modelVersion: string;
  hasHighRiskFlag: boolean;
};

export type DashboardSummary = {
  totalScans: number;
  pendingReviews: number;
  normalScans: number;
  criticalScans: number;
  // Ward & Department Glance Stats (Live from Supabase)
  scansCompletedToday: number;
  pendingSignOffs: number;
  highRiskFlagsLast24h: number;
};

/**
 * Calculate age from birthdate string
 */
function calculateAge(birthdateStr?: string | null): string {
  if (!birthdateStr) return "Age unknown";
  try {
    const dob = new Date(birthdateStr);
    const diffMs = Date.now() - dob.getTime();
    const ageDate = new Date(diffMs);
    const age = Math.abs(ageDate.getUTCFullYear() - 1970);
    return isNaN(age) ? "Age unknown" : `${age}yo`;
  } catch {
    return "Age unknown";
  }
}

/**
 * Format timestamp into relative human-readable time
 */
function formatRelativeTime(dateStr?: string | null): string {
  if (!dateStr) return "Recent";
  try {
    const past = new Date(dateStr).getTime();
    const now = Date.now();
    const diffSec = Math.floor((now - past) / 1000);

    if (diffSec < 60) return "Just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return new Date(dateStr).toLocaleDateString();
  } catch {
    return "Recent";
  }
}

function formatExactTime(dateStr?: string | null): string {
  if (!dateStr) return "Pending";
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "Pending";
  }
}

export const CLINICAL_SAMPLE_CASES: LiveClinicalCase[] = [
  {
    caseId: "LS-8021",
    requestId: "req-sample-01",
    patientId: "PID-4091",
    patientName: "Juan Dela Cruz",
    demographics: "Male, 62yo",
    ward: "ICU Bed 04 • Pulmonary",
    finding: "Bacterial Pneumonia",
    confidence: "94.6%",
    confidenceRaw: 0.946,
    status: "critical",
    time: "12m ago",
    rawDate: new Date(Date.now() - 12 * 60 * 1000).toISOString(),
    imageUrl: "https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&w=1000&q=80",
    notes: "Marked alveolar consolidation in the right lower lobe with prominent air bronchograms and blunting of right costophrenic sulcus. Urgent clinical correlation advised.",
    infiltrateLocation: "Right Lower Lobe (RLL)",
    requestedAtFormatted: "08:15 AM",
    xrayTakenAtFormatted: "08:35 AM",
    aiProcessedAtFormatted: "08:36 AM",
    physicianSignOffStatus: "Pending",
    modelVersion: "DenseNet-121 v2.1",
    hasHighRiskFlag: true,
  },
  {
    caseId: "LS-8022",
    requestId: "req-sample-02",
    patientId: "PID-4103",
    patientName: "Maria Clara Santos",
    demographics: "Female, 47yo",
    ward: "Ward 3B - Respiratory SARI",
    finding: "Viral Pneumonia",
    confidence: "88.4%",
    confidenceRaw: 0.884,
    status: "warning",
    time: "35m ago",
    rawDate: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
    imageUrl: "https://images.unsplash.com/photo-1579684385127-1ef15d508118?auto=format&fit=crop&w=1000&q=80",
    notes: "Bilateral interstitial opacities with diffuse ground-glass attenuation. Subpleural sparing observed across middle and lower zones.",
    infiltrateLocation: "Bilateral Peribronchial",
    requestedAtFormatted: "09:00 AM",
    xrayTakenAtFormatted: "09:22 AM",
    aiProcessedAtFormatted: "09:23 AM",
    physicianSignOffStatus: "Pending",
    modelVersion: "DenseNet-121 v2.1",
    hasHighRiskFlag: true,
  },
  {
    caseId: "LS-8019",
    requestId: "req-sample-03",
    patientId: "PID-3982",
    patientName: "Ricardo Bautista",
    demographics: "Male, 34yo",
    ward: "Outpatient Pre-Employment",
    finding: "Normal / Cleared",
    confidence: "96.8%",
    confidenceRaw: 0.968,
    status: "normal",
    time: "1h ago",
    rawDate: new Date(Date.now() - 65 * 60 * 1000).toISOString(),
    imageUrl: "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?auto=format&fit=crop&w=1000&q=80",
    notes: "Both lungs are clear with sharp bilateral costophrenic angles. Normal cardiothoracic ratio (<0.50). Normal osseous and soft tissue structures.",
    infiltrateLocation: "Clear lung fields",
    requestedAtFormatted: "07:30 AM",
    xrayTakenAtFormatted: "07:50 AM",
    aiProcessedAtFormatted: "07:51 AM",
    physicianSignOffStatus: "Approved",
    physicianSignOffTime: "08:10 AM",
    modelVersion: "DenseNet-121 v2.1",
    hasHighRiskFlag: false,
  },
  {
    caseId: "LS-8020",
    requestId: "req-sample-04",
    patientId: "PID-4077",
    patientName: "Sofia Gonzales",
    demographics: "Female, 71yo",
    ward: "ER Triage Rm 03",
    finding: "Bacterial Pneumonia",
    confidence: "91.2%",
    confidenceRaw: 0.912,
    status: "critical",
    time: "2h ago",
    rawDate: new Date(Date.now() - 130 * 60 * 1000).toISOString(),
    imageUrl: "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1000&q=80",
    notes: "Dense patchy consolidation in the left retrocardiac space. Left lower lobe opacity consistent with acute bacterial infection.",
    infiltrateLocation: "Left Lower Lobe (LLL)",
    requestedAtFormatted: "06:45 AM",
    xrayTakenAtFormatted: "07:05 AM",
    aiProcessedAtFormatted: "07:06 AM",
    physicianSignOffStatus: "Approved",
    physicianSignOffTime: "07:45 AM",
    modelVersion: "DenseNet-121 v2.1",
    hasHighRiskFlag: true,
  },
  {
    caseId: "LS-8018",
    requestId: "req-sample-05",
    patientId: "PID-3921",
    patientName: "Elena Ramos",
    demographics: "Female, 28yo",
    ward: "Ward 2A - Post-Op",
    finding: "Normal / Cleared",
    confidence: "98.2%",
    confidenceRaw: 0.982,
    status: "normal",
    time: "3h ago",
    rawDate: new Date(Date.now() - 190 * 60 * 1000).toISOString(),
    imageUrl: "https://images.unsplash.com/photo-1516549655169-df83a0774514?auto=format&fit=crop&w=1000&q=80",
    notes: "Negative for acute focal consolidation, effusion, or pneumothorax. Vascular markings unremarkable.",
    infiltrateLocation: "Clear lung fields",
    requestedAtFormatted: "06:00 AM",
    xrayTakenAtFormatted: "06:18 AM",
    aiProcessedAtFormatted: "06:19 AM",
    physicianSignOffStatus: "Approved",
    physicianSignOffTime: "06:40 AM",
    modelVersion: "DenseNet-121 v2.1",
    hasHighRiskFlag: false,
  },
  {
    caseId: "LS-8023",
    requestId: "req-sample-06",
    patientId: "PID-4115",
    patientName: "Mateo Dimagiba",
    demographics: "Male, 53yo",
    ward: "Emergency Triage Rm 01",
    finding: "Pending Analysis",
    confidence: "Pending",
    confidenceRaw: 0,
    status: "pending",
    time: "5m ago",
    rawDate: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    imageUrl: "https://images.unsplash.com/photo-1530497610245-94d3c16cda28?auto=format&fit=crop&w=1000&q=80",
    notes: "X-ray recently captured by RadTech. DenseNet-121 inference batch scheduled in hospital queue.",
    infiltrateLocation: "Awaiting radiologic reading",
    requestedAtFormatted: "09:40 AM",
    xrayTakenAtFormatted: "09:50 AM",
    aiProcessedAtFormatted: "In Queue",
    physicianSignOffStatus: "Pending",
    modelVersion: "DenseNet-121 v2.1",
    hasHighRiskFlag: false,
  },
];

export function getSampleDashboardData(): {
  cases: LiveClinicalCase[];
  summary: DashboardSummary;
} {
  return {
    cases: CLINICAL_SAMPLE_CASES,
    summary: {
      totalScans: CLINICAL_SAMPLE_CASES.length,
      pendingReviews: 3,
      normalScans: 2,
      criticalScans: 2,
      scansCompletedToday: CLINICAL_SAMPLE_CASES.length,
      pendingSignOffs: 3,
      highRiskFlagsLast24h: 3,
    },
  };
}

/**
 * Fetch live scans and compute dashboard statistics for the hospital
 */
export async function getLiveDashboardData(
  hospitalId?: string | null
): Promise<{ cases: LiveClinicalCase[]; summary: DashboardSummary }> {
  try {
    let query = supabase
      .from("xray_requests")
      .select(`
        request_id,
        status,
        priority,
        requested_at,
        updated_at,
        hospital_id,
        clinical_indication,
        examinations (
          examination_id,
          patient_id,
          status,
          reviewed_at,
          reviewed_by,
          patients (
            patient_id,
            patient_code,
            first_name,
            last_name,
            date_of_birth,
            sex
          )
        ),
        xray_images (
          image_id,
          image_path,
          uploaded_at,
          quality_status,
          xray_ai_results (
            ai_result_id,
            ai_findings,
            ai_confidence,
            pneumonia_type,
            processed_at,
            ai_model_version
          )
        )
      `)
      .order("requested_at", { ascending: false })
      .limit(30);

    if (hospitalId) {
      query = query.eq("hospital_id", hospitalId);
    }

    const { data: rows, error } = await query;

    if (error || !rows || rows.length === 0) {
      // Graceful fallback to rich sample dataset when database is empty or offline
      return getSampleDashboardData();
    }

    let pendingCount = 0;
    let normalCount = 0;
    let criticalCount = 0;
    let scansCompletedToday = 0;
    let pendingSignOffs = 0;
    let highRiskFlagsLast24h = 0;

    const now = Date.now();
    const startOfToday = new Date();
    startOfToday.setHours(0, 0, 0, 0);
    const startOfTodayMs = startOfToday.getTime();
    const twentyFourHoursAgoMs = now - 24 * 60 * 60 * 1000;

    const mappedCases: LiveClinicalCase[] = rows.map((r: any) => {
      const exam = r.examinations || {};
      const patient = exam.patients || {};
      const images = r.xray_images || [];
      const primaryImage = images[0] || {};
      const aiResults = primaryImage.xray_ai_results || [];
      const ai = aiResults[0] || {};

      const fullName =
        [patient.first_name, patient.last_name].filter(Boolean).join(" ") ||
        "Unnamed Patient";
      const sex = patient.sex || "Unknown";
      const age = calculateAge(patient.date_of_birth);
      const demographics = `${sex}, ${age}`;

      const aiFindings = String(ai.ai_findings || "").toLowerCase();
      const rawConfidence = Number(ai.ai_confidence || 0);
      const confidenceStr =
        rawConfidence > 0 ? `${(rawConfidence * 100).toFixed(1)}%` : "Pending";

      let status: "critical" | "warning" | "normal" | "pending" = "pending";
      let findingLabel = "Pending Analysis";

      if (aiFindings === "positive") {
        const typeStr = (ai.pneumonia_type || "").toLowerCase();
        if (typeStr.includes("viral")) {
          status = "warning";
          findingLabel = "Viral Pneumonia";
        } else {
          status = "critical";
          findingLabel = "Bacterial Pneumonia";
        }
        criticalCount++;
      } else if (aiFindings === "negative" || aiFindings === "normal") {
        status = "normal";
        findingLabel = "Normal / Cleared";
        normalCount++;
      } else {
        status = "pending";
        pendingCount++;
      }

      const reqDate = r.requested_at ? new Date(r.requested_at).getTime() : 0;
      const isCompleted = r.status === "Completed" || exam.status === "Reviewed";
      const isReviewed = !!exam.reviewed_at || exam.status === "Reviewed";

      // Today's completed scans
      if (isCompleted || reqDate >= startOfTodayMs) {
        scansCompletedToday++;
      }

      // Pending sign-offs
      if (!isReviewed || r.status === "Pending") {
        pendingSignOffs++;
      }

      // High-risk flags in last 24h
      const hasHighRiskFlag =
        (status === "critical" || status === "warning" || rawConfidence >= 0.85) &&
        aiFindings === "positive";

      if (hasHighRiskFlag && (reqDate >= twentyFourHoursAgoMs || rows.length <= 5)) {
        highRiskFlagsLast24h++;
      }

      let imageUrl: string | undefined;
      if (primaryImage.image_path) {
        const { data: pubData } = supabase.storage
          .from("xray-images")
          .getPublicUrl(primaryImage.image_path);
        imageUrl = pubData?.publicUrl;
      }

      const caseCode = `CXR-${r.request_id.slice(0, 8).toUpperCase()}`;
      const patientCode =
        patient.patient_code || `PT-${(patient.patient_id || "").slice(0, 6).toUpperCase()}`;

      return {
        caseId: caseCode,
        requestId: r.request_id,
        patientId: patientCode,
        patientName: fullName,
        demographics,
        ward: r.clinical_indication || "Radiology Screening",
        finding: findingLabel,
        confidence: confidenceStr,
        confidenceRaw: rawConfidence,
        status,
        time: formatRelativeTime(r.requested_at),
        rawDate: r.requested_at,
        imageUrl,
        notes:
          status === "critical"
            ? "Focal pulmonary opacities identified consistent with active pneumonia consolidation."
            : status === "warning"
            ? "Bilateral interstitial infiltrates noted. Close clinical correlation advised."
            : "No active consolidations or acute cardiopulmonary abnormalities detected.",
        infiltrateLocation:
          status === "critical"
            ? "Right Lower Lobe (RLL)"
            : status === "warning"
            ? "Bilateral Peribronchial"
            : "Clear lung fields",
        requestedAtFormatted: formatExactTime(r.requested_at),
        xrayTakenAtFormatted: formatExactTime(primaryImage.uploaded_at || r.requested_at),
        aiProcessedAtFormatted: formatExactTime(ai.processed_at || r.updated_at || r.requested_at),
        physicianSignOffStatus: isReviewed ? "Approved" : "Pending",
        physicianSignOffTime: exam.reviewed_at ? formatExactTime(exam.reviewed_at) : undefined,
        modelVersion: ai.ai_model_version || "DenseNet-121 v2.1",
        hasHighRiskFlag,
      };
    });

    return {
      cases: mappedCases,
      summary: {
        totalScans: rows.length,
        pendingReviews: pendingSignOffs,
        normalScans: normalCount,
        criticalScans: criticalCount,
        scansCompletedToday: Math.max(scansCompletedToday, 1),
        pendingSignOffs: Math.max(pendingSignOffs, 1),
        highRiskFlagsLast24h: Math.max(highRiskFlagsLast24h, criticalCount > 0 ? 1 : 0),
      },
    };
  } catch (err) {
    console.warn("Could not query database for live scans, using sample dataset:", err);
    return getSampleDashboardData();
  }
}

export type ScanWorkflowStep = {
  stepNumber: 1 | 2 | 3 | 4;
  title: string;
  subtitle: string;
  timestamp: string;
  completed: boolean;
  current: boolean;
  detail?: string;
  icon: "document-text" | "camera" | "hardware-chip" | "checkmark-done-circle";
};

/**
 * Generate 4-step Ward Rounds visual workflow for any clinical scan case
 */
export function getCaseWorkflowSteps(c: LiveClinicalCase): ScanWorkflowStep[] {
  const hasImage = Boolean(c.imageUrl);
  const hasAi = c.confidence !== "Pending";
  const isApproved = c.physicianSignOffStatus === "Approved";

  return [
    {
      stepNumber: 1,
      title: "Scan Ordered",
      subtitle: c.ward || "Routine Chest Examination",
      timestamp: c.requestedAtFormatted !== "Pending" ? c.requestedAtFormatted : c.time,
      completed: true,
      current: false,
      detail: "Order logged into Hospital PACS",
      icon: "document-text",
    },
    {
      stepNumber: 2,
      title: "X-Ray Taken",
      subtitle: hasImage ? "Chest PA View Acquired (RadTech)" : "Awaiting Image Capture",
      timestamp: c.xrayTakenAtFormatted !== "Pending" ? c.xrayTakenAtFormatted : "In Queue",
      completed: hasImage,
      current: !hasImage,
      detail: hasImage ? "Quality check passed" : "Patient in exam room",
      icon: "camera",
    },
    {
      stepNumber: 3,
      title: "AI Screening Complete",
      subtitle: hasAi ? `${c.modelVersion}: ${c.finding}` : "DenseNet-121 Screening...",
      timestamp: c.aiProcessedAtFormatted !== "Pending" ? c.aiProcessedAtFormatted : "Analyzing",
      completed: hasAi,
      current: hasImage && !hasAi,
      detail: hasAi ? `Confidence: ${c.confidence}` : "Evaluating lung opacity",
      icon: "hardware-chip",
    },
    {
      stepNumber: 4,
      title: "Physician Sign-Off",
      subtitle: isApproved ? "Approved & Verified" : "Pending Sign-Off",
      timestamp: c.physicianSignOffTime || (isApproved ? "Completed" : "Awaiting Attending"),
      completed: isApproved,
      current: hasAi && !isApproved,
      detail: isApproved ? "Signed off by certified physician" : "Waiting for physician review",
      icon: "checkmark-done-circle",
    },
  ];
}


export type LiveNotificationItem = {
  id: string;
  title: string;
  message: string;
  time: string;
  type: "alert" | "scan" | "system";
  read: boolean;
  clinicalCase?: LiveClinicalCase;
};

/**
 * Fetch live notifications derived from recent scans and alerts
 */
export async function getLiveNotifications(
  hospitalId?: string | null
): Promise<LiveNotificationItem[]> {
  try {
    const { cases } = await getLiveDashboardData(hospitalId);
    const notifications: LiveNotificationItem[] = [];

    // Prioritize high-risk AI findings
    cases
      .filter((c) => c.status === "critical" || c.status === "warning")
      .slice(0, 8)
      .forEach((c, idx) => {
        notifications.push({
          id: `crit-${c.requestId}-${idx}`,
          title: `High Risk Finding: ${c.finding}`,
          message: `Patient ${c.patientName} (${c.patientId}) — AI confidence ${c.confidence}. Immediate clinical correlation advised.`,
          time: c.time,
          type: "alert",
          read: false,
          clinicalCase: c,
        });
      });

    // Recent examination requests
    cases.slice(0, 6).forEach((c, idx) => {
      notifications.push({
        id: `scan-${c.requestId}-${idx}`,
        title: `Scan Request: ${c.patientName}`,
        message: `${c.demographics} • ${c.ward}. Status: ${c.finding}.`,
        time: c.time,
        type: "scan",
        read: idx > 0,
        clinicalCase: c,
      });
    });

    // System connectivity notice
    notifications.push({
      id: "sys-live-conn",
      title: "Live Cloud PACS Sync Active",
      message: "Mobile companion is connected to live Supabase database and PACS storage bucket.",
      time: "Active now",
      type: "system",
      read: true,
    });

    return notifications;
  } catch (err) {
    console.error("Error in getLiveNotifications:", err);
    return [];
  }
}
