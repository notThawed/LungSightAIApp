# LungSightAI

AI-assisted pneumonia screening on chest X-rays, for hospitals and clinics.

LungSightAI is a B2B product made of two applications that share one Supabase
backend and one design system:

| App | For | Location |
|---|---|---|
| **Web workspace** (Streamlit) | All hospital roles and LungSightAI system administrators: patient registration, examinations, X-ray upload and AI analysis, physician review, follow-ups, hospital and subscription administration, training-data review | [`streamlit_app/`](streamlit_app/) |
| **Mobile companion** (Expo / React Native) | Radiologists, radiologic technologists and staff on the go: live workload dashboard, hospital map, profile | [`mobile_app/`](mobile_app/) |

Administration (Hospital Admin, Superadmin) is web-only by design. The mobile
app rejects those roles at sign-in.

> **Clinical use.** AI output is decision support, not a diagnosis. Every AI
> result must be reviewed and confirmed by a qualified clinician. See
> [AI inference](#ai-inference-what-the-models-actually-do).

---

## Contents

- [Technology stack](#technology-stack)
- [Repository layout](#repository-layout)
- [Environment setup](#environment-setup)
- [Run the web app](#run-the-web-app)
- [Run the mobile app](#run-the-mobile-app)
- [Tests](#tests)
- [Design system](#design-system)
- [AI inference: what the models actually do](#ai-inference-what-the-models-actually-do)
- [Security notes](#security-notes)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)

---

## Technology stack

| Layer | Technology |
|---|---|
| Web UI | Streamlit 1.65+ (Python 3.13), custom CSS on shared design tokens, Altair charts, Folium maps |
| Mobile UI | Expo SDK 57, React Native 0.86, Expo Router (file-based routes), TypeScript 6, Manrope via `@expo-google-fonts/manrope`, `react-native-maps` |
| Backend | Supabase (Postgres, Auth, Storage, Row Level Security), Python service layer in [`backend/`](backend/) |
| AI | PyTorch + torchvision: ResNet-50 binary classifier, DenseNet-121 type classifier, Grad-CAM; CLIP (Hugging Face `transformers`) as a chest-X-ray input check |
| Payments | PayMongo checkout, plus a Supabase Edge Function webhook ([`supabase/functions/paymongo-webhook`](supabase/functions/paymongo-webhook/)) |

## Repository layout

```
backend/                 Supabase clients, queries (fetches.py, crud.py), domain utils
  ai/                    pneumonia_model.py, pneumonia_type_model.py, ood_validator.py
  backend_utils/         hospitals, follow-ups, subscriptions, dashboard metrics, ...
models/                  resnet_model.pt, densenet_121_classification.pt, class_names.json
shared/
  theme/tokens.json      ← design tokens: the single source of truth for both apps
  theme/streamlit_theme.py   turns tokens into CSS variables (--ls-*)
  theme/css_content/     page stylesheets (alias their variables to the tokens)
  ai_labels.py           the only wording used to describe AI output
streamlit_app/           web app: app.py (entry), layouts/ (one per role), pages/, components/
mobile_app/              Expo app: src/app (routes), src/components (screens + ui.tsx kit)
scripts/                 retraining export, model comparison, data backfills
supabase/                Supabase CLI config and Edge Functions
tests/                   pytest suite (unit, regression, app render, AI inference)
docs/                    design system and other documentation
```

## Environment setup

### Prerequisites

- Python **3.13**
- Node.js **20+** (tested with 24) and npm
- A Supabase project with the LungSightAI schema. The schema and RLS policies
  are **not** in this repository; export them from the existing project
  (`supabase db dump`) before setting up a new one.
- Expo Go or an Android or iOS emulator, for the mobile app

### Web app configuration

```bash
cp .env.example .env        # then fill in real values
```

| Variable | Required | Purpose |
|---|---|---|
| `SUPABASE_URL` | yes | Project URL |
| `SUPABASE_KEY` | yes | Publishable / anon key |
| `SUPABASE_SECRET_KEY` | yes | Service-role / secret key. **Server-side only.** |
| `INVITE_REDIRECT_URL` | no | Where invite e-mails redirect (default: the GitHub Pages redirect) |
| `APP_BASE_URL` | no | Public app URL, used for PayMongo return URLs (default `http://localhost:8501`) |
| `PAYMONGO_SECRET_KEY` | for payments | PayMongo API key |
| `CARTO_API_KEY` | no | CARTO basemap for the geospatial map |

On Streamlit Community Cloud, put the same keys in **App settings → Secrets**
instead of a `.env` file. If a required value is missing, the app shows a
"LungSightAI is not configured" screen instead of a traceback.

### Mobile app configuration

```bash
cp mobile_app/.env.example mobile_app/.env
```

| Variable | Purpose |
|---|---|
| `EXPO_PUBLIC_SUPABASE_URL` | Project URL |
| `EXPO_PUBLIC_SUPABASE_KEY` | **Anon / publishable key only.** `EXPO_PUBLIC_*` values are bundled into the app. |

## Run the web app

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate

# CPU-only PyTorch (smaller download). Skip this line if you have CUDA.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

streamlit run streamlit_app/app.py
```

Open http://localhost:8501. Run the command from the project root so
`.streamlit/config.toml` (theme, static serving, hidden page list) is picked up.

The first start downloads the CLIP model (`openai/clip-vit-base-patch32`,
about 600 MB) used for the chest-X-ray input check. Without internet access the
check is skipped and the Analyze screen says so.

## Run the mobile app

```bash
cd mobile_app
npm install
npx expo start          # press a (Android), i (iOS) or scan the QR code with Expo Go
```

Useful commands:

```bash
npm run lint                        # ESLint (eslint-config-expo)
npx tsc --noEmit                    # type-check
npx expo export --platform android  # verify the native bundle compiles
npm run web                         # browser preview (the map screen shows a list on web)
```

Use `npx expo install <package>` (not `npm install <package>`) to add
dependencies, so versions match Expo SDK 57.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The suite never touches a real database: [`tests/conftest.py`](tests/conftest.py)
sets placeholder Supabase credentials before anything is imported, and puts
Hugging Face into offline mode.

| Folder | What it covers |
|---|---|
| `tests/unit` | Design tokens are identical in `tokens.json`, `config.toml` and the mobile `theme.ts`, and meet WCAG AA contrast. AI wording never overclaims. Dashboard metric queries, failure handling, and web/mobile parity. |
| `tests/regression` | No merge-conflict markers, every Python file parses, env files are ignored, the mobile app never references the service key, every sidebar page has a route |
| `tests/app` | Renders the login screen and every role's dashboard with Streamlit's `AppTest`, using a patched data layer. Missing configuration shows the setup screen. |
| `tests/ai` | Runs the real model files on CPU: output contract, determinism, Grad-CAM, type classifier, OOD fallback |
| `tests/security` | **Opt-in, live, read-only**: anonymous users cannot read clinical tables, and clinical storage buckets are private. Run with `RUN_LIVE_SECURITY_TESTS=1`. |
| `tests/test_api.py` | FastAPI health stub |

Mobile: `npm run lint` (ESLint with `eslint-config-expo`) and `npx tsc --noEmit`. There are no JavaScript unit tests yet.

## Design system

Both apps use the tokens in [`shared/theme/tokens.json`](shared/theme/tokens.json):
a teal primary (`#0F7C88`) on cool neutral surfaces, Manrope type, a 4-px
spacing scale and 8/12/16 radii. See
[docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) for the full palette, components
and rules.

## AI inference: what the models actually do

| Step | Model | Output |
|---|---|---|
| 1. Input check | CLIP zero-shot ([`ood_validator.py`](backend/ai/ood_validator.py)) | Is this a chest X-ray? Rejects photos and screenshots below 0.85 probability. **Fails open:** if CLIP cannot load, images are accepted and the UI reports "Chest X-ray check: Not run". |
| 2. Screening | ResNet-50 ([`pneumonia_model.py`](backend/ai/pneumonia_model.py), `models/resnet_model.pt`) | `positive` / `negative` plus a softmax probability |
| 3. Type | DenseNet-121 ([`pneumonia_type_model.py`](backend/ai/pneumonia_type_model.py)) | `bacterial_pneumonia` / `viral_pneumonia` plus a probability, run for positive images |
| 4. Explanation | Grad-CAM on the ResNet | A heatmap of regions that influenced the prediction. It is not a lesion map. |

How results are shown (see [`shared/ai_labels.py`](shared/ai_labels.py)):

- The labels are "Pneumonia suspected" and "No pneumonia detected". They are
  never presented as risk levels.
- The text describes only what the model output. It never claims anatomical
  findings such as "bilateral consolidation".
- The number shown is **model confidence**: the probability the model gave its
  own prediction, not the probability that the patient has pneumonia.
- The physician's diagnosis and confirmed label are recorded separately from
  the AI result. Confirmed, consented cases can feed retraining; see
  [RETRAIN_GUIDE.md](RETRAIN_GUIDE.md).

The models run on the Streamlit server (CPU or CUDA). The mobile app does not
run inference.

## Security notes

> **Action required (found 2026-10-21):** with only the publishable key and
> no login, anyone could read every row of `patients` and `examinations`, and
> the `consent-signatures` storage bucket was public. The fix is
> [`supabase/migrations/20261021120000_lock_down_patient_data.sql`](supabase/migrations/20261021120000_lock_down_patient_data.sql)
> (run it in the Supabase SQL Editor). Verify it with
> `RUN_LIVE_SECURITY_TESTS=1 pytest tests/security`, a read-only check against
> the project in `.env`.

- `SUPABASE_SECRET_KEY` (service role) is used only by the Python server and
  bypasses Row Level Security. Hospital isolation in the web app is therefore
  enforced in application code (queries filter by `hospital_id`).
- The mobile app uses the anon key with the signed-in user's session, so **RLS
  policies decide what mobile users can read**. Review them before release.
  Dashboard counts on mobile only include rows that RLS allows.
- Never commit `.env`, `mobile_app/.env` or `.streamlit/secrets.toml`; all are
  ignored by git.
- Exported training images (`hybrid_negative_positive/`,
  `international_classification/`) are patient data and are git-ignored. See
  Known limitations for images committed before this rule existed.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "LungSightAI is not configured" / `SUPABASE_URL is missing` | Create `.env` from `.env.example` in the **project root**, or set Streamlit Secrets |
| `ModuleNotFoundError: torch` | Install PyTorch first (see [Run the web app](#run-the-web-app)), then `pip install -r requirements.txt` |
| `ModuleNotFoundError: auth` / `layouts` | Run `streamlit run streamlit_app/app.py` from the project root |
| Very slow first start | The CLIP model is downloading (about 600 MB, once) |
| Mobile: "EXPO_PUBLIC_SUPABASE_URL / … are missing" | Create `mobile_app/.env`, then restart Expo with `npx expo start --clear` |
| Mobile: login works but the dashboard shows "—" | The count queries were denied or failed. Check RLS `SELECT` policies on `examinations`, `follow_ups` and `patients`. |
| Mobile: Hospital Admin / Superadmin cannot sign in | Intended. Administration is web-only. |
| Mobile web preview: `codegenNativeComponent is not a function` | Restart with `npx expo start --web --clear`. The map uses `Geospatial.web.tsx` on web. |

## Known limitations

- **The full database schema is not in the repo.** Only the patient-data
  lock-down migration is. Export the rest with `supabase db dump` so RLS can
  be reviewed in code.
- Examinations whose patient has no `hospital_id` (2 pending on 2026-10-21)
  appear on no hospital's dashboard or queue. Assign those patients to a
  hospital.
- The System Admin **Reports** and **System Settings** pages are not built
  yet. They show an honest "not available yet" state.
- Mobile notifications are not implemented (empty state only).
- Dark mode exists for the token layer on web (`theme_preference`), but many
  page stylesheets still contain hard-coded light tints. The mobile app ships
  light mode only.
- About 35 hard-coded colors remain in page stylesheets, mostly whites and
  the navy plan-card palette. They are intentional, but they do not adapt to
  dark mode.
- The web app imports pages under two module names (`pages.*` and
  `streamlit_app.pages.*`). It works, but modules can load twice.
- `backend/api.py` (FastAPI) and `backend/database.py` (SQLAlchemy) are unused
  stubs.
- Patient X-ray images exported for retraining were committed to git before
  they were ignored. Removing them from history requires a history rewrite,
  which the repository owners must decide on.
- The brand mark is raster-only (500 px), so app icons are slightly soft. A
  vector logo would sharpen them.
