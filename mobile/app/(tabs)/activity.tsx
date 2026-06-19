import { useCallback } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { ActivityCard } from '@/src/components/ActivityCard';
import { Screen } from '@/src/components/Screen';
import { useActivityFeed } from '@/src/hooks/useActivityFeed';
import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export default function ActivityScreen() {
  const { items, refreshing, refresh, error } = useActivityFeed();

  const renderItem = useCallback(
    ({ item }: { item: ActivityItem }) => <ActivityCard item={item} />,
    [],
  );

  return (
    <Screen padded={false}>
      <View style={styles.header}>
        <Text style={styles.subtitle}>
          Live fleets, kill bursts, FC comms, and militia movement
        </Text>
      </View>
      {error ? (
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
    paddingHorizontal: spacing.lg,
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
