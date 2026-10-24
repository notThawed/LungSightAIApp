import '@/global.css';
import { Platform } from 'react-native';

export const Palette = {
  primary: '#1D4ED8',        // Medical blue
  primaryHover: '#1E40AF',
  primaryLight: '#EFF6FF',
  primaryBorder: '#BFDBFE',

  accent: '#0284C7',         // Clinical cyan
  accentLight: '#E0F2FE',

  success: '#059669',        // Normal / negative findings
  successLight: '#ECFDF5',
  successBorder: '#A7F3D0',

  warning: '#D97706',        // Pending / viral / moderate
  warningLight: '#FEF3C7',
  warningBorder: '#FDE68A',

  danger: '#DC2626',         // High priority / bacterial pneumonia
  dangerLight: '#FEF2F2',
  dangerBorder: '#FECACA',

  slate: {
    50: '#F8FAFC',
    100: '#F1F5F9',
    200: '#E2E8F0',
    300: '#CBD5E1',
    400: '#94A3B8',
    500: '#64748B',
    600: '#475569',
    700: '#334155',
    800: '#1E293B',
    900: '#0F172A',
  },
  white: '#FFFFFF',
  black: '#000000',
} as const;

export const Colors = {
  light: {
    text: Palette.slate[900],
    textSecondary: Palette.slate[500],
    textMuted: Palette.slate[400],
    background: Palette.slate[50],
    surface: Palette.white,
    border: Palette.slate[200],
    primary: Palette.primary,
    primaryLight: Palette.primaryLight,
  },
  dark: {
    text: Palette.white,
    textSecondary: Palette.slate[400],
    textMuted: Palette.slate[500],
    background: Palette.slate[900],
    surface: Palette.slate[800],
    border: Palette.slate[700],
    primary: '#3B82F6',
    primaryLight: '#1E3A8A',
  },
} as const;

export const Typography = {
  h1: {
    fontSize: 28,
    fontWeight: '800' as const,
    letterSpacing: -0.5,
    color: Palette.slate[900],
  },
  h2: {
    fontSize: 22,
    fontWeight: '800' as const,
    letterSpacing: -0.3,
    color: Palette.slate[900],
  },
  h3: {
    fontSize: 18,
    fontWeight: '700' as const,
    color: Palette.slate[900],
  },
  bodyLarge: {
    fontSize: 16,
    fontWeight: '500' as const,
    lineHeight: 24,
    color: Palette.slate[700],
  },
  body: {
    fontSize: 14,
    fontWeight: '400' as const,
    lineHeight: 20,
    color: Palette.slate[600],
  },
  bodySmall: {
    fontSize: 12,
    fontWeight: '500' as const,
    lineHeight: 16,
    color: Palette.slate[500],
  },
  label: {
    fontSize: 11,
    fontWeight: '700' as const,
    letterSpacing: 0.5,
    textTransform: 'uppercase' as const,
    color: Palette.slate[400],
  },
};

export const Spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
} as const;

export const Radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  pill: 999,
} as const;

export const Shadows = {
  sm: {
    shadowColor: Palette.slate[900],
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 2,
  },
  md: {
    shadowColor: Palette.slate[900],
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 3,
  },
  lg: {
    shadowColor: Palette.slate[900],
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.08,
    shadowRadius: 16,
    elevation: 6,
  },
};

export const TouchTarget = {
  minHeight: 48,
  hitSlop: { top: 10, bottom: 10, left: 10, right: 10 },
};
