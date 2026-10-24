# LungSight AI &bull; Clinical Chest X-Ray Intelligence Platform

> **AI-Assisted Pulmonary Triage & Hospital Radiology Decision-Support System**  
> Powered by ResNet-50 Deep Learning Inference, Streamlit, and Supabase.

---

## 📋 Changelog: What was Modified and Added (`feat/mobile-app-updates`)

This branch introduces an institutional redesign, including a dedicated public landing page, transferred subscription models, updated authentication flows, modernized administrative interfaces, and responsive card layouts.

### 1. New Features & Components Added

| Component / File | Description |
| :--- | :--- |
| **`streamlit_app/screens/homepage.py`** | **New Widescreen Landing Page**: Comprehensive public-facing portal featuring: <br>&bull; **Floating Header / Navbar**: Brand badges, responsive anchor links, and portal login quick-action.<br>&bull; **Clinical Hero Section**: Dual CTAs, clinical diagnostic metric badges (Sensitivity, Latency, RLS Isolation), and interactive CXR workstation preview.<br>&bull; **Clinical Pillars Grid**: 4 feature cards detailing automated triage, deep learning inference, physician validation, and longitudinal care tracking.<br>&bull; **Workflow Pipeline**: 3-step visual narrative (*DICOM Ingestion &rarr; DL Inference &rarr; Radiologist Review*).<br>&bull; **Hospital Subscription Plans**: Integrated pricing tiers with feature comparisons and direct hospital application modals.<br>&bull; **About Us & Institutional Governance**: Mission narrative, ethical AI copilot framing, and 256-bit SSL encryption trust badges.<br>&bull; **Smooth Anchor Navigation**: Client-side polling and event delegation for deep-link scrolling (`#features`, `#workflow`, `#plans`, `#about`, `#trust`). |
| **`shared/theme/css_content/homepage.css`** | **Design System & Stylesheet**: Dedicated 1,390-line stylesheet utilizing CSS design tokens (`--brand-teal`, `--navy-ink`, `--slate-deep`), glassmorphism effects, CSS Grid layouts, and strict vertical & horizontal centering (`justify-content: center`, `text-align: center`) across all card modules. |
| **`shared/images/hero_xray_preview.jpg`** | **High-Definition Radiography Workstation Asset**: Visual preview for the hero showcase card displaying simulated ResNet-50 heatmap localization. |
| **`modern_tabs` (`streamlit_app/components/ui.py`)** | **Modern Segmented Navigation**: Integrated `streamlit-antd-components` (`sac.tabs`) component replacing legacy Streamlit tab bars with pill-styled clinical navigation. |

---

### 2. Modified Modules & Enhancements

#### A. Public Routing & Authentication Flow
- **`streamlit_app/app.py`**:
  - Implemented state-based view switching between public landing (`homepage`) and staff authentication (`login`).
  - Added session cleanup hooks and smooth page transition handlers.
- **`streamlit_app/auth/login.py` & `shared/theme/css_content/login.css`**:
  - Cleaned up the login interface: transferred promotional subscription tiers and about cards to the new landing page, focusing the screen purely on secure clinical authentication.
  - Refined input styling, password reveal toggles, and hospital branding.

#### B. Administrative Portals & Modernized Tabs
- **`streamlit_app/pages/system_administrator/manage_subscriptions.py`**:
  - Switched from default `st.tabs` to `modern_tabs` with icons for *"Plans"*, *"Add plan"*, and *"Inactive plans"*.
- **`streamlit_app/pages/system_administrator/manage_user.py`**:
  - Upgraded user detail views with modern icon tabs for *"Account"*, *"Personal"*, and *"Activity"*.
- **`streamlit_app/pages/system_administrator/manage_patients.py`**:
  - Upgraded patient record inspection tabs for *"General"*, *"Medical"*, and *"Hospital"*.
- **`streamlit_app/pages/system_administrator/manage_applications.py`**:
  - Polished review workflows for incoming hospital subscription applications.
- **`shared/theme/css_content/hospital_admin_css/`**:
  - Modernized `hospital_info.css`, `subscription_settings.css`, and `subscription_usage.css` with cohesive palette variables, subtle card glows, and tabular data displays.

#### C. Clinical Workflows & Physician Tools
- **`streamlit_app/pages/physician/review_patient.py`**:
  - Fixed layout alignment, DICOM viewer contrast panels, and sign-off report buttons.
- **`streamlit_app/pages/staff/followups.py`**:
  - Polished follow-up appointment tracking tables and patient status pills.

#### D. Configuration & Environment
- **`requirements.txt`**:
  - Added `streamlit-antd-components` and `streamlit-shadcn-ui`.
- **`test_model.py`**:
  - Updated hardcoded user paths to dynamically resolved `pathlib.Path` relative paths.
- **`.gitignore`**:
  - Added project agent rules and local cache ignores.

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python**: Version `3.10` or `3.11` recommended.
- **Git** installed on your workstation.

### 2. Installation
Clone the repository and check out the branch:
```bash
git clone https://github.com/notThawed/LungSightAIApp.git
cd LungSightAIApp
git checkout feat/mobile-app-updates
```

Create and activate a virtual environment:
```powershell
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Running the Application
Launch the Streamlit clinical platform:
```bash
streamlit run streamlit_app/app.py
```
Open your browser at `http://localhost:8501`.

---

## 🔒 Clinical Regulatory Notice
LungSight is an artificial intelligence-assisted clinical decision-support system intended for use by licensed physicians, radiologists, and healthcare professionals. The system provides automated presumptive findings to assist in triage and diagnostic prioritization. It does not replace independent clinical judgment, laboratory testing, or formal medical diagnosis.
