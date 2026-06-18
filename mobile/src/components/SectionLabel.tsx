import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

interface SectionLabelProps {
  title: string;
  subtitle?: string;
  variant?: 'page' | 'section';
}

export function SectionLabel({ title, subtitle, variant = 'section' }: SectionLabelProps) {
  if (variant === 'page') {
    return (
      <View style={styles.pageContainer}>
        <View style={styles.accent} />
        <View style={styles.pageText}>
          <Text style={styles.pageTitle}>{title}</Text>
          {subtitle && <Text style={styles.pageSubtitle}>{subtitle}</Text>}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.sectionContainer}>
      <Text style={styles.sectionTitle}>{title}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pageContainer: {
    flexDirection: 'row',
    alignItems: 'stretch',
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  accent: {
    width: 3,
    backgroundColor: colors.fleetRed,
  },
  pageText: {
    flex: 1,
    gap: spacing.xs,
    justifyContent: 'center',
  },
  pageTitle: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 16,
    lineHeight: 20,
  },
  pageSubtitle: {
    ...typography.caption,
    color: colors.muted,
  },
  sectionContainer: {
    marginBottom: spacing.sm,
    marginTop: spacing.lg,
  },
  sectionTitle: {
    ...typography.overline,
    color: colors.faded,
    fontSize: 11,
  },
});
