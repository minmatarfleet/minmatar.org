import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { SeeAllLink } from '@/src/components/SeeAllLink';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

interface PulseSectionCardProps {
  title: string;
  subtitle?: string;
  badge?: string;
  badgeLive?: boolean;
  children: ReactNode;
  footer?: { label: string; onPress: () => void };
}

export function PulseSectionCard({
  title,
  subtitle,
  badge,
  badgeLive = false,
  children,
  footer,
}: PulseSectionCardProps) {
  return (
    <View style={styles.wrap}>
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.title}>{title}</Text>
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        </View>
        {badge ? (
          <View style={[styles.badge, badgeLive && styles.badgeLive]}>
            {badgeLive ? <View style={styles.badgeDot} /> : null}
            <Text style={styles.badgeText}>{badge}</Text>
          </View>
        ) : null}
      </View>
      <View style={styles.body}>{children}</View>
      {footer ? <SeeAllLink label={footer.label} onPress={footer.onPress} /> : null}
    </View>
  );
}

interface PulseSubsectionProps {
  label: string;
  children: ReactNode;
}

export function PulseSubsection({ label, children }: PulseSubsectionProps) {
  return (
    <View style={styles.subsection}>
      <Text style={styles.subsectionLabel}>{label}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: spacing.xl,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  headerText: {
    flex: 1,
    gap: 2,
  },
  title: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 16,
    lineHeight: 20,
  },
  subtitle: {
    ...typography.caption,
    color: colors.muted,
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  badgeLive: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    borderColor: colors.fleetRed,
    backgroundColor: colors.fleetRedMuted,
  },
  badgeDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.green,
  },
  badgeText: {
    ...typography.overline,
    fontSize: 9,
    color: colors.faded,
  },
  body: {
    gap: 0,
  },
  subsection: {
    marginBottom: spacing.sm,
  },
  subsectionLabel: {
    ...typography.overline,
    color: colors.faded,
    fontSize: 10,
    marginBottom: spacing.sm,
  },
});
