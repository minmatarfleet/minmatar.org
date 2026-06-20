import { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  SectionList,
  StyleSheet,
  View,
} from 'react-native';
import { Text } from 'react-native-paper';

import { ActivityCard } from '@/src/components/ActivityCard';
import { ActivityDetailModal } from '@/src/components/ActivityDetailModal';
import { ActivitySectionHeader } from '@/src/components/ActivitySectionHeader';
import { MinmatarButton } from '@/src/components/MinmatarButton';
import { Screen } from '@/src/components/Screen';
import { ScreenHeader } from '@/src/components/ScreenHeader';
import { useActivityFeed } from '@/src/hooks/useActivityFeed';
import type { ActivityItem } from '@/src/types/activity';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { groupActivityByTimeline } from '@/src/utils/activityTimeline';

const ACTIVITY_HEADER = {
  title: 'Activity',
  subtitle: "What's moving across the warzone",
} as const;

export default function ActivityScreen() {
  const { items, loading, refreshing, refresh, error } = useActivityFeed();
  const [selected, setSelected] = useState<ActivityItem | null>(null);
  const sections = useMemo(() => groupActivityByTimeline(items), [items]);

  const handleView = useCallback((item: ActivityItem) => {
    setSelected(item);
  }, []);

  const renderSectionHeader = useCallback(
    ({ section }: { section: { title: string; key: string } }) => (
      <ActivitySectionHeader
        title={section.title}
        isFirst={sections[0]?.key === section.key}
      />
    ),
    [sections],
  );

  const renderItem = useCallback(
    ({
      item,
      index,
      section,
    }: {
      item: ActivityItem;
      index: number;
      section: { data: ActivityItem[] };
    }) => (
      <ActivityCard
        item={item}
        isFirst={index === 0}
        isLast={index === section.data.length - 1}
        onView={handleView}
      />
    ),
    [handleView],
  );

  if (loading && items.length === 0) {
    return (
      <Screen padded={false}>
        <ScreenHeader {...ACTIVITY_HEADER} />
        <View style={styles.center}>
          <ActivityIndicator color={colors.fleetYellow} />
        </View>
      </Screen>
    );
  }

  if (error && items.length === 0) {
    return (
      <Screen padded={false}>
        <ScreenHeader {...ACTIVITY_HEADER} />
        <ScrollView
          contentContainerStyle={styles.errorContainer}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => void refresh()}
              tintColor={colors.fleetYellow}
              colors={[colors.fleetRed]}
            />
          }
        >
          <Text style={styles.errorTitle}>Couldn't load activity</Text>
          <Text style={styles.errorBody}>{error}</Text>
          <MinmatarButton
            label="Try again"
            onPress={() => void refresh()}
            disabled={refreshing}
            style={styles.retryButton}
          />
        </ScrollView>
      </Screen>
    );
  }

  return (
    <Screen padded={false}>
      <ScreenHeader {...ACTIVITY_HEADER} />
      <SectionList
        sections={sections}
        keyExtractor={(item) => item.id}
        renderSectionHeader={renderSectionHeader}
        renderItem={renderItem}
        stickySectionHeadersEnabled={false}
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
              <Text style={styles.emptyTitle}>No recent activity</Text>
              <Text style={styles.emptyBody}>
                It's been quiet the last few days.
              </Text>
            </View>
          ) : null
        }
      />
      <ActivityDetailModal item={selected} onClose={() => setSelected(null)} />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.xs,
    paddingBottom: spacing.xxxl,
  },
  center: {
    flex: 1,
    padding: spacing.xxxl,
    alignItems: 'center',
    justifyContent: 'center',
  },
  errorContainer: {
    flexGrow: 1,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xxxl,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
  },
  errorTitle: {
    ...typography.bodyStrong,
    color: colors.highlight,
    textAlign: 'center',
  },
  errorBody: {
    ...typography.body,
    color: colors.muted,
    textAlign: 'center',
    lineHeight: 22,
  },
  retryButton: {
    marginTop: spacing.sm,
    minWidth: 160,
  },
  emptyTitle: {
    ...typography.bodyStrong,
    color: colors.highlight,
    textAlign: 'center',
  },
  emptyBody: {
    ...typography.body,
    color: colors.muted,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 22,
  },
});
