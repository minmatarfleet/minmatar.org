import { Pressable, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Text } from 'react-native-paper';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { getPlayerIcon } from '@/src/utils/eveImage';

interface AuthorRowProps {
  characterId: number;
  name: string;
  label?: string;
  large?: boolean;
}

export function AuthorRow({ characterId, name, label, large = false }: AuthorRowProps) {
  const size = large ? 48 : 32;

  return (
    <View style={styles.row}>
      <Image
        source={{ uri: getPlayerIcon(characterId, 128) }}
        style={{ width: size, height: size, borderWidth: 1, borderColor: colors.borderHover }}
        contentFit="cover"
      />
      <View style={styles.text}>
        {label && <Text style={styles.label}>{label}</Text>}
        <Text style={[styles.name, large && styles.nameLarge]}>{name}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  text: {
    gap: 2,
  },
  label: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 9,
  },
  name: {
    ...typography.bodyStrong,
    color: colors.fleetYellow,
    fontSize: 14,
  },
  nameLarge: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 16,
  },
});
