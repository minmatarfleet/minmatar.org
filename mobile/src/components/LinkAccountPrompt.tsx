import { Linking, Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { MY_MINMATAR_URL } from '@/src/config/env';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

interface LinkAccountPromptProps {
  compact?: boolean;
}

export function LinkAccountPrompt({ compact = false }: LinkAccountPromptProps) {
  return (
    <View style={[styles.wrap, compact && styles.wrapCompact]}>
      <Text style={styles.title}>Link your character</Text>
      <Text style={styles.body}>
        Connect this character on my.minmatar.org to see fleet schedules and ops.
      </Text>
      <Pressable
        onPress={() => void Linking.openURL(MY_MINMATAR_URL)}
        style={({ pressed }) => [styles.link, pressed && styles.pressed]}
      >
        <Text style={styles.linkText}>Open my.minmatar.org</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    padding: spacing.lg,
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  wrapCompact: {
    marginHorizontal: spacing.lg,
  },
  title: {
    ...typography.bodyStrong,
    color: colors.highlight,
  },
  body: {
    ...typography.caption,
    color: colors.muted,
    lineHeight: 18,
  },
  link: {
    alignSelf: 'flex-start',
    marginTop: spacing.xs,
  },
  linkText: {
    ...typography.overline,
    color: colors.fleetYellow,
    fontSize: 11,
  },
  pressed: {
    opacity: 0.8,
  },
});
