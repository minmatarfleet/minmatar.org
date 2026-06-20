import { StyleSheet, View, type ViewStyle } from 'react-native';
import { Text } from 'react-native-paper';

import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

interface ScreenHeaderProps {
  title: string;
  subtitle?: string;
  badge?: string;
  badgeLive?: boolean;
  style?: ViewStyle;
}

export function ScreenHeader({ title, subtitle, badge, badgeLive = false, style }: ScreenHeaderProps) {
  return (
    <View style={[styles.wrap, style]}>
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
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: spacing.md,
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
});
