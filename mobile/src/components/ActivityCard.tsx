import { Pressable, StyleSheet, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Text } from 'react-native-paper';

import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { formatTimelineTime } from '@/src/utils/eveTime';
import { ActivityEntityAvatars } from '@/src/components/ActivityEntityAvatars';
import {
  ACTIVITY_CARD_MIN_HEIGHT,
  ACTIVITY_PREVIEW_LINES,
  getActivityAccent,
  kindLabel,
  mapActivityToCard,
} from '@/src/utils/activityDisplay';

const RAIL_WIDTH = 28;
const NODE_SIZE = 18;
const LINE_WIDTH = 2;

function kindIcon(kind: ActivityItem['kind']): keyof typeof MaterialCommunityIcons.glyphMap {
  switch (kind) {
    case 'fleet_active':
      return 'flag-variant-outline';
    case 'killmail_batch':
      return 'skull-crossbones-outline';
    case 'communication':
      return 'bullhorn-outline';
    case 'contested_change':
      return 'map-marker-radius-outline';
  }
}

interface ActivityCardProps {
  item: ActivityItem;
  isFirst?: boolean;
  isLast?: boolean;
  onView: (item: ActivityItem) => void;
}

export function ActivityCard({ item, isFirst = false, isLast = false, onView }: ActivityCardProps) {
  const { title, subheader, preview } = mapActivityToCard(item);
  const { accent, nodeBg } = getActivityAccent(item);

  return (
    <View style={styles.row}>
      <View style={styles.rail}>
        {!isFirst ? <View style={styles.lineAbove} /> : <View style={styles.railSpacer} />}
        <View style={[styles.node, { borderColor: accent, backgroundColor: nodeBg }]}>
          <MaterialCommunityIcons name={kindIcon(item.kind)} size={10} color={accent} />
        </View>
        {!isLast ? <View style={styles.lineBelow} /> : null}
      </View>

      <View style={styles.content}>
        <Pressable
          onPress={() => onView(item)}
          style={({ pressed }) => [styles.card, { borderLeftColor: accent }, pressed && styles.cardPressed]}
        >
          <View style={styles.cardHeader}>
            <Text style={[styles.label, { color: accent }]}>{kindLabel(item)}</Text>
            <View style={styles.headerMeta}>
              <Text style={styles.time}>{formatTimelineTime(item.timestamp)}</Text>
              <MaterialCommunityIcons name="chevron-right" size={14} color={accent} />
            </View>
          </View>

          <Text style={styles.title} numberOfLines={1}>
            {title}
          </Text>
          <Text style={styles.subheader} numberOfLines={1}>
            {subheader}
          </Text>
          <ActivityEntityAvatars item={item} />
          <Text style={styles.preview} numberOfLines={ACTIVITY_PREVIEW_LINES}>
            {preview}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'stretch',
  },
  rail: {
    width: RAIL_WIDTH,
    alignItems: 'center',
  },
  railSpacer: {
    height: spacing.xs,
  },
  lineAbove: {
    width: LINE_WIDTH,
    height: spacing.xs,
    backgroundColor: colors.borderHover,
  },
  node: {
    width: NODE_SIZE,
    height: NODE_SIZE,
    borderRadius: NODE_SIZE / 2,
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.borderHover,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
  },
  lineBelow: {
    width: LINE_WIDTH,
    flex: 1,
    minHeight: ACTIVITY_CARD_MIN_HEIGHT + spacing.md,
    backgroundColor: colors.borderHover,
  },
  content: {
    flex: 1,
    paddingLeft: spacing.xs,
    paddingBottom: spacing.md,
  },
  card: {
    minHeight: ACTIVITY_CARD_MIN_HEIGHT,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 3,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm,
    gap: 1,
  },
  cardPressed: {
    opacity: 0.85,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 2,
  },
  headerMeta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  label: {
    ...typography.overline,
    fontSize: 8,
  },
  time: {
    ...typography.caption,
    color: colors.muted,
    fontSize: 10,
    lineHeight: 13,
  },
  title: {
    ...typography.bodyStrong,
    color: colors.highlight,
    fontSize: 13,
    lineHeight: 17,
  },
  subheader: {
    ...typography.caption,
    color: colors.faded,
    fontSize: 11,
    lineHeight: 14,
  },
  preview: {
    ...typography.caption,
    color: colors.faded,
    fontSize: 11,
    lineHeight: 14,
    marginTop: 2,
  },
});
