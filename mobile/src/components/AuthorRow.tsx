import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { Text } from 'react-native-paper';
import { FleetLogoSquare } from '@/src/components/FleetLogoSquare';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { getPlayerIcon } from '@/src/utils/eveImage';

interface AuthorRowProps {
  characterId: number;
  name: string;
  label?: string;
  large?: boolean;
  compact?: boolean;
}

export function AuthorRow({ characterId, name, label, large = false, compact = false }: AuthorRowProps) {
  const size = large ? 48 : compact ? 20 : 32;

  return (
    <View style={styles.row}>
      {characterId > 0 ? (
        <Image
          source={{ uri: getPlayerIcon(characterId, 128) }}
          style={[
            styles.avatar,
            { width: size, height: size },
            compact && styles.avatarCompact,
          ]}
          contentFit="cover"
        />
      ) : (
        <FleetLogoSquare size={size} />
      )}
      <View style={styles.text}>
        {label ? <Text style={styles.label}>{label}</Text> : null}
        <Text style={[styles.name, large && styles.nameLarge, compact && styles.nameCompact]}>{name}</Text>
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
  avatar: {
    borderWidth: 1,
    borderColor: colors.borderHover,
  },
  avatarCompact: {
    borderWidth: 1,
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
  nameCompact: {
    ...typography.caption,
    fontSize: 11,
  },
});
