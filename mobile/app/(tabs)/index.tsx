import { useCallback, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Screen } from '@/src/components/Screen';
import { PostCard } from '@/src/components/PostCard';
import { mockPosts } from '@/src/data/mockPosts';
import type { PostListUI } from '@/src/types/posts';
import { colors } from '@/src/theme';
import { spacing } from '@/src/theme/spacing';

export default function HomeScreen() {
  const router = useRouter();
  const [posts, setPosts] = useState<PostListUI[]>(mockPosts);
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    setTimeout(() => {
      setPosts([...mockPosts]);
      setRefreshing(false);
    }, 600);
  }, []);

  const renderItem = useCallback(
    ({ item, index }: { item: PostListUI; index: number }) => (
      <PostCard
        post={item}
        featured={index === 0}
        onPress={() => router.push(`/post/${item.post_id}`)}
      />
    ),
    [router]
  );

  return (
    <Screen padded={false}>
      <FlatList
        data={posts}
        keyExtractor={(item) => String(item.post_id)}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.fleetYellow}
            colors={[colors.fleetRed]}
          />
        }
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xxxl,
  },
});
