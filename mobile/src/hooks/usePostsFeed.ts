import { useCallback, useEffect, useState } from 'react';

import { buildTagMap, mapApiPostToListItem } from '@/src/api/mappers/posts';
import { listPosts, listTags } from '@/src/api/posts';
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
  const [propagandaTagId, setPropagandaTagId] = useState<number | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void listTags()
      .then((tags) => {
        const id = tags.find((t) => t.tag === 'Propaganda')?.tag_id;
        setPropagandaTagId(id ?? null);
      })
      .catch(() => setPropagandaTagId(null));
  }, []);

  const loadPage = useCallback(
    async (pageNum: number, replace: boolean) => {
      const tagId = filter === 'propaganda' ? propagandaTagId : undefined;
      if (filter === 'propaganda' && propagandaTagId == null) {
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

      const mapped = raw.map((post) => mapApiPostToListItem(post, tagById));

      setHasMore(raw.length >= PAGE_SIZE);
      setPosts((prev) => (replace ? mapped : [...prev, ...mapped]));
      setPage(pageNum);
    },
    [filter, propagandaTagId],
  );

  const refresh = useCallback(async () => {
    if (filter === 'propaganda' && propagandaTagId == null) {
      return;
    }
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
    if (filter === 'propaganda' && propagandaTagId == null) {
      setLoading(propagandaTagId === undefined);
      setPosts([]);
      setPage(1);
      return;
    }
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
  return mapApiPostToListItem(raw[0], tagById);
}
