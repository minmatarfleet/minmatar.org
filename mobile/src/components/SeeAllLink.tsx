import { Pressable, StyleSheet } from 'react-native';
import { Text } from 'react-native-paper';

import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

interface SeeAllLinkProps {
  label: string;
  onPress: () => void;
}

export function SeeAllLink({ label, onPress }: SeeAllLinkProps) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.wrap, pressed && styles.pressed]}>
      <Text style={styles.text}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingTop: spacing.sm,
    paddingBottom: spacing.xs,
  },
  pressed: {
    opacity: 0.8,
  },
  text: {
    ...typography.overline,
    color: colors.fleetYellow,
    fontSize: 10,
  },
});
