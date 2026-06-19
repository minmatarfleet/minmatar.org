import { ScrollView, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import Markdown from 'react-native-markdown-display';
import { Text } from 'react-native-paper';
import { AuthorRow } from '@/src/components/AuthorRow';
import { RequireAuth } from '@/src/auth/RequireAuth';
import { MinmatarButton } from '@/src/components/MinmatarButton';
import { Tag } from '@/src/components/Tag';
import { getPostById } from '@/src/data/mockPosts';
import { colors } from '@/src/theme';
import { markdownStyles } from '@/src/theme/markdown';
import { spacing, typography } from '@/src/theme/spacing';
import { getPlayerIcon } from '@/src/utils/eveImage';

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

export default function PostDetailScreen() {
  const router = useRouter();
  const { post_id } = useLocalSearchParams<{ post_id: string }>();
  const post = getPostById(Number(post_id));

  if (!post) {
    return (
      <RequireAuth>
        <View style={styles.notFound}>
          <Text style={styles.notFoundTitle}>Article not found</Text>
          <MinmatarButton label="Go back" onPress={() => router.back()} />
        </View>
      </RequireAuth>
    );
  }

  const imageUri = post.image ?? getPlayerIcon(post.author.character_id, 512);

  return (
    <RequireAuth>
    <>
      <Stack.Screen options={{ title: 'Article', headerBackTitle: 'News' }} />
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <Image source={{ uri: imageUri }} style={styles.heroImage} contentFit="cover" />
          <LinearGradient
            colors={['transparent', colors.scrim, colors.background]}
            locations={[0.3, 0.7, 1]}
            style={styles.heroScrim}
          />
        </View>

        <View style={styles.body}>
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

          <Text style={styles.excerpt}>{post.excerpt}</Text>

          <View style={styles.divider} />

          <Markdown style={markdownStyles}>{post.content}</Markdown>
        </View>
      </ScrollView>
    </>
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
