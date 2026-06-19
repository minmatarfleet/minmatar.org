import { useCallback, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { ActivityCard } from '@/src/components/ActivityCard';
import { ActivityDetailModal } from '@/src/components/ActivityDetailModal';
import { Screen } from '@/src/components/Screen';
import { useActivityFeed } from '@/src/hooks/useActivityFeed';
import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export default function ActivityScreen() {
  const { items, refreshing, refresh, error, isPreview } = useActivityFeed();
  const [selected, setSelected] = useState<ActivityItem | null>(null);

  const handleView = useCallback((item: ActivityItem) => {
    setSelected(item);
  }, []);

  const renderItem = useCallback(
    ({ item, index }: { item: ActivityItem; index: number }) => (
      <ActivityCard
        item={item}
        isFirst={index === 0}
        isLast={index === items.length - 1}
        onView={handleView}
      />
    ),
    [handleView, items.length],
  );

  return (
    <Screen padded={false}>
      <View style={styles.header}>
        <Text style={styles.subtitle}>
          Live fleets, kill bursts, FC comms, and militia movement
        </Text>
        {isPreview ? (
          <Text style={styles.previewHint}>
            Preview data — live warzone feed is empty or still rolling out.
          </Text>
        ) : null}
      </View>
      {error && !isPreview ? (
        <View style={styles.center}>
          <Text style={styles.error}>{error}</Text>
        </View>
      ) : null}
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => void refresh()}
            tintColor={colors.fleetYellow}
            colors={[colors.fleetRed]}
          />
        }
        ListEmptyComponent={
          !refreshing ? (
            <View style={styles.center}>
              <Text style={styles.empty}>No recent activity</Text>
            </View>
          ) : null
        }
      />
      <ActivityDetailModal item={selected} onClose={() => setSelected(null)} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  subtitle: {
    ...typography.caption,
    color: colors.muted,
  },
  previewHint: {
    ...typography.caption,
    color: colors.fleetYellow,
    marginTop: spacing.xs,
  },
  list: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
    paddingBottom: spacing.xxxl,
  },
  center: {
    padding: spacing.xxxl,
    alignItems: 'center',
  },
  empty: {
    ...typography.body,
    color: colors.muted,
  },
  error: {
    ...typography.caption,
    color: colors.fleetRed,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
});
