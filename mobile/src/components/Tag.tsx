import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import type { TagColor } from '@/src/theme/colors';
import { tagColorMap } from '@/src/theme/colors';
import { typography } from '@/src/theme/spacing';

interface TagProps {
  text: string;
  color?: TagColor;
  narrow?: boolean;
}

export function Tag({ text, color = 'fleet-red', narrow = false }: TagProps) {
  const { background, text: textColor } = tagColorMap[color];

  return (
    <View
      style={[
        styles.tag,
        narrow && styles.tagNarrow,
        { backgroundColor: background, borderColor: `${background}88` },
      ]}
    >
      <Text style={[styles.text, { color: textColor }]} numberOfLines={1}>
        {text}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    alignSelf: 'flex-start',
    borderWidth: StyleSheet.hairlineWidth,
  },
  tagNarrow: {
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  text: {
    ...typography.overline,
    fontFamily: 'Norwester',
    fontSize: 10,
    letterSpacing: 0.6,
  },
});
