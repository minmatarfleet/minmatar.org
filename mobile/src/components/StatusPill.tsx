import { useEffect, useRef } from 'react';
import { Animated, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

type StatusVariant = 'active' | 'completed' | 'cancelled' | 'upcoming';

interface StatusPillProps {
  variant: StatusVariant;
  label: string;
}

const variantConfig: Record<StatusVariant, { bg: string; text: string; pulse?: boolean }> = {
  active: { bg: colors.fleetRedMuted, text: colors.fleetRed, pulse: true },
  completed: { bg: colors.greenMuted, text: colors.green },
  cancelled: { bg: 'rgba(255,255,255,0.06)', text: colors.muted },
  upcoming: { bg: 'rgba(241, 217, 160, 0.1)', text: colors.fleetYellow },
};

export function StatusPill({ variant, label }: StatusPillProps) {
  const config = variantConfig[variant];
  const pulse = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!config.pulse) return;

    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(pulse, { toValue: 0.45, duration: 900, useNativeDriver: true }),
        Animated.timing(pulse, { toValue: 1, duration: 900, useNativeDriver: true }),
      ])
    );
    animation.start();
    return () => animation.stop();
  }, [config.pulse, pulse]);

  return (
    <View style={[styles.pill, { backgroundColor: config.bg }]}>
      {config.pulse && (
        <Animated.View style={[styles.dot, { backgroundColor: config.text, opacity: pulse }]} />
      )}
      <Text style={[styles.label, { color: config.text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  label: {
    ...typography.overline,
    fontSize: 11,
  },
});
