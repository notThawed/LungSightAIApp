# LungSightAI Mobile

The mobile companion to the LungSightAI web workspace, for **Radiologists,
Radiologic Technologists and Staff**. Hospital Admin and Superadmin accounts
are rejected at sign-in, because administration happens on the web app.

Built with Expo SDK 57, React Native 0.86, Expo Router and TypeScript. It
shares the design tokens in [`../shared/theme/tokens.json`](../shared/theme/tokens.json)
with the web app; see [`../docs/DESIGN_SYSTEM.md`](../docs/DESIGN_SYSTEM.md).

## Screens

| Route | Screen | Data |
|---|---|---|
| `/login` | Email + password sign-in | `supabase.auth.signInWithPassword` |
| `/` | Session and role gate; routes by role | `user_profiles`, `roles` |
| `/physician`, `/rad_tech`, `/staff` | Role dashboard with live counts (same metrics as the web dashboards) | `examinations`, `follow_ups` (count-only queries) |
| `…/geospatial` | Map of active partner hospitals (list-only on web) | `hospitals` |
| `…/profile` | View and edit personal information, sign out | `user_profiles` |
| `…/notifications` | Placeholder (not implemented yet) | — |

## Setup

```bash
cp .env.example .env     # EXPO_PUBLIC_SUPABASE_URL + EXPO_PUBLIC_SUPABASE_KEY (anon key only)
npm install
npx expo start           # a = Android, i = iOS, or scan the QR code with Expo Go
```

`EXPO_PUBLIC_*` variables are embedded in the app bundle. **Never use the
service-role key here.** All data access goes through Supabase Row Level
Security with the signed-in user's session.

## Checks

```bash
npm run lint                        # ESLint (must report 0 problems)
npx tsc --noEmit                    # type-check (must report 0 errors)
npx expo export --platform android  # bundle the native app without a device
npm run web                         # browser preview
```

Add dependencies with `npx expo install <package>`, so the versions match the
SDK.

## Code layout

```
src/app/                 Expo Router routes (thin wrappers)
src/components/ui.tsx    Shared UI kit: Screen, BrandBar, Card, Button, TextField, Pill,
                         StatCard, Note, DetailRow, StateView, EmptyState
src/components/          Dashboard, Profile, Geospatial (+ .web.tsx fallback), Notifications
src/constants/theme.ts   Design tokens (mirror of shared/theme/tokens.json)
src/constants/ai.ts      AI disclaimer wording (mirror of shared/ai_labels.py)
src/lib/                 supabase client, user profile, dashboard metrics, hospitals
```
