import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

interface ActivitySectionHeaderProps {
  title: string;
  isFirst?: boolean;
}

export function ActivitySectionHeader({ title, isFirst = false }: ActivitySectionHeaderProps) {
  return (
    <View style={[styles.container, isFirst ? styles.first : styles.follow]}>
      <Text style={styles.title}>{title}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: spacing.xs,
  },
  first: {
    paddingTop: spacing.xs,
    paddingBottom: spacing.xs,
  },
  follow: {
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
  title: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 11,
    letterSpacing: 1.2,
  },
});
