import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import type { FleetTypes } from '@/src/types/fleets';
import { colors } from '@/src/theme';
import { typography } from '@/src/theme/spacing';

const typeConfig: Record<FleetTypes, { label: string; color: string }> = {
  strategic: { label: 'STRAT', color: colors.fleetRed },
  training: { label: 'TRAIN', color: colors.green },
  non_strategic: { label: 'ROAM', color: colors.allianceBlue },
};

interface FleetTypeIconProps {
  type?: FleetTypes;
}

export function FleetTypeIcon({ type = 'non_strategic' }: FleetTypeIconProps) {
  const config = typeConfig[type];

  return (
    <View style={[styles.badge, { backgroundColor: config.color }]}>
      <Text style={styles.label}>{config.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  label: {
    ...typography.overline,
    fontFamily: 'Norwester',
    color: colors.highlight,
    fontSize: 9,
    letterSpacing: 0.8,
  },
});
