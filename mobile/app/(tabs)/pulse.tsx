import { useCallback, useMemo } from 'react';
import { ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { isActiveFleet, isUpcomingFleet } from '@/src/api/mappers/fleets';
import { useAuth } from '@/src/auth/AuthContext';
import { PulseFleetRow } from '@/src/components/PulseFleetRow';
import { PulseSectionCard } from '@/src/components/PulseSectionCard';
import { Screen } from '@/src/components/Screen';
import { WarzonePanel } from '@/src/components/WarzonePanel';
import { useFleetsSchedule } from '@/src/hooks/useFleets';
import { useWarzoneBriefing } from '@/src/hooks/useWarzoneBriefing';
import type { FleetItem } from '@/src/types/fleets';
import { spacing } from '@/src/theme/spacing';

const MAX_UPCOMING = 3;

export default function PulseScreen() {
  const router = useRouter();
  const { token, isLinked } = useAuth();
  const { briefing: warzoneBriefing, loading: warzoneLoading } = useWarzoneBriefing();
  const { fleets, loading: fleetsLoading } = useFleetsSchedule(isLinked ? token : null);

  const liveFleets = useMemo(() => fleets.filter(isActiveFleet).slice(0, 1), [fleets]);
  const liveIds = useMemo(() => new Set(liveFleets.map((f) => f.id)), [liveFleets]);
  const upcomingFleets = useMemo(
    () =>
      fleets
        .filter((f) => !liveIds.has(f.id) && isUpcomingFleet(f))
        .sort((a, b) => a.start_time.getTime() - b.start_time.getTime())
        .slice(0, MAX_UPCOMING),
    [fleets, liveIds],
  );

  const hasFleetSection = liveFleets.length + upcomingFleets.length > 0;

  const fleetRow = useCallback(
    (fleet: FleetItem, variant: 'live' | 'upcoming', highlighted = false) => (
      <PulseFleetRow
        key={fleet.id}
        fleet={fleet}
        variant={variant}
        highlighted={highlighted}
        onPress={() => router.push(`/fleet/${fleet.id}`)}
      />
    ),
    [router],
  );

  const hasWarzone =
    !warzoneLoading &&
    (warzoneBriefing.amarrContested.length > 0 ||
      warzoneBriefing.minmatarContested.length > 0 ||
      warzoneBriefing.hotKills != null ||
      warzoneBriefing.changes24h.length > 0);

  return (
    <Screen padded={false}>
      <ScrollView contentContainerStyle={styles.scroll}>
        {!fleetsLoading && hasFleetSection ? (
          <PulseSectionCard
            title="Fleets"
            subtitle="What's forming up next"
            badge={liveFleets.length > 0 ? 'LIVE' : undefined}
            badgeLive={liveFleets.length > 0}
            footer={{ label: 'See all fleets →', onPress: () => router.push('/fleets') }}
          >
            {liveFleets.map((f) => fleetRow(f, 'live', true))}
            {upcomingFleets.map((f) => fleetRow(f, 'upcoming'))}
          </PulseSectionCard>
        ) : null}

        {hasWarzone ? <WarzonePanel briefing={warzoneBriefing} /> : null}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xxxl,
  },
});
