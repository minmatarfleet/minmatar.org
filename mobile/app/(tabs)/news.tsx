import { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  View,
} from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Text } from 'react-native-paper';

import { PostCard } from '@/src/components/PostCard';
import { NewsFilterChips, type NewsFilter } from '@/src/components/NewsFilterChips';
import { Screen } from '@/src/components/Screen';
import { ScreenHeader } from '@/src/components/ScreenHeader';
import { usePostsFeed } from '@/src/hooks/usePostsFeed';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export default function NewsScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ filter?: string }>();
  const initialFilter: NewsFilter = params.filter === 'propaganda' ? 'propaganda' : 'all';
  const [filter, setFilter] = useState<NewsFilter>(initialFilter);
  const { posts, loading, refreshing, loadingMore, hasMore, error, refresh, loadMore } =
    usePostsFeed(filter);

  const renderItem = useCallback(
    ({ item, index }: { item: (typeof posts)[0]; index: number }) => (
      <PostCard
        post={item}
        featured={index === 0 && filter === 'all'}
        onPress={() => router.push(`/post/${item.post_id}`)}
      />
    ),
    [filter, router],
  );

  const newsSubtitle =
    filter === 'propaganda'
      ? 'Voice from the front lines'
      : 'Stories and updates from the alliance';

  return (
    <Screen padded={false}>
      <ScreenHeader title="News" subtitle={newsSubtitle} />
      <NewsFilterChips value={filter} onChange={setFilter} />
      {loading && posts.length === 0 ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.fleetYellow} />
        </View>
      ) : error ? (
        <View style={styles.center}>
          <Text style={styles.error}>{error}</Text>
        </View>
      ) : (
        <FlatList
          key={filter}
          data={posts}
          keyExtractor={(item) => String(item.post_id)}
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
          onEndReached={() => void loadMore()}
          onEndReachedThreshold={0.4}
          ListFooterComponent={
            loadingMore ? (
              <ActivityIndicator color={colors.fleetYellow} style={styles.footer} />
            ) : null
          }
          ListEmptyComponent={
            !loading ? (
              <View style={styles.center}>
                <Text style={styles.empty}>No posts yet</Text>
              </View>
            ) : null
          }
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxxl,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xxxl,
  },
  error: {
    ...typography.body,
    color: colors.fleetRed,
    textAlign: 'center',
  },
  empty: {
    ...typography.body,
    color: colors.muted,
  },
  footer: {
    paddingVertical: spacing.lg,
  },
});
