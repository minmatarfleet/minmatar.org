import { ScrollView, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import Markdown from 'react-native-markdown-display';
import { Text } from 'react-native-paper';
import { Countdown } from '@/src/components/Countdown';
import { FleetTypeIcon } from '@/src/components/FleetTypeIcon';
import { MinmatarButton } from '@/src/components/MinmatarButton';
import { StatusPill } from '@/src/components/StatusPill';
import { getFleetById } from '@/src/data/mockFleets';
import type { FleetItem } from '@/src/types/fleets';
import { colors } from '@/src/theme';
import { markdownStyles } from '@/src/theme/markdown';
import { spacing, typography } from '@/src/theme/spacing';
import { getPlayerIcon } from '@/src/utils/eveImage';

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

export default function FleetDetailScreen() {
  const router = useRouter();
  const { fleet_id } = useLocalSearchParams<{ fleet_id: string }>();
  const fleet = getFleetById(Number(fleet_id));

  if (!fleet) {
    return (
      <View style={styles.notFound}>
        <Text style={styles.notFoundTitle}>Fleet not found</Text>
        <MinmatarButton label="Go back" onPress={() => router.back()} />
      </View>
    );
  }

  const [system, station] = fleet.location?.split(' - ') ?? [];
  const status = getStatus(fleet);
  const isUpcoming = status.variant === 'upcoming';

  const metaParts = [
    system,
    station,
    fleet.audience,
    fleet.members_count && fleet.members_count > 0 ? `${fleet.members_count} pilots` : null,
    fleet.fleet_commander_fleet_count ? `${fleet.fleet_commander_fleet_count} FC fleets` : null,
  ].filter(Boolean);

  return (
    <>
      <Stack.Screen options={{ title: fleet.fleet_commander_name, headerBackTitle: 'Fleets' }} />
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <Image
            source={{ uri: getPlayerIcon(fleet.fleet_commander_id, 512) }}
            style={styles.heroImage}
            contentFit="cover"
          />
          <LinearGradient
            colors={['transparent', colors.scrim, colors.background]}
            locations={[0.25, 0.65, 1]}
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
            <Markdown style={markdownStyles}>{fleet.objective}</Markdown>
          )}

          {fleet.description && fleet.description !== fleet.objective && (
            <Text style={styles.description}>{fleet.description}</Text>
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
      </ScrollView>
    </>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    paddingBottom: spacing.xxxl,
  },
  hero: {
    height: 200,
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
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  heroBottom: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
    bottom: spacing.lg,
    gap: 2,
  },
  fcName: {
    ...typography.titleLg,
    color: colors.highlight,
    fontSize: 22,
    lineHeight: 26,
  },
  corpName: {
    ...typography.caption,
    color: colors.faded,
  },
  body: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    gap: spacing.lg,
  },
  description: {
    ...typography.body,
    color: colors.muted,
  },
  metaLine: {
    ...typography.caption,
    color: colors.faded,
    lineHeight: 18,
  },
  schedule: {
    gap: spacing.xs,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  scheduleTime: {
    ...typography.caption,
    color: colors.fleetYellow,
  },
  notFound: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xxxl,
    gap: spacing.lg,
  },
  notFoundTitle: {
    ...typography.title,
    color: colors.highlight,
  },
});
