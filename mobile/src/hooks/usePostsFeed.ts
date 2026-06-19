import { useCallback, useEffect, useState } from 'react';

import { buildTagMap, mapApiPostToListItem } from '@/src/api/mappers/posts';
import { listPosts, listTags } from '@/src/api/posts';
import { getUserProfiles, profilesByUserId } from '@/src/api/users';
import type { PostListUI } from '@/src/types/posts';

const PAGE_SIZE = 20;

export type NewsFilter = 'all' | 'propaganda';

export function usePostsFeed(filter: NewsFilter) {
  const [posts, setPosts] = useState<PostListUI[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [propagandaTagId, setPropagandaTagId] = useState<number | undefined>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void listTags().then((tags) => {
      const id = tags.find((t) => t.tag === 'Propaganda')?.tag_id;
      setPropagandaTagId(id);
    });
  }, []);

  const loadPage = useCallback(
    async (pageNum: number, replace: boolean) => {
      const tagId = filter === 'propaganda' ? propagandaTagId : undefined;
      if (filter === 'propaganda' && propagandaTagId === undefined) {
        return;
      }

      const raw = await listPosts({
        status: 'published',
        page_num: pageNum,
        page_size: PAGE_SIZE,
        ...(tagId != null ? { tag_id: tagId } : {}),
      });

      const tags = await listTags();
      const tagById = buildTagMap(tags);
      const userIds = raw.map((p) => p.user_id);
      const profiles = await getUserProfiles(userIds);
      const profileMap = profilesByUserId(profiles);

      const mapped = raw.map((post) => {
        const profile = profileMap.get(post.user_id);
        const characterId = profile?.eve_character_profile?.character_id ?? 0;
        const authorName =
          profile?.eve_character_profile?.character_name ?? profile?.username ?? 'Unknown';
        return mapApiPostToListItem(post, tagById, authorName, characterId);
      });

      setHasMore(raw.length >= PAGE_SIZE);
      setPosts((prev) => (replace ? mapped : [...prev, ...mapped]));
      setPage(pageNum);
    },
    [filter, propagandaTagId],
  );

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      await loadPage(1, true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load posts');
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, [loadPage]);

  useEffect(() => {
    setLoading(true);
    setPosts([]);
    setPage(1);
    void refresh();
  }, [filter, propagandaTagId, refresh]);

  const loadMore = useCallback(async () => {
    if (loadingMore || !hasMore || loading) return;
    setLoadingMore(true);
    try {
      await loadPage(page + 1, false);
    } catch {
      // keep existing list
    } finally {
      setLoadingMore(false);
    }
  }, [hasMore, loadPage, loading, loadingMore, page]);

  return {
    posts,
    loading,
    refreshing,
    loadingMore,
    hasMore,
    error,
    refresh,
    loadMore,
  };
}

export async function fetchLatestPost(): Promise<PostListUI | null> {
  const raw = await listPosts({ status: 'published', page_num: 1, page_size: 1 });
  if (raw.length === 0) return null;
  const tags = await listTags();
  const tagById = buildTagMap(tags);
  const profiles = await getUserProfiles([raw[0].user_id]);
  const profile = profiles[0];
  const characterId = profile?.eve_character_profile?.character_id ?? 0;
  const authorName =
    profile?.eve_character_profile?.character_name ?? profile?.username ?? 'Unknown';
  return mapApiPostToListItem(raw[0], tagById, authorName, characterId);
}
