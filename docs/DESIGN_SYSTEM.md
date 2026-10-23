# LungSightAI Design System

One visual language for the Streamlit web workspace and the Expo mobile app.

## Source of truth

All values live in [`shared/theme/tokens.json`](../shared/theme/tokens.json).
They reach each platform like this:

| Platform | How tokens are applied |
|---|---|
| Streamlit (native widgets) | [`.streamlit/config.toml`](../.streamlit/config.toml) `[theme]`: primary, background, text, border, font, radius |
| Streamlit (custom HTML/CSS) | [`shared/theme/streamlit_theme.py`](../shared/theme/streamlit_theme.py) emits `--ls-*` CSS variables. It is injected once at the top of `app.py`, before any page CSS. |
| Page stylesheets | Files in [`shared/theme/css_content/`](../shared/theme/css_content/) keep their local names (`--sa-teal`, `--rx-ink`, …) but **alias** them to tokens, e.g. `--sa-teal: var(--ls-primary)` |
| Mobile | [`mobile_app/src/constants/theme.ts`](../mobile_app/src/constants/theme.ts) mirrors the JSON as `Colors`, `FontSize`, `Spacing`, `Radius` and the `Type` text presets |

`tests/unit/test_design_tokens.py` fails if `config.toml` or `theme.ts` drift
from `tokens.json`, if a token falls below WCAG AA contrast, or if a page
stylesheet redefines a canonical `--ls-*` token.

**To change a color:** edit `tokens.json`, then copy the value into
`theme.ts`, and into `config.toml` if it is one of the native theme colors.
Run `pytest tests/unit/test_design_tokens.py`.

## Color

Light theme (default). Contrast is measured against white.

| Token | CSS variable | Hex | Use | Contrast |
|---|---|---|---|---|
| primary | `--ls-primary` | `#0F7C88` | Primary buttons, active navigation, links, focus ring | 4.9:1 |
| primaryDark | `--ls-primary-dark` | `#0B626C` | Hover/pressed primary | 7.1:1 |
| primarySoft | `--ls-primary-soft` | `#E8F4F6` | Selected rows, icon chips, active nav background | — |
| navy | `--ls-navy` | `#102D40` | Login hero and dark panels | — |
| ink | `--ls-ink` | `#12283A` | Headings, primary text, values | 15.1:1 |
| textSoft | `--ls-text-soft` | `#4E6272` | Body text, labels | 6.3:1 |
| muted | `--ls-muted` | `#64778A` | Captions, hints, placeholders | 4.6:1 |
| background | `--ls-background` | `#F4F7F8` | App background | — |
| surface | `--ls-surface` | `#FFFFFF` | Cards, panels, inputs, top bar | — |
| surfaceSoft | `--ls-surface-soft` | `#F4F8F9` | Hover, secondary panels | — |
| border | `--ls-border` | `#DDE8EB` | Card and input borders | — |
| borderStrong | `--ls-border-strong` | `#BCD3D8` | Hover borders, dashed empty states | — |

Status colors carry meaning. Never use them for decoration or for chart
series.

| Meaning | Token (fg / soft bg) | Hex | Examples |
|---|---|---|---|
| Success | `success` / `successSoft` | `#23745A` / `#EAF6F1` | Completed, active, saved |
| Warning | `warning` / `warningSoft` | `#B45309` / `#FEF3C7` | Pending, grace period, partial data |
| Danger | `danger` / `dangerSoft` | `#B91C1C` / `#FEE2E2` | Errors, missed, destructive actions, "Pneumonia suspected" |
| Info | `info` / `infoSoft` | `#2A5FA8` / `#E8F1FB` | Neutral notices, "ready for review" |

Dark-theme values are defined in `tokens.json` and pass AA too. The web
applies them when a user picks dark mode; the mobile app currently ships light
only.

**Charts** use a validated categorical pair, never status colors: AI negative
`#2A5FA8`, AI positive `#C2410C`. This pair passes colour-vision-deficiency
separation. Every chart has a legend and a "View as table" fallback.

## Typography

One family everywhere: **Manrope** (400/500/600/700/800). The Fraunces serif
and Barlow Condensed fonts were removed.

| Role | Size / weight | Web | Mobile `Type.*` |
|---|---|---|---|
| Page title | 30 / 600–800 | `.sa-page-title`, `h1` | `display` (24) |
| Section title | 20 / 700 | `.sa-section-title` | `title` |
| Card heading | 16 / 700 | — | `heading` |
| Body | 14–16 / 400 | Streamlit base (15 px) | `body` |
| Label | 12 / 600 | `.sa-th`, field labels | `label` |
| Caption / hint | 12 / 400 | `.sa-metric-hint`, `st.caption` | `caption` |
| Metric value | 26–28 / 700–800 | `.sa-metric-value` | `metric` |

Mobile page titles are smaller (24) to suit narrow screens.

## Spacing, radius, elevation

- **Spacing:** 4, 8, 12, 16, 24, 32, 48, 64 (`--ls-space-1…8`, `Spacing[1…8]`).
  Screen padding: 16 on mobile, 24 on web. Gap between cards: 12–16.
- **Radius:** 8 (inputs, buttons, small chips), 12 (metric cards, notes),
  16 (cards, panels), 999 (pills).
- **Elevation:** flat. Use a 1-px border plus `--ls-shadow-sm`. No gradients.
  The only exceptions are the login hero image and the X-ray placeholder
  texture.

## Components

| Pattern | Web (`streamlit_app/components/ui.py`) | Mobile (`src/components/ui.tsx`) |
|---|---|---|
| Page header | `page_header(title, caption, action…)` | `PageHeader` |
| Section title | `section_title()` | `SectionTitle` |
| Metric card | `metric_card(title, value, icon, tone, hint)` | `StatCard` |
| Status label | `pill(text, tone)` | `Pill` |
| Message box | `note(text, tone)` | `Note` |
| Empty state | `empty_state(text)` | `EmptyState` / `StateView kind="empty"` |
| Loading / error | `st.spinner`, `note(..., "red")` | `StateView kind="loading" / "error"` |
| Detail rows | `show_rows([(label, value)])` | `DetailRow` |
| Button | `st.button(type="primary")` (themed) | `Button variant="primary" / "secondary" / "danger"` |
| Input | `st.text_input` (themed) | `TextField` |
| Role dashboard | `components/role_dashboard.py` | `components/Dashboard.tsx` |

Rules:

- **One primary action per view.** Secondary actions use the secondary
  (outlined) style; destructive actions use danger.
- **Touch targets** on mobile are at least 48 px (`TouchTarget`).
- **Icons:** Material Symbols Rounded on web (Streamlit's bundled font), and
  Ionicons *outline* on mobile. Use the same concept on both, e.g. web
  `event_available` = mobile `calendar-outline`.
- **Numbers that failed to load show "—" and a warning note, never 0.**
- Status always pairs color with text (and an icon where space allows), never
  color alone.

## Navigation

- **Web:** a left sidebar with the brand, a user card, grouped sections and
  account actions. The top bar shows the current page name and description on
  the left, and the user, role and hospital on the right. The brand appears
  only in the sidebar.
- **Mobile:** bottom tabs (Dashboard, Map, Profile), with the brand bar at the
  top of the dashboard and notifications as a pushed screen.
- **Role names** are the database role names everywhere: Radiologist,
  Radiologic Technologist, Staff, Hospital Admin, and System Administrator
  (for `Superadmin`).

## Clinical wording

All AI wording comes from [`shared/ai_labels.py`](../shared/ai_labels.py)
(web) and [`mobile_app/src/constants/ai.ts`](../mobile_app/src/constants/ai.ts)
(mobile):

- **Results:** "Pneumonia suspected" / "No pneumonia detected". Types:
  "Bacterial pattern" / "Viral pattern".
- **Confidence:** "Model confidence". It is never presented as the probability
  of disease.
- **Disclaimer:** "AI decision support only — not a diagnosis. A qualified
  clinician must review the image and confirm the result."
- **Never:** risk levels, severity, anatomical findings, or "diagnosed by AI".
  `tests/unit/test_ai_labels.py` enforces this.
