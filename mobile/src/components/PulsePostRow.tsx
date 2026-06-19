import { PostCard } from '@/src/components/PostCard';
import type { PostListUI } from '@/src/types/posts';

interface PulsePostRowProps {
  post: PostListUI;
  onPress?: () => void;
}

/** Pulse briefing headline — uses the same featured card as News. */
export function PulsePostRow({ post, onPress }: PulsePostRowProps) {
  return <PostCard post={post} featured onPress={onPress} />;
}
