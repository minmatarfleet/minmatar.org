import type { ApiPostDetail, ApiPostListItem, ApiTag } from '@/src/api/types';
import type { PostListUI, PostUI } from '@/src/types/posts';

function tagsFromIds(tagIds: number[], tagById: Map<number, string>): string[] {
  return tagIds.map((id) => tagById.get(id)).filter((t): t is string => Boolean(t));
}

export function mapApiPostToListItem(
  post: ApiPostListItem,
  tagById: Map<number, string>,
  authorName: string,
  characterId: number,
): PostListUI {
  return {
    post_id: post.post_id,
    title: post.title,
    state: post.state,
    slug: post.slug,
    date_posted: new Date(post.date_posted),
    user_id: post.user_id,
    author: { character_id: characterId, character_name: authorName },
    tags: tagsFromIds(post.tag_ids, tagById),
    image: post.image || undefined,
  };
}

export function mapApiPostToDetail(
  post: ApiPostDetail,
  tagById: Map<number, string>,
  authorName: string,
  characterId: number,
): PostUI {
  return {
    ...mapApiPostToListItem(post, tagById, authorName, characterId),
    excerpt: post.seo_description,
    content: post.content,
  };
}

export function buildTagMap(tags: ApiTag[]): Map<number, string> {
  return new Map(tags.map((t) => [t.tag_id, t.tag]));
}
