import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import type { WarzoneSystemHot } from '@/src/types/warzone';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

interface WarzoneChangesTableProps {
  systems: WarzoneSystemHot[];
  hasFull24hWindow?: boolean;
}

function formatDelta(delta: number): string {
  if (delta === 0) return '0%';
  const sign = delta > 0 ? '+' : '';
  return `${sign}${delta}%`;
}

function deltaStyle(delta: number) {
  if (delta > 0) return styles.deltaUp;
  if (delta < 0) return styles.deltaDown;
  return styles.deltaFlat;
}

export function WarzoneChangesTable({ systems, hasFull24hWindow }: WarzoneChangesTableProps) {
  if (systems.length === 0) {
    return null;
  }

  const ordered = [...systems].sort(
    (a, b) =>
      Math.abs(b.delta_24h) - Math.abs(a.delta_24h) ||
      b.delta_24h - a.delta_24h ||
      a.system_name.localeCompare(b.system_name),
  );

  return (
    <View>
      {hasFull24hWindow === false ? (
        <Text style={styles.partialNote}>
          Showing change since the earliest reading in the last 24 hours.
        </Text>
      ) : null}
      <View style={styles.table}>
      <View style={styles.headerRow}>
        <Text style={[styles.headerCell, styles.systemCol]}>System</Text>
        <Text style={[styles.headerCell, styles.nowCol]}>Now</Text>
        <Text style={[styles.headerCell, styles.deltaCol]}>24h</Text>
      </View>
      {ordered.map((system) => (
        <View key={system.system_id} style={styles.row}>
          <View style={styles.systemCol}>
            <Text style={styles.systemName} numberOfLines={1}>
              {system.system_name}
            </Text>
          </View>
          <Text style={[styles.cell, styles.nowCol]}>{system.contested_percent}%</Text>
          <Text style={[styles.cell, styles.deltaCol, deltaStyle(system.delta_24h)]}>
            {formatDelta(system.delta_24h)}
          </Text>
        </View>
      ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  table: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    backgroundColor: colors.surfaceRaised,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  headerCell: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 9,
  },
  cell: {
    ...typography.caption,
    color: colors.highlight,
    fontSize: 12,
    fontWeight: '600',
  },
  systemCol: {
    flex: 1,
    minWidth: 0,
  },
  nowCol: {
    width: 52,
    textAlign: 'right',
  },
  deltaCol: {
    width: 52,
    textAlign: 'right',
  },
  systemName: {
    ...typography.caption,
    color: colors.highlight,
    fontSize: 13,
  },
  deltaUp: {
    color: colors.green,
  },
  deltaDown: {
    color: colors.fleetRed,
  },
  deltaFlat: {
    color: colors.muted,
  },
  partialNote: {
    ...typography.caption,
    color: colors.muted,
    fontSize: 11,
    lineHeight: 16,
    marginBottom: spacing.sm,
  },
});
