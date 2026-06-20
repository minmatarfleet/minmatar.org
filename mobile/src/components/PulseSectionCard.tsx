import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { ScreenHeader } from '@/src/components/ScreenHeader';
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
      <ScreenHeader
        title={title}
        subtitle={subtitle}
        badge={badge}
        badgeLive={badgeLive}
        style={styles.header}
      />
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
    paddingHorizontal: 0,
    paddingTop: 0,
    marginBottom: spacing.md,
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
