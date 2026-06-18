import { Pressable, StyleSheet, type PressableProps, type ViewStyle } from 'react-native';
import { Text } from 'react-native-paper';
import { colors } from '@/src/theme/colors';
import { typography } from '@/src/theme/spacing';

type ButtonVariant = 'primary' | 'secondary' | 'success';

interface MinmatarButtonProps extends PressableProps {
  label: string;
  variant?: ButtonVariant;
  fullWidth?: boolean;
  style?: ViewStyle;
}

const variantStyles: Record<ButtonVariant, { bg: string; text: string; border?: string }> = {
  primary: { bg: colors.fleetRed, text: colors.fleetYellow },
  secondary: { bg: 'transparent', text: colors.fleetYellow, border: colors.borderHover },
  success: { bg: colors.green, text: colors.highlight },
};

export function MinmatarButton({
  label,
  variant = 'primary',
  fullWidth = false,
  style,
  ...props
}: MinmatarButtonProps) {
  const v = variantStyles[variant];

  return (
    <Pressable
      style={({ pressed }) => [
        styles.base,
        fullWidth && styles.fullWidth,
        {
          backgroundColor: v.bg,
          borderColor: v.border ?? 'transparent',
          borderWidth: v.border ? 1 : 0,
          opacity: pressed ? 0.88 : 1,
        },
        style,
      ]}
      {...props}
    >
      <Text style={[styles.label, { color: v.text }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    paddingHorizontal: 16,
    paddingVertical: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  fullWidth: {
    alignSelf: 'stretch',
  },
  label: {
    ...typography.bodyStrong,
    fontSize: 13,
    letterSpacing: 0.3,
  },
});
