import type { ApiPostDetail, ApiPostListItem, ApiTag } from '@/src/api/types';
import type { PostListUI, PostUI } from '@/src/types/posts';

function tagsFromIds(tagIds: number[], tagById: Map<number, string>): string[] {
  return tagIds.map((id) => tagById.get(id)).filter((t): t is string => Boolean(t));
}

export function mapApiPostToListItem(
  post: ApiPostListItem,
  tagById: Map<number, string>,
): PostListUI {
  return {
    post_id: post.post_id,
    title: post.title,
    state: post.state,
    slug: post.slug,
    date_posted: new Date(post.date_posted),
    user_id: post.user_id,
    author: {
      character_id: post.author_character_id,
      character_name: post.author_character_name,
    },
    tags: tagsFromIds(post.tag_ids, tagById),
    image: post.image || undefined,
  };
}

export function mapApiPostToDetail(post: ApiPostDetail, tagById: Map<number, string>): PostUI {
  return {
    ...mapApiPostToListItem(post, tagById),
    excerpt: post.seo_description,
    content: post.content,
  };
}

export function buildTagMap(tags: ApiTag[]): Map<number, string> {
  return new Map(tags.map((t) => [t.tag_id, t.tag]));
}
