import type { CharacterBasic, PostListUI } from '@/src/types/posts';
import { getFleetLogoSquareUrl, getPlayerIcon } from '@/src/utils/eveImage';

export const MINMATAR_FLEET_AUTHOR_NAME = 'Minmatar Fleet';

export function isFleetAuthor(author: CharacterBasic): boolean {
  return author.character_id === 0;
}

export function getPostCoverImage(post: Pick<PostListUI, 'image' | 'author'>): string {
  if (post.image) {
    return post.image;
  }

  if (post.author.character_id > 0) {
    return getPlayerIcon(post.author.character_id, 512);
  }

  return getFleetLogoSquareUrl();
}
