import { Pressable, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import Markdown from 'react-native-markdown-display';
import { Text } from 'react-native-paper';
import type { FleetItem } from '@/src/types/fleets';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { getPlayerIcon } from '@/src/utils/eveImage';
import { Countdown } from './Countdown';
import { FleetTypeIcon } from './FleetTypeIcon';
import { MinmatarButton } from './MinmatarButton';
import { StatusPill } from './StatusPill';

interface FleetCardProps {
  fleet: FleetItem;
  highlighted?: boolean;
  onPress?: () => void;
}

function formatEveTime(date: Date): string {
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  });
}

function getStatus(fleet: FleetItem): { variant: 'active' | 'completed' | 'cancelled' | 'upcoming'; label: string } {
  if (fleet.status === 'cancelled') return { variant: 'cancelled', label: 'Cancelled' };
  if (fleet.tracking && !fleet.tracking.end_time) return { variant: 'active', label: 'Live now' };
  if (fleet.tracking?.end_time) return { variant: 'completed', label: 'Completed' };
  return { variant: 'upcoming', label: 'Scheduled' };
}

export function FleetCard({ fleet, highlighted = false, onPress }: FleetCardProps) {
  const [system, station] = fleet.location?.split(' - ') ?? [];
  const status = getStatus(fleet);
  const isUpcoming = status.variant === 'upcoming';

  const metaParts = [
    system,
    fleet.audience,
    fleet.members_count && fleet.members_count > 0 ? `${fleet.members_count} pilots` : null,
  ].filter(Boolean);

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        highlighted && styles.highlighted,
        pressed && styles.pressed,
      ]}
    >
      {highlighted && <View style={styles.highlightBar} />}

      <View style={styles.hero}>
        <Image
          source={{ uri: getPlayerIcon(fleet.fleet_commander_id, 512) }}
          style={styles.heroImage}
          contentFit="cover"
          transition={300}
        />
        <LinearGradient
          colors={['transparent', colors.scrim, colors.surface]}
          locations={[0, 0.5, 1]}
          style={styles.heroScrim}
        />
        <View style={styles.heroTop}>
          <FleetTypeIcon type={fleet.type} />
          <StatusPill variant={status.variant} label={status.label} />
        </View>
        <View style={styles.heroBottom}>
          <Text style={styles.fcName}>{fleet.fleet_commander_name}</Text>
          {fleet.corporation_name && (
            <Text style={styles.corpName}>{fleet.corporation_name}</Text>
          )}
        </View>
      </View>

      <View style={styles.body}>
        {fleet.objective && (
          <Markdown
            style={{
              body: { ...typography.body, color: colors.faded, marginBottom: 0 },
              strong: { color: colors.highlight, fontFamily: 'Montserrat_600SemiBold' },
            }}
          >
            {fleet.objective}
          </Markdown>
        )}

        {metaParts.length > 0 && (
          <Text style={styles.metaLine}>{metaParts.join('  ·  ')}</Text>
        )}

        {isUpcoming && (
          <View style={styles.schedule}>
            <Text style={styles.scheduleTime}>{formatEveTime(fleet.start_time)} UTC</Text>
            <Countdown date={fleet.start_time} />
          </View>
        )}

        {isUpcoming && (
          <MinmatarButton label="Volunteer" variant="success" fullWidth onPress={() => {}} />
        )}
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pressed: {
    opacity: 0.94,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.lg,
    overflow: 'hidden',
  },
  highlighted: {
    borderColor: colors.fleetRed,
    backgroundColor: colors.surfaceRaised,
  },
  highlightBar: {
    height: 3,
    backgroundColor: colors.fleetRed,
  },
  hero: {
    height: 132,
    position: 'relative',
  },
  heroImage: {
    ...StyleSheet.absoluteFillObject,
  },
  heroScrim: {
    ...StyleSheet.absoluteFillObject,
  },
  heroTop: {
    position: 'absolute',
    top: spacing.md,
    left: spacing.md,
    right: spacing.md,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  heroBottom: {
    position: 'absolute',
    left: spacing.md,
    right: spacing.md,
    bottom: spacing.md,
    gap: 2,
  },
  fcName: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 18,
    lineHeight: 22,
  },
  corpName: {
    ...typography.caption,
    color: colors.faded,
    fontSize: 11,
  },
  body: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  metaLine: {
    ...typography.caption,
    color: colors.muted,
  },
  schedule: {
    gap: spacing.xs,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  scheduleTime: {
    ...typography.caption,
    color: colors.fleetYellow,
    fontSize: 11,
  },
});
