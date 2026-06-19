import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Text } from 'react-native-paper';

import { Tag } from '@/src/components/Tag';
import type { WarzoneSystemHot } from '@/src/types/warzone';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { getFrontlinesCover, getTypeRender, getWarzoneCardCover } from '@/src/utils/eveImage';

type RowVariant = 'default' | 'featured';

interface WarzoneHotRowProps {
  system: WarzoneSystemHot;
  variant?: RowVariant;
}

function formatContestedDelta(delta: number): string {
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${delta}%`;
}

function WarzonePercentThumb({
  system,
  featured,
}: {
  system: WarzoneSystemHot;
  featured: boolean;
}) {
  const systemArt = getTypeRender(system.sun_type_id, 256);
  const [coverUri, setCoverUri] = useState(systemArt);
  const isAmarr = system.front === 'amarr';

  return (
    <View style={styles.thumb}>
      <Image
        source={{ uri: coverUri }}
        style={styles.thumbImage}
        contentFit="cover"
        transition={300}
        onError={() => setCoverUri(getWarzoneCardCover())}
      />
      {featured ? (
        <Image
          source={{ uri: getFrontlinesCover() }}
          style={[styles.thumbImage, styles.featuredOverlay]}
          contentFit="cover"
          transition={300}
        />
      ) : null}
      <LinearGradient
        colors={['rgba(0, 0, 0, 0.15)', 'rgba(0, 0, 0, 0.55)', 'rgba(0, 0, 0, 0.92)']}
        locations={[0, 0.5, 1]}
        style={styles.thumbScrim}
      />
      <LinearGradient
        colors={
          isAmarr
            ? ['rgba(241, 217, 160, 0.35)', 'transparent', 'rgba(0, 0, 0, 0.4)']
            : ['rgba(181, 54, 32, 0.4)', 'transparent', 'rgba(0, 0, 0, 0.45)']
        }
        locations={[0, 0.45, 1]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.thumbScrim}
      />
      <View style={styles.thumbContent}>
        <Text style={styles.percent}>{system.contested_percent}%</Text>
        <Text style={styles.thumbLabel}>contested %</Text>
      </View>
    </View>
  );
}

export function WarzoneHotRow({ system, variant = 'default' }: WarzoneHotRowProps) {
  const heating = system.delta_24h >= 0;
  const featured = variant === 'featured';
  const frontLabel = system.front === 'amarr' ? 'Amarr front' : 'Minmatar front';

  return (
    <View style={[styles.card, featured && styles.featured]}>
      <WarzonePercentThumb system={system} featured={featured} />
      <View style={styles.cardBody}>
        <View style={styles.topRow}>
          <Text style={styles.date}>{frontLabel}</Text>
          {featured ? <Tag text="Hot" color="fleet-red" narrow /> : null}
        </View>
        <Text style={styles.title}>{system.system_name}</Text>
        <View style={styles.stats}>
          <View style={styles.stat}>
            <Text style={styles.statLabel}>Contested</Text>
            <Text style={styles.statValue}>{system.contested_percent}%</Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statLabel}>24h Δ</Text>
            <Text style={[styles.statValue, heating ? styles.deltaUp : styles.deltaDown]}>
              {formatContestedDelta(system.delta_24h)}
            </Text>
          </View>
          <View style={styles.stat}>
            <Text style={styles.statLabel}>Kills</Text>
            <Text style={styles.statValue}>{system.kills_24h}</Text>
          </View>
        </View>
        <View style={styles.barTrack}>
          <View
            style={[
              styles.barFill,
              {
                width: `${Math.min(system.contested_percent, 100)}%`,
                backgroundColor: system.front === 'amarr' ? colors.fleetYellow : colors.fleetRed,
              },
            ]}
          />
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
    overflow: 'hidden',
  },
  featured: {
    borderColor: colors.borderHover,
    marginBottom: spacing.md,
  },
  thumb: {
    width: 108,
    height: 108,
    position: 'relative',
    overflow: 'hidden',
    backgroundColor: colors.black,
  },
  thumbImage: {
    ...StyleSheet.absoluteFillObject,
  },
  featuredOverlay: {
    opacity: 0.45,
  },
  thumbScrim: {
    ...StyleSheet.absoluteFillObject,
  },
  thumbContent: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'flex-end',
    paddingBottom: spacing.sm,
    gap: 2,
  },
  percent: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 22,
    lineHeight: 24,
    textShadowColor: 'rgba(0, 0, 0, 0.85)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 4,
  },
  thumbLabel: {
    ...typography.overline,
    color: colors.fleetYellow,
    fontSize: 8,
    textShadowColor: 'rgba(0, 0, 0, 0.85)',
    textShadowOffset: { width: 0, height: 1 },
    textShadowRadius: 3,
  },
  cardBody: {
    flex: 1,
    padding: spacing.md,
    gap: spacing.sm,
    justifyContent: 'center',
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  date: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 9,
  },
  title: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 15,
    lineHeight: 19,
  },
  stats: {
    flexDirection: 'row',
    gap: spacing.md,
    flexWrap: 'wrap',
  },
  stat: {
    gap: 1,
    minWidth: 52,
  },
  statLabel: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 8,
  },
  statValue: {
    ...typography.caption,
    color: colors.highlight,
    fontSize: 12,
    fontWeight: '600',
  },
  deltaUp: {
    color: colors.green,
  },
  deltaDown: {
    color: colors.fleetRed,
  },
  barTrack: {
    height: 3,
    backgroundColor: colors.surfaceRaised,
    borderRadius: 2,
    overflow: 'hidden',
    marginTop: spacing.xs,
  },
  barFill: {
    height: '100%',
    borderRadius: 2,
  },
});
