import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import Markdown from 'react-native-markdown-display';
import { Text } from 'react-native-paper';

import { buildTagMap, mapApiPostToDetail } from '@/src/api/mappers/posts';
import { getPost, listTags } from '@/src/api/posts';
import { RequireAuth } from '@/src/auth/RequireAuth';
import { AuthorRow } from '@/src/components/AuthorRow';
import { MediaViewer } from '@/src/components/MediaViewer';
import { MinmatarButton } from '@/src/components/MinmatarButton';
import { Tag } from '@/src/components/Tag';
import type { PostUI } from '@/src/types/posts';
import { colors } from '@/src/theme';
import { markdownStyles } from '@/src/theme/markdown';
import { spacing, typography } from '@/src/theme/spacing';
import { getPostCoverImage } from '@/src/utils/postAuthor';
import {
  extractYoutubeVideoIds,
  hasReadableMarkdownContent,
  isVideoPost,
  stripMediaEmbeds,
} from '@/src/utils/postMedia';

const tagColorForTag = (tag: string): 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green' | 'fleet-yellow' => {
  if (tag === 'Frontlines') return 'fleet-red';
  if (tag === 'Metropolis' || tag === 'Metro Daily News') return 'alliance-blue';
  if (tag === 'Propaganda') return 'militia-purple';
  if (tag === 'Rust and Blood') return 'green';
  return 'fleet-yellow';
};

function formatDate(date: Date): string {
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

function PostDetailContent() {
  const router = useRouter();
  const { post_id } = useLocalSearchParams<{ post_id: string }>();
  const [post, setPost] = useState<PostUI | null>(null);
  const [loading, setLoading] = useState(true);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const raw = await getPost(Number(post_id));
        const tags = await listTags();
        const tagById = buildTagMap(tags);
        if (active) {
          setPost(mapApiPostToDetail(raw, tagById));
        }
      } catch {
        if (active) setMissing(true);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [post_id]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.fleetYellow} />
      </View>
    );
  }

  if (!post || missing) {
    return (
      <View style={styles.notFound}>
        <Text style={styles.notFoundTitle}>Article not found</Text>
        <MinmatarButton label="Go back" onPress={() => router.back()} />
      </View>
    );
  }

  const imageUri = getPostCoverImage(post);
  const videoIds = extractYoutubeVideoIds(post.content);
  const isVideo = isVideoPost(post.content);
  const markdownContent = stripMediaEmbeds(post.content);
  const showMarkdown = hasReadableMarkdownContent(post.content);

  return (
    <>
      <Stack.Screen options={{ title: isVideo ? 'Video' : 'Article', headerBackTitle: 'News' }} />
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        {isVideo ? (
          <MediaViewer videoIds={videoIds} />
        ) : (
          <View style={styles.hero}>
            <Image source={{ uri: imageUri }} style={styles.heroImage} contentFit="cover" />
            <LinearGradient
              colors={['transparent', colors.scrim, colors.background]}
              locations={[0.3, 0.7, 1]}
              style={styles.heroScrim}
            />
          </View>
        )}

        <View style={[styles.body, isVideo && styles.bodyVideo]}>
          <Text style={styles.date}>{formatDate(post.date_posted)}</Text>
          <Text style={styles.title}>{post.title}</Text>

          <View style={styles.tagRow}>
            {post.tags.map((tag) => (
              <Tag key={tag} text={tag} color={tagColorForTag(tag)} />
            ))}
          </View>

          <AuthorRow
            characterId={post.author.character_id}
            name={post.author.character_name}
            label="Author"
            large
          />

          {post.excerpt ? <Text style={styles.excerpt}>{post.excerpt}</Text> : null}

          {showMarkdown ? (
            <>
              <View style={styles.divider} />
              <Markdown style={markdownStyles}>{markdownContent}</Markdown>
            </>
          ) : null}
        </View>
      </ScrollView>
    </>
  );
}

export default function PostDetailScreen() {
  return (
    <RequireAuth>
      <PostDetailContent />
    </RequireAuth>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    paddingBottom: spacing.xxxl,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  hero: {
    height: 220,
    position: 'relative',
  },
  heroImage: {
    ...StyleSheet.absoluteFillObject,
  },
  heroScrim: {
    ...StyleSheet.absoluteFillObject,
  },
  body: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    gap: spacing.lg,
    marginTop: -spacing.xxl,
  },
  bodyVideo: {
    marginTop: 0,
  },
  date: {
    ...typography.overline,
    color: colors.muted,
  },
  title: {
    ...typography.display,
    color: colors.highlight,
    fontSize: 28,
    lineHeight: 32,
  },
  tagRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  excerpt: {
    ...typography.body,
    color: colors.fleetYellow,
    fontSize: 16,
    lineHeight: 24,
    fontStyle: 'italic',
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
  },
  notFound: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xxxl,
    gap: spacing.lg,
  },
  notFoundTitle: {
    ...typography.title,
    color: colors.highlight,
  },
});
