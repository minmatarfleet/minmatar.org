import { apiFetch } from '@/src/api/client';
import type {
  ApiPostDetail,
  ApiPostListItem,
  ApiTag,
} from '@/src/api/types';

export interface ListPostsParams {
  status?: string;
  tag_id?: number;
  page_num?: number;
  page_size?: number;
}

export async function listPosts(params: ListPostsParams = {}): Promise<ApiPostListItem[]> {
  const query = new URLSearchParams();
  if (params.status) query.set('status', params.status);
  if (params.tag_id != null) query.set('tag_id', String(params.tag_id));
  if (params.page_num != null) query.set('page_num', String(params.page_num));
  if (params.page_size != null) query.set('page_size', String(params.page_size));
  const qs = query.toString();
  return apiFetch<ApiPostListItem[]>(`/api/blog/posts${qs ? `?${qs}` : ''}`);
}

export async function getPost(postId: number): Promise<ApiPostDetail> {
  return apiFetch<ApiPostDetail>(`/api/blog/posts/${postId}`);
}

export async function listTags(): Promise<ApiTag[]> {
  return apiFetch<ApiTag[]>('/api/blog/tags');
}

export async function findTagIdByName(name: string): Promise<number | undefined> {
  const tags = await listTags();
  return tags.find((t) => t.tag === name)?.tag_id;
}
