import { Pressable, StyleSheet, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Text } from 'react-native-paper';

import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { formatTimelineTime } from '@/src/utils/eveTime';
import {
  ACTIVITY_CARD_HEIGHT,
  ACTIVITY_PREVIEW_LINES,
  getActivityAccent,
  kindLabel,
  mapActivityToCard,
} from '@/src/utils/activityDisplay';

const RAIL_WIDTH = 36;
const NODE_SIZE = 24;
const LINE_WIDTH = 2;

function kindIcon(kind: ActivityItem['kind']): keyof typeof MaterialCommunityIcons.glyphMap {
  switch (kind) {
    case 'fleet_active':
      return 'flag-variant-outline';
    case 'killmail_batch':
      return 'skull-crossbones-outline';
    case 'communication':
      return 'bullhorn-outline';
    case 'militia_joins':
      return 'account-group-outline';
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
          <MaterialCommunityIcons name={kindIcon(item.kind)} size={13} color={accent} />
        </View>
        {!isLast ? <View style={styles.lineBelow} /> : null}
      </View>

      <View style={styles.content}>
        <View style={[styles.card, { borderLeftColor: accent }]}>
          <View style={styles.cardHeader}>
            <Text style={[styles.label, { color: accent }]}>{kindLabel(item.kind)}</Text>
            <Text style={styles.time}>{formatTimelineTime(item.timestamp)}</Text>
          </View>

          <View style={styles.cardBody}>
            <Text style={styles.title} numberOfLines={1}>
              {title}
            </Text>
            <Text style={styles.subheader} numberOfLines={1}>
              {subheader}
            </Text>
            <Text style={styles.preview} numberOfLines={ACTIVITY_PREVIEW_LINES}>
              {preview}
            </Text>
          </View>

          <Pressable
            onPress={() => onView(item)}
            style={({ pressed }) => [styles.viewBtn, pressed && styles.viewBtnPressed]}
            hitSlop={4}
          >
            <Text style={[styles.viewLabel, { color: accent }]}>View</Text>
            <MaterialCommunityIcons name="chevron-right" size={16} color={accent} />
          </Pressable>
        </View>
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
    height: spacing.sm,
  },
  lineAbove: {
    width: LINE_WIDTH,
    height: spacing.sm,
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
    minHeight: ACTIVITY_CARD_HEIGHT + spacing.lg,
    backgroundColor: colors.borderHover,
  },
  content: {
    flex: 1,
    paddingLeft: spacing.sm,
    paddingBottom: spacing.lg,
  },
  card: {
    height: ACTIVITY_CARD_HEIGHT,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 3,
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  cardBody: {
    flex: 1,
    gap: 2,
  },
  label: {
    ...typography.overline,
    fontSize: 9,
  },
  time: {
    ...typography.caption,
    color: colors.muted,
    fontSize: 11,
  },
  title: {
    ...typography.bodyStrong,
    color: colors.highlight,
    fontSize: 14,
    lineHeight: 18,
  },
  subheader: {
    ...typography.caption,
    color: colors.faded,
    fontSize: 12,
    lineHeight: 16,
  },
  preview: {
    ...typography.caption,
    color: colors.faded,
    fontSize: 12,
    lineHeight: 16,
    marginTop: spacing.xs,
  },
  viewBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-end',
    gap: 2,
    marginTop: spacing.xs,
  },
  viewBtnPressed: {
    opacity: 0.7,
  },
  viewLabel: {
    ...typography.bodyStrong,
    fontSize: 12,
  },
});
