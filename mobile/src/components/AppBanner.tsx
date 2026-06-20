import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AccountAvatarButton } from '@/src/components/AccountSheet';
import { FleetLogoSquare } from '@/src/components/FleetLogoSquare';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

function formatEveTime(date: Date): string {
  const hours = date.getUTCHours().toString().padStart(2, '0');
  const minutes = date.getUTCMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

export function AppBanner() {
  const insets = useSafeAreaInsets();
  const [eveTime, setEveTime] = useState(() => formatEveTime(new Date()));

  useEffect(() => {
    const interval = setInterval(() => setEveTime(formatEveTime(new Date())), 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <View style={[styles.wrap, { paddingTop: insets.top + spacing.sm }]}>
      <View style={styles.row}>
        <FleetLogoSquare size={32} />
        <View style={styles.divider} />
        <View style={styles.timeBlock}>
          <Text style={styles.timeLabel}>EVE</Text>
          <Text style={styles.time}>{eveTime}</Text>
        </View>
        <View style={styles.spacer} />
        <AccountAvatarButton size={32} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
    backgroundColor: colors.background,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    minHeight: 36,
  },
  divider: {
    width: StyleSheet.hairlineWidth,
    height: 24,
    backgroundColor: colors.borderHover,
  },
  timeBlock: {
    gap: 1,
  },
  timeLabel: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 8,
    lineHeight: 10,
  },
  time: {
    ...typography.bodyStrong,
    color: colors.faded,
    fontSize: 15,
    lineHeight: 18,
    fontVariant: ['tabular-nums'],
  },
  spacer: {
    flex: 1,
  },
});
