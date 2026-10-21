/**
 * LungSightAI mobile UI kit — the React Native counterpart of the web
 * helpers in streamlit_app/components/ui.py. Screens compose these instead
 * of styling raw Views so web and mobile share one visual language.
 */

import type { ComponentProps, ReactNode } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type StyleProp,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Ionicons from '@expo/vector-icons/Ionicons';

import { C, FontFamily, Radius, Shadow, Spacing, TouchTarget, Type } from '../constants/theme';

type IconName = ComponentProps<typeof Ionicons>['name'];
export type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';

const TONES: Record<Tone, { fg: string; bg: string }> = {
  primary: { fg: C.primary, bg: C.primarySoft },
  success: { fg: C.success, bg: C.successSoft },
  warning: { fg: C.warning, bg: C.warningSoft },
  danger: { fg: C.danger, bg: C.dangerSoft },
  info: { fg: C.info, bg: C.infoSoft },
  neutral: { fg: C.textSoft, bg: C.surfaceSoft },
};

// ============================================================
// LAYOUT
// ============================================================

/** Scrollable, safe-area-aware screen with the app background. */
export function Screen({
  children,
  refreshing,
  onRefresh,
  scroll = true,
}: {
  children: ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
  scroll?: boolean;
}) {
  if (!scroll) {
    return (
      <SafeAreaView edges={['top']} style={styles.screen}>
        <View style={styles.screenContent}>{children}</View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView edges={['top']} style={styles.screen}>
      <ScrollView
        contentContainerStyle={styles.screenContent}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
        refreshControl={
          onRefresh ? (
            <RefreshControl
              refreshing={!!refreshing}
              onRefresh={onRefresh}
              colors={[C.primary]}
              tintColor={C.primary}
            />
          ) : undefined
        }
      >
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

/** Product mark + wordmark, used at the top of every signed-in screen. */
export function BrandBar({ right }: { right?: ReactNode }) {
  return (
    <View style={styles.brandBar}>
      <View style={styles.brandRow}>
        <Image
          source={require('../../assets/images/lungsight-mark.png')}
          style={styles.brandMark}
          accessibilityIgnoresInvertColors
        />
        <Text style={styles.brandText}>
          LungSight<Text style={styles.brandAccent}>AI</Text>
        </Text>
      </View>
      {right}
    </View>
  );
}

/** Page title + optional caption, mirrors page_header() on the web. */
export function PageHeader({ title, caption }: { title: string; caption?: string }) {
  return (
    <View style={styles.pageHeader}>
      <Text style={Type.display} accessibilityRole="header">
        {title}
      </Text>
      {caption ? <Text style={[Type.body, styles.pageCaption]}>{caption}</Text> : null}
    </View>
  );
}

export function SectionTitle({ title, caption }: { title: string; caption?: string }) {
  return (
    <View style={styles.sectionTitle}>
      <Text style={Type.title} accessibilityRole="header">
        {title}
      </Text>
      {caption ? <Text style={[Type.caption, styles.sectionCaption]}>{caption}</Text> : null}
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

// ============================================================
// CONTROLS
// ============================================================

export function Button({
  label,
  onPress,
  variant = 'primary',
  icon,
  loading,
  disabled,
  style,
}: {
  label: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  icon?: IconName;
  loading?: boolean;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const palette = {
    primary: { bg: C.primary, fg: C.onPrimary, border: C.primary },
    secondary: { bg: C.surface, fg: C.ink, border: C.border },
    danger: { bg: C.surface, fg: C.danger, border: C.dangerSoft },
  }[variant];

  const inactive = disabled || loading;

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!inactive, busy: !!loading }}
      onPress={onPress}
      disabled={inactive}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: palette.bg, borderColor: palette.border },
        pressed && !inactive && styles.buttonPressed,
        inactive && styles.buttonDisabled,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={palette.fg} />
      ) : (
        <>
          {icon ? <Ionicons name={icon} size={18} color={palette.fg} /> : null}
          <Text style={[Type.button, { color: palette.fg }]}>{label}</Text>
        </>
      )}
    </Pressable>
  );
}

export function IconButton({
  icon,
  label,
  onPress,
}: {
  icon: IconName;
  label: string;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={onPress}
      hitSlop={4}
      style={({ pressed }) => [styles.iconButton, pressed && styles.buttonPressed]}
    >
      <Ionicons name={icon} size={22} color={C.ink} />
    </Pressable>
  );
}

export function TextField({
  label,
  error,
  ...inputProps
}: TextInputProps & { label: string; error?: string }) {
  return (
    <View style={styles.field}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        placeholderTextColor={C.muted}
        accessibilityLabel={label}
        {...inputProps}
        style={[
          styles.input,
          inputProps.multiline && styles.inputMultiline,
          error ? styles.inputError : null,
          inputProps.style,
        ]}
      />
      {error ? <Text style={styles.fieldError}>{error}</Text> : null}
    </View>
  );
}

// ============================================================
// DATA DISPLAY
// ============================================================

export function Pill({ label, tone = 'neutral', icon }: { label: string; tone?: Tone; icon?: IconName }) {
  const { fg, bg } = TONES[tone];

  return (
    <View style={[styles.pill, { backgroundColor: bg }]}>
      {icon ? <Ionicons name={icon} size={14} color={fg} /> : null}
      <Text style={[styles.pillText, { color: fg }]}>{label}</Text>
    </View>
  );
}

/** Mirrors metric_card() on the web: icon, label, value, hint. */
export function StatCard({
  icon,
  label,
  value,
  hint,
  tone = 'primary',
}: {
  icon: IconName;
  label: string;
  value: string;
  hint?: string;
  tone?: Tone;
}) {
  const { fg, bg } = TONES[tone];

  return (
    <View style={styles.statCard} accessible accessibilityLabel={`${label}: ${value}`}>
      <View style={[styles.statIcon, { backgroundColor: bg }]}>
        <Ionicons name={icon} size={20} color={fg} />
      </View>
      <Text style={Type.metric}>{value}</Text>
      <Text style={[Type.bodyStrong, styles.statLabel]} numberOfLines={2}>
        {label}
      </Text>
      {hint ? (
        <Text style={Type.caption} numberOfLines={2}>
          {hint}
        </Text>
      ) : null}
    </View>
  );
}

export function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <View style={styles.detailRow}>
      <Text style={Type.label}>{label}</Text>
      <Text style={[Type.bodyStrong, styles.detailValue]}>{value?.trim() || 'Not provided'}</Text>
    </View>
  );
}

/** Coloured message box, mirrors note() on the web. */
export function Note({ children, tone = 'primary', icon }: { children: ReactNode; tone?: Tone; icon?: IconName }) {
  const { fg, bg } = TONES[tone];

  return (
    <View style={[styles.note, { backgroundColor: bg, borderLeftColor: fg }]}>
      {icon ? <Ionicons name={icon} size={18} color={fg} style={styles.noteIcon} /> : null}
      <Text style={[Type.body, styles.noteText]}>{children}</Text>
    </View>
  );
}

// ============================================================
// STATES
// ============================================================

/** Full-screen loading / empty / error state. */
export function StateView({
  kind,
  title,
  message,
  actionLabel,
  onAction,
  secondaryLabel,
  onSecondary,
}: {
  kind: 'loading' | 'empty' | 'error';
  title: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
}) {
  const icon: IconName = kind === 'error' ? 'alert-circle-outline' : 'file-tray-outline';
  const tone = kind === 'error' ? TONES.danger : TONES.primary;

  return (
    <SafeAreaView style={[styles.screen, styles.stateWrap]}>
      <View style={styles.stateCard} accessibilityLiveRegion="polite">
        {kind === 'loading' ? (
          <ActivityIndicator size="large" color={C.primary} />
        ) : (
          <View style={[styles.stateIcon, { backgroundColor: tone.bg }]}>
            <Ionicons name={icon} size={30} color={tone.fg} />
          </View>
        )}
        <Text style={[Type.title, styles.stateTitle]}>{title}</Text>
        {message ? <Text style={[Type.body, styles.stateMessage]}>{message}</Text> : null}
        {actionLabel && onAction ? (
          <Button label={actionLabel} onPress={onAction} style={styles.stateAction} />
        ) : null}
        {secondaryLabel && onSecondary ? (
          <Button label={secondaryLabel} onPress={onSecondary} variant="secondary" style={styles.stateSecondary} />
        ) : null}
      </View>
    </SafeAreaView>
  );
}

/** Inline empty state inside a screen (no full-screen wrapper). */
export function EmptyState({ title, message, icon = 'file-tray-outline' }: { title: string; message?: string; icon?: IconName }) {
  return (
    <View style={styles.empty}>
      <Ionicons name={icon} size={26} color={C.muted} />
      <Text style={[Type.heading, styles.emptyTitle]}>{title}</Text>
      {message ? <Text style={[Type.body, styles.emptyMessage]}>{message}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: C.background,
  },
  screenContent: {
    padding: Spacing[4],
    paddingBottom: Spacing[6],
    gap: Spacing[4],
  },

  brandBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  brandRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing[2],
  },
  brandMark: {
    width: 32,
    height: 32,
  },
  brandText: {
    fontFamily: FontFamily.extrabold,
    fontSize: 18,
    color: C.ink,
    letterSpacing: -0.2,
  },
  brandAccent: {
    color: C.primary,
  },

  pageHeader: {
    gap: Spacing[1],
  },
  pageCaption: {
    marginTop: 2,
  },
  sectionTitle: {
    marginTop: Spacing[2],
  },
  sectionCaption: {
    marginTop: 2,
  },

  card: {
    backgroundColor: C.surface,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: C.border,
    padding: Spacing[4],
    gap: Spacing[3],
    ...Shadow,
  },

  button: {
    minHeight: TouchTarget,
    borderRadius: Radius.md,
    borderWidth: 1,
    paddingHorizontal: Spacing[4],
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing[2],
  },
  buttonPressed: {
    opacity: 0.85,
  },
  buttonDisabled: {
    opacity: 0.55,
  },
  iconButton: {
    width: 44,
    height: 44,
    borderRadius: Radius.md,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.border,
    alignItems: 'center',
    justifyContent: 'center',
  },

  field: {
    gap: 6,
  },
  fieldLabel: {
    ...Type.label,
    color: C.textSoft,
  },
  input: {
    minHeight: TouchTarget,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: Radius.md,
    backgroundColor: C.surface,
    paddingHorizontal: Spacing[4],
    fontFamily: FontFamily.regular,
    fontSize: 16,
    color: C.ink,
  },
  inputMultiline: {
    minHeight: 96,
    paddingTop: Spacing[3],
    textAlignVertical: 'top',
  },
  inputError: {
    borderColor: C.danger,
  },
  fieldError: {
    ...Type.caption,
    color: C.danger,
  },

  pill: {
    alignSelf: 'flex-start',
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: Spacing[3],
    paddingVertical: 6,
    borderRadius: Radius.pill,
  },
  pillText: {
    fontFamily: FontFamily.semibold,
    fontSize: 12,
  },

  statCard: {
    flexBasis: '47%',
    flexGrow: 1,
    backgroundColor: C.surface,
    borderRadius: Radius.lg,
    borderWidth: 1,
    borderColor: C.border,
    padding: Spacing[4],
    gap: 2,
    ...Shadow,
  },
  statIcon: {
    width: 36,
    height: 36,
    borderRadius: Radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing[2],
  },
  statLabel: {
    marginTop: 2,
  },

  detailRow: {
    gap: 2,
    paddingVertical: Spacing[2],
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: C.border,
  },
  detailValue: {
    fontSize: 15,
  },

  note: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: Spacing[2],
    padding: Spacing[3],
    borderRadius: Radius.md,
    borderLeftWidth: 3,
  },
  noteIcon: {
    marginTop: 1,
  },
  noteText: {
    flex: 1,
    color: C.ink,
  },

  stateWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    padding: Spacing[5],
  },
  stateCard: {
    width: '100%',
    maxWidth: 420,
    alignItems: 'center',
    gap: Spacing[2],
  },
  stateIcon: {
    width: 60,
    height: 60,
    borderRadius: 30,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: Spacing[2],
  },
  stateTitle: {
    textAlign: 'center',
    marginTop: Spacing[2],
  },
  stateMessage: {
    textAlign: 'center',
  },
  stateAction: {
    alignSelf: 'stretch',
    marginTop: Spacing[4],
  },
  stateSecondary: {
    alignSelf: 'stretch',
  },

  empty: {
    alignItems: 'center',
    gap: Spacing[1],
    paddingVertical: Spacing[5],
    paddingHorizontal: Spacing[4],
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: C.borderStrong,
    borderRadius: Radius.lg,
  },
  emptyTitle: {
    marginTop: Spacing[1],
    textAlign: 'center',
  },
  emptyMessage: {
    textAlign: 'center',
  },
});
