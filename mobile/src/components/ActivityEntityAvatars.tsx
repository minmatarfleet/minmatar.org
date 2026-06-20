import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Text } from 'react-native-paper';

import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { getPlayerIcon, getTypeIcon } from '@/src/utils/eveImage';

const AVATAR_SIZE = 22;
const MAX_VISIBLE = 7;

interface ActivityEntityAvatarsProps {
  item: ActivityItem;
}

export function ActivityEntityAvatars({ item }: ActivityEntityAvatarsProps) {
  if (item.kind === 'fleet_active' && item.roster?.length) {
    const visible = item.roster.slice(0, MAX_VISIBLE);
    const extra =
      item.roster_total != null
        ? Math.max(0, item.roster_total - visible.length)
        : Math.max(0, item.roster.length - visible.length);

    return (
      <View style={styles.row}>
        {visible.map((pilot) => (
          <Image
            key={pilot.character_id}
            source={{ uri: getPlayerIcon(pilot.character_id, 64) }}
            style={styles.portrait}
            contentFit="cover"
            accessibilityLabel={pilot.name}
          />
        ))}
        {extra > 0 ? (
          <View style={styles.moreBadge}>
            <Text style={styles.moreText}>+{extra}</Text>
          </View>
        ) : null}
      </View>
    );
  }

  if (item.kind === 'killmail_batch' && item.ships?.length) {
    const visible = item.ships.filter((ship) => ship.type_id != null).slice(0, MAX_VISIBLE);
    if (!visible.length) {
      return null;
    }

    return (
      <View style={styles.row}>
        {visible.map((ship) => (
          <View key={ship.type_id} style={styles.shipWrap}>
            <Image
              source={{ uri: getTypeIcon(ship.type_id!, 64) }}
              style={styles.shipIcon}
              contentFit="contain"
              accessibilityLabel={ship.name}
            />
            {ship.count > 1 ? (
              <View style={styles.countBadge}>
                <Text style={styles.countText}>{ship.count}</Text>
              </View>
            ) : null}
          </View>
        ))}
      </View>
    );
  }

  return null;
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: 2,
    minHeight: AVATAR_SIZE,
  },
  portrait: {
    width: AVATAR_SIZE,
    height: AVATAR_SIZE,
    borderRadius: AVATAR_SIZE / 2,
    borderWidth: 1,
    borderColor: colors.borderHover,
    backgroundColor: colors.surfaceRaised,
  },
  shipWrap: {
    width: AVATAR_SIZE,
    height: AVATAR_SIZE,
    position: 'relative',
  },
  shipIcon: {
    width: AVATAR_SIZE,
    height: AVATAR_SIZE,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.borderHover,
    backgroundColor: colors.surfaceRaised,
  },
  countBadge: {
    position: 'absolute',
    right: -4,
    bottom: -3,
    minWidth: 12,
    height: 12,
    borderRadius: 6,
    paddingHorizontal: 2,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderHover,
    alignItems: 'center',
    justifyContent: 'center',
  },
  countText: {
    ...typography.caption,
    fontSize: 8,
    lineHeight: 10,
    color: colors.highlight,
  },
  moreBadge: {
    minWidth: AVATAR_SIZE,
    height: AVATAR_SIZE,
    borderRadius: AVATAR_SIZE / 2,
    paddingHorizontal: spacing.xs,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.borderHover,
    alignItems: 'center',
    justifyContent: 'center',
  },
  moreText: {
    ...typography.caption,
    fontSize: 10,
    lineHeight: 12,
    color: colors.faded,
  },
});
