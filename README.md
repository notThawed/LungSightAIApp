# LungSight AI &bull; Clinical Chest X-Ray Intelligence Platform

> **AI-Assisted Pulmonary Triage, Hospital Management & Radiology Decision-Support Platform**  
> Powered by ResNet-50 Deep Learning Inference, Streamlit, and Supabase PostgreSQL.

---

## 📋 Comprehensive Changelog & System Overview

This release delivers an enterprise-grade redesign and architectural overhaul of the **System Administrator Suite**, **Monitoring & Compliance Engine**, **Hospital Management**, and **Profile & Security Settings**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             LUNGSIGHT AI PLATFORM                           │
├─────────────────────┬───────────────────────────┬───────────────────────────┤
│ System Admin Suite  │  Monitoring & Compliance  │  Clinical Operations      │
│ • Manage Hospitals  │  • View Reports           │  • Patient Management     │
│ • Manage Users      │  • Audit Logs             │  • Examination Review     │
│ • Manage Subscriptions│• Email Notifications    │  • Medical Records        │
│ • Client Applications│• Data Training Review    │  • Physician Diagnostics  │
└─────────────────────┴───────────────────────────┴───────────────────────────┘
```

---

### 1. New Additions & Major Enhancements

#### A. Administrative KPI & Metric Card System
- **Rich Tinted Gradient Theming**: Completely overhauled `.sa-metric` in `base.css` to feature vibrant, high-contrast clinical gradients instead of plain white backgrounds:
  - **Teal / Cyan (`.sa-metric-teal`)**: Overview, totals, and facility metrics (`#F0FDFA` &rarr; `#E6F7F8` with `#0F7C88` border & solid badge).
  - **Green / Emerald (`.sa-metric-green`)**: Active records, confirmed deliveries, approved accounts (`#F0FDF4` &rarr; `#DCFCE7` with `#16A34A` border).
  - **Blue / Royal (`.sa-metric-blue`)**: Subscribed facilities, operational workflows, calendar periods (`#EFF6FF` &rarr; `#DBEAFE` with `#2563EB` border).
  - **Amber / Gold (`.sa-metric-amber`)**: Pending reviews, warnings, flagged AI abnormalities (`#FFFDF5` &rarr; `#FEF3C7` with `#D97706` border).
  - **Red / Rose (`.sa-metric-red`)**: Critical alerts, failed deliveries, rejected accounts (`#FEF2F2` &rarr; `#FEE2E2` with `#DC2626` border).
- **Solid Elevation Badges**: Icon badges styled with 48x48px dimensions, 13px border radius, white SVG symbols, and soft colored drop shadows.

---

#### B. Subscription Management (`manage_subscriptions.py` & `manage_subscriptions.css`)
- **Top Overview KPI Cards**: 4 real-time metric cards for *Total Plans*, *Active Plans*, *Active Hospitals* (queried from `hospital_subscriptions`), and *Archived Plans*.
- **Interactive Tier Cards**:
  - Distinct colored top-accent stripes: Teal for Starter, Royal Blue for Professional, Gold for Enterprise, Slate for Archived.
  - Dynamic subscriber count badges (e.g. `4 facilities enrolled`).
  - Formatted monthly pricing with calculated annual billing savings (`Save ~17%`).
  - Quotas & limits metric grid with inline SVG icons for *Staff Accounts*, *Patient Records*, and *Monthly AI Scans* (supporting numeric counts and modern `Unlimited` badges).
- **Interactive Search & Sort Toolbar**: Live search bar, sorting dropdown (Price Low-to-High, High-to-Low, Most Subscribed), and active tier count badge.
- **Add Plan Form with Live Card Preview**:
  - Two-column layout: Form configuration on the left; **Live Card Preview** on the right that dynamically updates as the admin types.
  - Automatic annual billing discount calculator with optional custom override.
- **Safe Dialog Modals**:
  - *Edit Plan Dialog*: Structured 2-column input layout with renewal guidelines.
  - *Confirm Plan Dialog*: Quota summary card before publishing to registration workflows.
  - *Delete Plan Dialog*: Integrated safeguard warning if active hospital facilities are currently enrolled on the tier.

---

#### C. View Reports (`hospital_reports.py` & `reports.css`)
- **Report Controls Card**: Clean facility selector and reporting timeframe radios (Weekly, Monthly, Custom range).
- **Executive Report Metadata Banner**: Clinical header displaying facility name, verified report badge, active date range tag, Manila timezone timestamp, and unique report ID chip.
- **KPI Metrics Overhaul**: Upgraded plain `st.metric` elements to vibrant `.sa-metric` cards categorized by clinical status.
- **Trend Charts & Analytics**: Grouped bar charts for registration vs. analysis vs. physician review throughput, along with AI screening outcome distribution charts.
- **Export Actions Panel**: Dedicated card with one-click preparation and download for PDF clinical reports and Excel spreadsheets.

---

#### D. Audit Logs (`audit_logs.py` & `audit_logs.css`)
- **Top KPI Metrics Bar**: Real-time overview of *Total Events Logged*, *Audited Scope*, *Timeframe*, and *Events on Current Page*.
- **Multi-Criteria Filter Panel**: Filtering by Date Range, Event Category, Outcome, Healthcare Facility, Actor, and Free-text query, complete with a 1-click **Reset Filters** button.
- **Results Toolbar & Pagination**: Dynamic count badge (`Showing X of Y events`) with responsive pagination controls.
- **Selected Event Inspector Card**: Detailed metadata drawer displaying event type, colored outcome pills (`SUCCESS` in green, `FAILED` in red, `WARNING` in amber), actor avatar chip, timestamp, target entity, and formatted JSON payload viewer.
- **Compliance CSV Export**: Timestamped export dataset generator with record count verification.

---

#### E. Email Notifications (`notification_history.py` & `notification_history.css`)
- **Top KPI Metrics Bar**: Overview metrics for *Total Emails Logged*, *Recipient Scope*, *Filter Period*, and *Records on Page*.
- **Notification Filters Card**: Status filter, transactional email event type, date range, and facility selector with quick-reset action.
- **Interactive Status Guide**: Visual status legend strip with color-coded badges:
  - `Delivered` (Green): Verified by provider webhook event.
  - `Sent` (Teal): Dispatched to email service provider.
  - `Failed` (Red): Delivery attempt failed (retryable).
  - `Skipped` (Amber): Recipient account no longer eligible.
  - `Suppressed` (Grey): Address previously bounced or complained.
- **Email Delivery Inspector & Diagnostics**: When an email is selected, shows delivery attempts (`1/3`), timestamps, failure diagnostics alert box, and a prominent **"Retry Email Delivery Now"** button for failed messages.

---

#### F. Profile & Account Management (`profile.py` & `profile.css`)
- **Identity Card Modernization**:
  - Fixed CSS class mismatch for `.ls-profile-avatar` so initials and profile pictures render with circular borders, white outlines, and soft elevation.
  - Added official role badge (`System Administrator`, `Hospital Admin`, etc.), online account status pill, facility affiliation chip, and last login timestamp.
- **CommonMark Code-Block Bug Fix**: Removed all indented multiline HTML strings across `profile.py` that previously triggered Streamlit's `<pre><code>` markdown code block formatting.
- **Themed Section Cards with Accent Stripes**:
  - Profile Picture (`#0F7C88` Teal)
  - Personal Information (`#2563EB` Blue)
  - Account Information (`#16A34A` Green)
  - Hospital Affiliation (`#D97706` Amber)
  - Preferences (`#8B5CF6` Purple)
  - Security & Password (`#DC2626` Red)

---

#### G. Additional Portals & Pages
- **Manage Applications (`manage_applications.py`)**: KPI metric cards, application review drawer, dynamic status filtering, and facility approval modal.
- **Manage Hospitals (`manage_hospital.py`)**: Interactive hospital map, usage progress tracks, staff profile modals, and subscription status badges.
- **Manage Users (`manage_user.py`)**: Role badges, active/inactive toggles, avatar initials, and search/filter toolbars.
- **Manage Patients (`manage_patients.py`)**: Patient demographic records, pagination, and clinical status badges.
- **Manage Examinations (`manage_examinations.py`)**: DICOM image review, AI confidence scores, and radiologist sign-off workflows.
- **Manage Medical Records (`manage_medical_records.py`)**: Medical record timelines, diagnosis history, and clinical attachments.

---

### 2. Directory Structure of Changed Modules

```
LungSightAIApp/
├── shared/
│   └── theme/
│       └── css_content/
│           ├── profile.css
│           └── system_admin_css/
│               ├── base.css                    # Global metric cards & base tokens
│               ├── reports.css                 # Reports generator & metadata styles
│               ├── audit_logs.css              # Audit event inspector & filter toolbar
│               ├── notification_history.css    # Email notification status & diagnostics
│               ├── manage_subscriptions.css    # Plan cards, quotas & preview panel
│               ├── manage_application.css      # Application review cards
│               ├── manage_hospital.css         # Hospital map & detail views
│               ├── manage_users.css            # User management table & cards
│               ├── manage_patients.css         # Patient records styling
│               ├── manage_examinations.css     # Examination inspection styles
│               └── manage_medical_records.css  # Medical records history styles
└── streamlit_app/
    ├── app.py
    ├── components/
    │   ├── ui.py
    │   └── dialogs/
    │       └── manage_hospital_dialogs.py
    └── pages/
        ├── audit_logs.py                       # Audit logs interface
        ├── hospital_reports.py                 # Clinical reports generator
        ├── notification_history.py             # Email notification queue
        ├── profile.py                          # Profile & security settings
        └── system_administrator/
            ├── dashboard.py
            ├── manage_applications.py
            ├── manage_examinations.py
            ├── manage_hospital.py
            ├── manage_medical_records.py
            ├── manage_patients.py
            ├── manage_subscriptions.py
            ├── manage_user.py
            └── reports.py
```

---

## 🚀 How to Commit and Push Your Code

Follow these terminal steps to stage your changes, commit them with a clean message, and push to GitHub.

### Step 1: Open Terminal in the Project Directory
Ensure you are in `c:\Users\espej\Lungs`:
```powershell
cd c:\Users\espej\Lungs
```

### Step 2: Stage All Modified and New Files
```powershell
git add .
```

### Step 3: Verify Staged Files
```powershell
git status
```
*You should see all modified `.py` and `.css` files, new `.css` files, and `.gitignore` staged in green.*

### Step 4: Commit Your Changes
```powershell
git commit -m "feat(system-admin): overhaul metric cards, reports, audit logs, notifications, and subscriptions UI"
```

### Step 5: Push to GitHub

#### Option A: Push directly to `feat/mobile-app-updates`
If you want these updates placed directly onto the `feat/mobile-app-updates` branch:
```powershell
git push origin LungSightDeployment:feat/mobile-app-updates
```
*(Or switch to the branch first: `git checkout feat/mobile-app-updates`, then `git merge LungSightDeployment`, and `git push origin feat/mobile-app-updates`)*

#### Option B: Push to `LungSightDeployment`
If you want to keep the current branch up to date on GitHub:
```powershell
git push origin LungSightDeployment
```

---

## 💻 Local Development Setup

### 1. Prerequisites
- **Python 3.10+**
- **Git**

### 2. Environment Activation & Dependencies
```powershell
# Activate virtual environment
.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Launching the Platform
```powershell
streamlit run streamlit_app/app.py
```
Open your browser at `http://localhost:8501`.

---

## 🔒 Clinical Regulatory Notice
LungSight is an artificial intelligence-assisted clinical decision-support system intended for use by licensed physicians, radiologists, and healthcare professionals. The system provides automated presumptive findings to assist in triage and diagnostic prioritization. It does not replace independent clinical judgment, laboratory testing, or formal medical diagnosis.
