// Email templates: HTML + plain text, every dynamic value escaped.
//
// Wording rules: received != approved, approved != active, a reminder never
// claims a payment happened. No PHI, AI results, or payment amounts. Subjects
// are fixed strings (no user-supplied text in headers).

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

type Body = { subject: string; heading: string; paragraphs: string[]; cta?: string };

function bodyFor(row: TemplateRow): Body {
  const d = row.template_data ?? {};
  const hospital = plain(d.hospital_name) || "your hospital";
  const plan = plain(d.plan_name, 60);

  switch (row.event_type) {
    case "application.received": {
      const reference = /^[A-Z0-9]{8}$/.test(String(d.reference ?? "")) ? String(d.reference) : "—";
      return {
        subject: "LungSight: we received a hospital application",
        heading: "Application received",
        paragraphs: [
          "We received a hospital application that listed this email address as the contact.",
          `Reference: ${reference}`,
          "Our team will review the application. Receiving this message does not mean the application has been approved.",
          "If you did not submit an application, you can ignore this email.",
        ],
      };
    }
    case "application.rejected": {
      const reference = /^[A-Z0-9]{8}$/.test(String(d.reference ?? "")) ? String(d.reference) : "—";
      return {
        subject: "LungSight: update on your hospital application",
        heading: "Application update",
        paragraphs: [
          "We have reviewed the hospital application that listed this email address as the contact.",
          `Reference: ${reference}`,
          "We are unable to approve this application at this time.",
          "If you have questions, please contact the LungSight team and mention the reference above.",
          "If you did not submit an application, you can ignore this email.",
        ],
      };
    }
    case "application.approved":
      return {
        subject: "LungSight: hospital application approved",
        heading: "Application approved",
        paragraphs: [
          `The LungSight application for ${hospital} has been approved.`,
          "You will receive a separate invitation email to set your password. After you sign in, complete the hospital setup.",
          "The subscription becomes active only after the setup is completed.",
        ],
        cta: "Sign in to LungSight",
      };
    case "subscription.activated":
      return {
        subject: "LungSight: subscription active",
        heading: "Subscription active",
        paragraphs: [
          `The LungSight subscription for ${hospital} is now active${plan ? ` on the ${plan} plan` : ""}.`,
          `The current period ends on ${formatDate(d.end_date)}.`,
        ],
        cta: "Open LungSight",
      };
    case "subscription.renewed":
      return {
        subject: "LungSight: subscription renewed",
        heading: "Subscription renewed",
        paragraphs: [
          `The renewal for ${hospital} has been applied.`,
          `The subscription now runs until ${formatDate(d.end_date)}.`,
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
        heading: "Subscription reminder",
        paragraphs: [
          `The LungSight subscription for ${hospital} ends ${when}.`,
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
        heading: "Operations alert",
        paragraphs: [line, "Sign in to LungSight to review. This alert repeats at most once a day."],
        cta: "Open LungSight",
      };
    }
    default:
      throw new UnknownTemplateError(row.event_type);
  }
}

const FOOTER = "This is an automated message from LungSight AI. Do not reply with patient information.";

export function renderEmail(row: TemplateRow, options: RenderOptions): RenderedEmail {
  const body = bodyFor(row);
  const base = safeBaseUrl(options.appBaseUrl);
  const prefix = options.subjectPrefix ? `${plain(options.subjectPrefix, 20)} ` : "";

  const textParts = [body.heading, "", ...body.paragraphs];
  if (body.cta && base) textParts.push("", `${body.cta}: ${base}/`);
  textParts.push("", FOOTER);

  const link = body.cta && base
    ? `<p style="margin:24px 0"><a href="${escapeHtml(base)}/" style="background:#0E7490;color:#ffffff;` +
      `padding:10px 16px;border-radius:6px;text-decoration:none">${escapeHtml(body.cta)}</a></p>`
    : "";

  const html =
    `<!doctype html><html><body style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;line-height:1.5">` +
    `<div style="max-width:560px;margin:0 auto;padding:24px">` +
    `<h2 style="color:#0E7490;margin:0 0 16px">${escapeHtml(body.heading)}</h2>` +
    body.paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join("") +
    link +
    `<p style="color:#64748b;font-size:12px;margin-top:32px">${escapeHtml(FOOTER)}</p>` +
    `</div></body></html>`;

  return { subject: prefix + body.subject, html, text: textParts.join("\n") };
}
