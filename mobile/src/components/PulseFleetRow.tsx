import { Pressable, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Text } from 'react-native-paper';

import { StatusPill } from '@/src/components/StatusPill';
import { isActiveFleet } from '@/src/api/mappers/fleets';
import type { FleetItem } from '@/src/types/fleets';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { formatEveTimeShort } from '@/src/utils/eveTime';
import { getPlayerIcon } from '@/src/utils/eveImage';

type PulseFleetRowVariant = 'live' | 'upcoming' | 'aar';

interface PulseFleetRowProps {
  fleet: FleetItem;
  onPress?: () => void;
  variant?: PulseFleetRowVariant;
  highlighted?: boolean;
}

export function PulseFleetRow({
  fleet,
  onPress,
  variant,
  highlighted = false,
}: PulseFleetRowProps) {
  const live = variant === 'live' || (variant == null && isActiveFleet(fleet));
  const resolvedVariant: PulseFleetRowVariant = variant ?? (live ? 'live' : 'upcoming');
  const location = fleet.location?.split(' - ')[0] ?? fleet.location;
  const isAar = resolvedVariant === 'aar';

  const dateLine = isAar
    ? 'After action report'
    : live
      ? 'Live now'
      : formatEveTimeShort(fleet.start_time);

  const title = isAar ? 'Latest AAR' : fleet.fleet_commander_name;
  const meta = isAar ? fleet.fleet_commander_name : location;

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        (highlighted || live) && styles.highlighted,
        pressed && styles.pressed,
      ]}
    >
      <Image
        source={{ uri: getPlayerIcon(fleet.fleet_commander_id, 256) }}
        style={styles.thumb}
        contentFit="cover"
        transition={200}
      />
      <View style={styles.cardBody}>
        <View style={styles.topRow}>
          <Text style={styles.date}>{dateLine}</Text>
          {live && !isAar ? <StatusPill variant="active" label="Live" /> : null}
        </View>
        <Text style={styles.title} numberOfLines={2}>
          {title}
        </Text>
        {meta ? (
          <Text style={styles.meta} numberOfLines={1}>
            {meta}
          </Text>
        ) : null}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressed: {
    opacity: 0.92,
  },
  card: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  highlighted: {
    borderColor: colors.fleetRed,
  },
  thumb: {
    width: 108,
    height: 108,
  },
  cardBody: {
    flex: 1,
    padding: spacing.md,
    gap: spacing.sm,
    justifyContent: 'center',
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  date: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 9,
  },
  title: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 15,
    lineHeight: 19,
  },
  meta: {
    ...typography.caption,
    color: colors.fleetYellow,
    fontSize: 11,
  },
});
