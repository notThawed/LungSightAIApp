// Email templates: branded HTML + plain text, every dynamic value escaped.
//
// Wording rules: received != approved, approved != active, a reminder never
// claims a payment happened. No PHI, AI results, or payment amounts. Subjects
// are fixed strings (no user-supplied text in headers). Emails to the
// unverified applicant address (receipt, rejection) carry no links.
//
// Layout uses tables and inline styles only, so it renders in Gmail, Outlook
// and mobile clients.

export type TemplateRow = {
  email_id: string;
  event_type: string;
  template_data: Record<string, unknown>;
};

export type RenderOptions = {
  appBaseUrl: string;
  subjectPrefix?: string;
};

export type RenderedEmail = { subject: string; html: string; text: string };

export class UnknownTemplateError extends Error {
  constructor(eventType: string) {
    super(`no template for ${eventType}`);
    this.name = "UnknownTemplateError";
  }
}

const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

const BRAND = {
  name: "LungSight AI",
  tagline: "Screening support for hospital imaging teams",
  primary: "#0E7490",
  primaryDark: "#155E75",
  ink: "#0F172A",
  body: "#334155",
  muted: "#64748B",
  line: "#E2E8F0",
  panel: "#F1F5F9",
  page: "#EEF2F6",
};

export function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function plain(value: unknown, max = 120): string {
  return String(value ?? "").replace(/[\u0000-\u001f\u007f]+/g, " ").trim().slice(0, max);
}

export function formatDate(value: unknown): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value ?? ""));
  if (!match) return "—";
  const month = Number(match[2]);
  if (month < 1 || month > 12) return "—";
  return `${MONTHS[month - 1]} ${Number(match[3])}, ${match[1]}`;
}

function intValue(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
}

export function safeBaseUrl(value: string): string | null {
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    url.hash = "";
    url.search = "";
    return url.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}

type Body = {
  subject: string;
  preheader: string;
  heading: string;
  paragraphs: string[];
  details?: [string, string][];
  after?: string[];
  cta?: string;
};

function reference(d: Record<string, unknown>): string {
  return /^[A-Z0-9]{8}$/.test(String(d.reference ?? "")) ? String(d.reference) : "—";
}

function bodyFor(row: TemplateRow): Body {
  const d = row.template_data ?? {};
  const hospital = plain(d.hospital_name) || "your hospital";
  const plan = plain(d.plan_name, 60);

  switch (row.event_type) {
    case "application.received":
      return {
        subject: "LungSight: we received a hospital application",
        preheader: "Your hospital application has been received and is waiting for review.",
        heading: "Application received",
        paragraphs: [
          "Hello,",
          "We received a hospital application that listed this email address as the contact.",
        ],
        details: [["Reference", reference(d)]],
        after: [
          "Our team will review the application. Receiving this message does not mean the application has been approved.",
          "If you did not submit an application, you can ignore this email.",
        ],
      };

    case "application.rejected":
      return {
        subject: "LungSight: update on your hospital application",
        preheader: "An update on the hospital application you submitted.",
        heading: "Application update",
        paragraphs: [
          "Hello,",
          "We have reviewed the hospital application that listed this email address as the contact.",
        ],
        details: [["Reference", reference(d)]],
        after: [
          "We are unable to approve this application at this time.",
          "If you have questions, please contact the LungSight team and mention the reference above.",
          "If you did not submit an application, you can ignore this email.",
        ],
      };

    case "application.approved":
      return {
        subject: "LungSight: hospital application approved",
        preheader: "Your hospital application was approved. Here is what happens next.",
        heading: "Application approved",
        paragraphs: [
          "Hello,",
          `Good news: the LungSight application for ${hospital} has been approved.`,
        ],
        details: [["Hospital", hospital]],
        after: [
          "Next steps:",
          "1. Look for a separate invitation email and set your password.",
          "2. Sign in and complete the hospital setup.",
          "The subscription becomes active only after the setup is completed.",
        ],
        cta: "Sign in to LungSight",
      };

    case "subscription.activated":
      return {
        subject: "LungSight: subscription active",
        preheader: `The LungSight subscription for ${hospital} is now active.`,
        heading: "Subscription active",
        paragraphs: [
          "Hello,",
          `The LungSight subscription for ${hospital} is now active${plan ? ` on the ${plan} plan` : ""}.`,
        ],
        details: [
          ["Hospital", hospital],
          ...(plan ? [["Plan", plan] as [string, string]] : []),
          ["Current period ends", formatDate(d.end_date)],
        ],
        cta: "Open LungSight",
      };

    case "subscription.renewed":
      return {
        subject: "LungSight: subscription renewed",
        preheader: `The renewal for ${hospital} has been applied.`,
        heading: "Subscription renewed",
        paragraphs: [
          "Hello,",
          `The renewal for ${hospital} has been applied.`,
        ],
        details: [
          ["Hospital", hospital],
          ["Subscription runs until", formatDate(d.end_date)],
        ],
        cta: "View subscription settings",
      };

    case "subscription.expiry_reminder": {
      const days = intValue(d.days_left);
      const when = days === 0
        ? `today, ${formatDate(d.end_date)}`
        : `in ${days ?? "a few"} day${days === 1 ? "" : "s"}, on ${formatDate(d.end_date)}`;
      return {
        subject: days === 0 ? "LungSight: subscription ends today" : "LungSight: subscription ending soon",
        preheader: `The LungSight subscription for ${hospital} ends ${when}.`,
        heading: days === 0 ? "Subscription ends today" : "Subscription ending soon",
        paragraphs: [
          "Hello,",
          `The LungSight subscription for ${hospital} ends ${when}.`,
        ],
        details: [
          ["Hospital", hospital],
          ["End date", formatDate(d.end_date)],
        ],
        after: [
          "To keep access without interruption, a Hospital Admin can renew from Subscription Settings.",
          "If you have already renewed, you can ignore this reminder.",
        ],
        cta: "Review subscription",
      };
    }

    case "ops.alert": {
      const count = intValue(d.count) ?? 0;
      const alerts: Record<string, string> = {
        payments_not_applied: `${count} paid payment(s) have not been applied to an application or subscription after 15 minutes.`,
        email_failures: `${count} email(s) failed permanently in the last hour.`,
      };
      const line = alerts[String(d.alert)];
      if (!line) throw new UnknownTemplateError(`ops.alert:${String(d.alert)}`);
      return {
        subject: "LungSight operations alert",
        preheader: line,
        heading: "Operations alert",
        paragraphs: [line],
        after: ["Sign in to LungSight to review. This alert repeats at most once a day."],
        cta: "Open LungSight",
      };
    }

    default:
      throw new UnknownTemplateError(row.event_type);
  }
}

const FOOTER_LINES = [
  `${BRAND.name} — ${BRAND.tagline}`,
  "This is an automated message. Please do not reply, and never send patient information by email.",
];

function paragraphHtml(text: string): string {
  return `<p style="margin:0 0 16px;font-size:15px;line-height:24px;color:${BRAND.body}">${escapeHtml(text)}</p>`;
}

function detailsHtml(details: [string, string][]): string {
  const rows = details.map(([label, value], index) =>
    `<tr>` +
    `<td style="padding:10px 16px;font-size:13px;color:${BRAND.muted};${index ? `border-top:1px solid ${BRAND.line};` : ""}">${escapeHtml(label)}</td>` +
    `<td align="right" style="padding:10px 16px;font-size:14px;font-weight:bold;color:${BRAND.ink};${index ? `border-top:1px solid ${BRAND.line};` : ""}">${escapeHtml(value)}</td>` +
    `</tr>`).join("");
  return `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" ` +
    `style="margin:4px 0 20px;background:${BRAND.panel};border:1px solid ${BRAND.line};border-radius:10px;border-collapse:separate">${rows}</table>`;
}

function buttonHtml(label: string, href: string): string {
  return `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:8px 0 24px"><tr>` +
    `<td align="center" bgcolor="${BRAND.primary}" style="border-radius:8px">` +
    `<a href="${escapeHtml(href)}" target="_blank" style="display:inline-block;padding:13px 26px;font-size:15px;` +
    `font-weight:bold;color:#ffffff;text-decoration:none;border-radius:8px">${escapeHtml(label)} &rarr;</a>` +
    `</td></tr></table>` +
    `<p style="margin:0 0 6px;font-size:12px;line-height:18px;color:${BRAND.muted}">If the button doesn't work, copy and paste this link into your browser:</p>` +
    `<p style="margin:0 0 20px;font-size:12px;line-height:18px;word-break:break-all"><a href="${escapeHtml(href)}" target="_blank" ` +
    `style="color:${BRAND.primary};text-decoration:underline">${escapeHtml(href)}</a></p>`;
}

function layoutHtml(body: Body, link: string | null): string {
  return `<!doctype html>` +
    `<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">` +
    `<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">` +
    `<title>${escapeHtml(body.heading)}</title></head>` +
    `<body style="margin:0;padding:0;background:${BRAND.page}">` +
    `<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">${escapeHtml(body.preheader)}</div>` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:${BRAND.page}">` +
    `<tr><td align="center" style="padding:32px 12px">` +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" ` +
    `style="max-width:600px;background:#ffffff;border:1px solid ${BRAND.line};border-radius:14px;border-collapse:separate;overflow:hidden;` +
    `font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif">` +
    // header
    `<tr><td bgcolor="${BRAND.primary}" style="background:${BRAND.primary};padding:22px 32px;border-radius:14px 14px 0 0">` +
    `<span style="font-size:20px;font-weight:bold;letter-spacing:0.3px;color:#ffffff">${escapeHtml(BRAND.name)}</span>` +
    `</td></tr>` +
    // content
    `<tr><td style="padding:32px 32px 8px">` +
    `<h1 style="margin:0 0 20px;font-size:24px;line-height:32px;font-weight:bold;color:${BRAND.ink}">${escapeHtml(body.heading)}</h1>` +
    body.paragraphs.map(paragraphHtml).join("") +
    (body.details && body.details.length ? detailsHtml(body.details) : "") +
    (body.after ?? []).map(paragraphHtml).join("") +
    (body.cta && link ? buttonHtml(body.cta, link) : "") +
    `</td></tr>` +
    // footer
    `<tr><td style="padding:20px 32px 28px;border-top:1px solid ${BRAND.line}">` +
    FOOTER_LINES.map((line, i) =>
      `<p style="margin:${i ? "6px" : "0"} 0 0;font-size:12px;line-height:18px;color:${BRAND.muted}">${escapeHtml(line)}</p>`).join("") +
    `</td></tr>` +
    `</table>` +
    `</td></tr></table></body></html>`;
}

export function renderEmail(row: TemplateRow, options: RenderOptions): RenderedEmail {
  const body = bodyFor(row);
  const base = safeBaseUrl(options.appBaseUrl);
  const link = body.cta && base ? `${base}/` : null;
  const prefix = options.subjectPrefix ? `${plain(options.subjectPrefix, 20)} ` : "";

  const textParts = [body.heading, "", ...body.paragraphs];
  for (const [label, value] of body.details ?? []) textParts.push(`${label}: ${value}`);
  if (body.details?.length) textParts.push("");
  textParts.push(...(body.after ?? []));
  if (body.cta && link) textParts.push("", `${body.cta}: ${link}`);
  textParts.push("", "—", ...FOOTER_LINES);

  return { subject: prefix + body.subject, html: layoutHtml(body, link), text: textParts.join("\n") };
}
