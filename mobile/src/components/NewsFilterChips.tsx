import { Pressable, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export type NewsFilter = 'all' | 'propaganda';

interface NewsFilterChipsProps {
  value: NewsFilter;
  onChange: (value: NewsFilter) => void;
}

const OPTIONS: { id: NewsFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'propaganda', label: 'Propaganda' },
];

export function NewsFilterChips({ value, onChange }: NewsFilterChipsProps) {
  return (
    <View style={styles.row}>
      {OPTIONS.map((opt) => {
        const active = opt.id === value;
        return (
          <Pressable
            key={opt.id}
            onPress={() => onChange(opt.id)}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.label, active && styles.labelActive]}>{opt.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
  },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: {
    backgroundColor: colors.fleetRedMuted,
    borderColor: colors.fleetRed,
  },
  label: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 10,
  },
  labelActive: {
    color: colors.fleetYellow,
  },
});
