import { Pressable, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Text } from 'react-native-paper';
import type { PostListUI } from '@/src/types/posts';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { getPlayerIcon } from '@/src/utils/eveImage';
import { Tag } from './Tag';

interface PostCardProps {
  post: PostListUI;
  featured?: boolean;
  onPress?: () => void;
}

const tagColorForTag = (tag: string): 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green' | 'fleet-yellow' => {
  if (tag === 'Frontlines') return 'fleet-red';
  if (tag === 'Metropolis' || tag === 'Metro Daily News') return 'alliance-blue';
  if (tag === 'Propaganda') return 'militia-purple';
  if (tag === 'Rust and Blood') return 'green';
  return 'fleet-yellow';
};

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

export function PostCard({ post, featured = false, onPress }: PostCardProps) {
  const imageUri = post.image ?? getPlayerIcon(post.author.character_id, 512);

  if (featured) {
    return (
      <Pressable onPress={onPress} style={({ pressed }) => [styles.featuredCard, pressed && styles.pressed]}>
        <View style={styles.featuredImageWrap}>
          <Image source={{ uri: imageUri }} style={styles.featuredImage} contentFit="cover" transition={300} />
          <LinearGradient
            colors={['transparent', 'rgba(0,0,0,0.3)', colors.surface]}
            locations={[0.2, 0.55, 1]}
            style={styles.featuredScrim}
          />
          <View style={styles.featuredOverlay}>
            <Text style={styles.featuredDate}>{formatDate(post.date_posted)}</Text>
            <Text style={styles.featuredTitle} numberOfLines={3}>
              {post.title}
            </Text>
          </View>
        </View>
        <View style={styles.featuredBody}>
          <View style={styles.tagRow}>
            {post.tags.map((tag) => (
              <Tag key={tag} text={tag} color={tagColorForTag(tag)} />
            ))}
          </View>
          <AuthorRow name={post.author.character_name} characterId={post.author.character_id} />
        </View>
      </Pressable>
    );
  }

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <Image source={{ uri: imageUri }} style={styles.thumb} contentFit="cover" transition={200} />
      <View style={styles.cardBody}>
        <Text style={styles.date}>{formatDate(post.date_posted)}</Text>
        <Text style={styles.title} numberOfLines={2}>
          {post.title}
        </Text>
        <View style={styles.tagRow}>
          {post.tags.slice(0, 2).map((tag) => (
            <Tag key={tag} text={tag} color={tagColorForTag(tag)} narrow />
          ))}
        </View>
        <AuthorRow name={post.author.character_name} characterId={post.author.character_id} compact />
      </View>
    </Pressable>
  );
}

function AuthorRow({
  name,
  characterId,
  compact = false,
}: {
  name: string;
  characterId: number;
  compact?: boolean;
}) {
  return (
    <View style={styles.authorRow}>
      <Image
        source={{ uri: getPlayerIcon(characterId, 64) }}
        style={[styles.authorAvatar, compact && styles.authorAvatarSm]}
        contentFit="cover"
      />
      <Text style={[styles.authorName, compact && styles.authorNameSm]}>{name}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pressed: {
    opacity: 0.92,
  },
  featuredCard: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderHover,
    marginBottom: spacing.xl,
    overflow: 'hidden',
  },
  featuredImageWrap: {
    height: 240,
    position: 'relative',
  },
  featuredImage: {
    ...StyleSheet.absoluteFillObject,
  },
  featuredScrim: {
    ...StyleSheet.absoluteFillObject,
  },
  featuredOverlay: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  featuredDate: {
    ...typography.overline,
    color: colors.fleetYellow,
    fontSize: 10,
  },
  featuredTitle: {
    ...typography.display,
    color: colors.highlight,
    fontSize: 24,
    lineHeight: 28,
  },
  featuredBody: {
    padding: spacing.lg,
    gap: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  card: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  thumb: {
    width: 108,
    height: 108,
  },
  cardBody: {
    flex: 1,
    padding: spacing.md,
    gap: spacing.sm,
    justifyContent: 'center',
  },
  date: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 9,
  },
  title: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 15,
    lineHeight: 19,
  },
  tagRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  authorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  authorAvatar: {
    width: 24,
    height: 24,
    borderWidth: 1,
    borderColor: colors.borderHover,
  },
  authorAvatarSm: {
    width: 20,
    height: 20,
  },
  authorName: {
    ...typography.caption,
    color: colors.fleetYellow,
  },
  authorNameSm: {
    fontSize: 11,
  },
});
