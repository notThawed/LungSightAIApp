/**
 * LungSightAI design tokens for the mobile app.
 *
 * Mirrors shared/theme/tokens.json (the single source of truth also used by
 * the Streamlit web app). Keep the values identical —
 * tests/unit/test_design_tokens.py fails if they drift.
 */

import '@/global.css';

import { Platform, type TextStyle } from 'react-native';

export const Colors = {
  light: {
    primary: '#0F7C88',
    primaryDark: '#0B626C',
    primarySoft: '#E8F4F6',
    onPrimary: '#FFFFFF',
    navy: '#102D40',
    background: '#F4F7F8',
    surface: '#FFFFFF',
    surfaceSoft: '#F4F8F9',
    ink: '#12283A',
    textSoft: '#4E6272',
    muted: '#64778A',
    border: '#DDE8EB',
    borderLight: '#E9EFF2',
    borderStrong: '#BCD3D8',
    success: '#23745A',
    successSoft: '#EAF6F1',
    warning: '#B45309',
    warningSoft: '#FEF3C7',
    danger: '#B91C1C',
    dangerSoft: '#FEE2E2',
    info: '#2A5FA8',
    infoSoft: '#E8F1FB',
  },
  dark: {
    primary: '#3FB8C4',
    primaryDark: '#6CCBD4',
    primarySoft: '#153A41',
    onPrimary: '#0F1A22',
    navy: '#0B1E2B',
    background: '#0F1A22',
    surface: '#16232D',
    surfaceSoft: '#1C2C38',
    ink: '#E6EEF2',
    textSoft: '#A9B8C3',
    muted: '#8597A4',
    border: '#2A3B47',
    borderLight: '#22323D',
    borderStrong: '#3A5060',
    success: '#4CC38A',
    successSoft: '#163428',
    warning: '#F0A84A',
    warningSoft: '#3A2A12',
    danger: '#F27A6E',
    dangerSoft: '#3D1C19',
    info: '#7AA7E8',
    infoSoft: '#1A2A42',
  },
} as const;

export type ThemeColor = keyof typeof Colors.light;

/** The app currently ships the light theme (matching the web default). */
export const C = Colors.light;

/** Manrope weights, loaded in src/app/_layout.tsx via @expo-google-fonts/manrope. */
export const FontFamily = {
  regular: 'Manrope_400Regular',
  medium: 'Manrope_500Medium',
  semibold: 'Manrope_600SemiBold',
  bold: 'Manrope_700Bold',
  extrabold: 'Manrope_800ExtraBold',
} as const;

export const FontSize = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 20,
  xl: 24,
  xxl: 30,
} as const;

export const Spacing = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 24,
  6: 32,
  7: 48,
  8: 64,
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  pill: 999,
} as const;

/** Text presets — every screen uses these instead of ad-hoc font styles. */
export const Type = {
  display: { fontFamily: FontFamily.extrabold, fontSize: FontSize.xl, lineHeight: 30, color: C.ink },
  title: { fontFamily: FontFamily.bold, fontSize: FontSize.lg, lineHeight: 26, color: C.ink },
  heading: { fontFamily: FontFamily.bold, fontSize: FontSize.md, lineHeight: 22, color: C.ink },
  body: { fontFamily: FontFamily.regular, fontSize: FontSize.sm, lineHeight: 21, color: C.textSoft },
  bodyStrong: { fontFamily: FontFamily.semibold, fontSize: FontSize.sm, lineHeight: 21, color: C.ink },
  label: { fontFamily: FontFamily.semibold, fontSize: FontSize.xs, lineHeight: 16, color: C.muted },
  caption: { fontFamily: FontFamily.regular, fontSize: FontSize.xs, lineHeight: 17, color: C.muted },
  metric: { fontFamily: FontFamily.extrabold, fontSize: 26, lineHeight: 32, color: C.ink },
  button: { fontFamily: FontFamily.bold, fontSize: 15, lineHeight: 20 },
} satisfies Record<string, TextStyle>;

/** Subtle elevation, matching --ls-shadow-sm on the web. */
export const Shadow = Platform.select({
  ios: { shadowColor: C.ink, shadowOpacity: 0.06, shadowRadius: 4, shadowOffset: { width: 0, height: 1 } },
  default: { elevation: 1 },
});

/** Minimum touch target (Apple HIG / Material). */
export const TouchTarget = 48;

export const BottomTabInset = Platform.select({ ios: 50, android: 80 }) ?? 0;
export const MaxContentWidth = 800;
