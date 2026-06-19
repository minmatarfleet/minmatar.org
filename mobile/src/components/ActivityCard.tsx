import { StyleSheet, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Text } from 'react-native-paper';

import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { getActivityAccent, mapActivityToCard } from '@/src/utils/activityDisplay';

interface ActivityCardProps {
  item: ActivityItem;
}

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

export function ActivityCard({ item }: ActivityCardProps) {
  const { title, subheader, preview } = mapActivityToCard(item);
  const { accent, nodeBg } = getActivityAccent(item);

  return (
    <View style={styles.row}>
      <View style={[styles.node, { borderColor: accent, backgroundColor: nodeBg }]}>
        <MaterialCommunityIcons name={kindIcon(item.kind)} size={14} color={accent} />
      </View>
      <View style={[styles.card, { borderLeftColor: accent }]}>
        <Text style={[styles.title, { color: colors.text }]} numberOfLines={1}>
          {title}
        </Text>
        <Text style={styles.subheader} numberOfLines={1}>
          {subheader}
        </Text>
        <Text style={styles.preview} numberOfLines={2}>
          {preview}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.md,
  },
  node: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.xs,
  },
  card: {
    flex: 1,
    borderLeftWidth: 2,
    paddingLeft: spacing.md,
    paddingVertical: spacing.sm,
  },
  title: {
    ...typography.body,
    fontWeight: '600',
  },
  subheader: {
    ...typography.caption,
    color: colors.muted,
    marginTop: 2,
  },
  preview: {
    ...typography.caption,
    color: colors.muted,
    marginTop: spacing.xs,
  },
});
