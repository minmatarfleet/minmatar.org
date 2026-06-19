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
  const items = useActivityFeed();
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
      </View>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={false}
            onRefresh={() => {}}
            tintColor={colors.fleetYellow}
            colors={[colors.fleetRed]}
          />
        }
        ListEmptyComponent={
          <View style={styles.center}>
            <Text style={styles.empty}>No recent activity</Text>
          </View>
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
});
