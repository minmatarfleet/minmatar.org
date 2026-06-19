import { useCallback, useEffect, useMemo, useState } from 'react';
import { Linking, ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { isActiveFleet, isUpcomingFleet } from '@/src/api/mappers/fleets';
import { useAuth } from '@/src/auth/AuthContext';
import { PulseFleetRow } from '@/src/components/PulseFleetRow';
import { PulsePostRow } from '@/src/components/PulsePostRow';
import { PulseSectionCard, PulseSubsection } from '@/src/components/PulseSectionCard';
import { Screen } from '@/src/components/Screen';
import { WarzonePanel } from '@/src/components/WarzonePanel';
import { fetchLatestPost } from '@/src/hooks/usePostsFeed';
import { fetchRecentAarFleet, useFleetsSchedule } from '@/src/hooks/useFleets';
import { useWarzoneBriefing } from '@/src/hooks/useWarzoneBriefing';
import type { FleetItem } from '@/src/types/fleets';
import type { PostListUI } from '@/src/types/posts';
import { spacing } from '@/src/theme/spacing';
import {
  getPulseFleetSectionTitle,
  isEveWeekend,
  isPulseTonightWindow,
  isSameEveDay,
  nowInEve,
} from '@/src/utils/eveTime';

function pickPulseFleets(fleets: FleetItem[]) {
  const now = nowInEve();
  const live = fleets.filter(isActiveFleet).slice(0, 1);
  const liveIds = new Set(live.map((f) => f.id));

  if (isPulseTonightWindow(now)) {
    const tonight = fleets
      .filter((f) => isUpcomingFleet(f) && isSameEveDay(f.start_time, now))
      .slice(0, 2);
    const tonightIds = new Set(tonight.map((f) => f.id));
    const weekend = fleets
      .filter(
        (f) =>
          isUpcomingFleet(f) &&
          isEveWeekend(f.start_time) &&
          !tonightIds.has(f.id) &&
          !liveIds.has(f.id),
      )
      .slice(0, 2);
    return {
      sectionTitle: getPulseFleetSectionTitle(now),
      live,
      tonight,
      weekend,
    };
  }

  const weekend = fleets
    .filter(
      (f) =>
        isUpcomingFleet(f) &&
        isEveWeekend(f.start_time) &&
        !liveIds.has(f.id),
    )
    .slice(0, 2);

  return {
    sectionTitle: getPulseFleetSectionTitle(now),
    live,
    tonight: [] as FleetItem[],
    weekend,
  };
}

export default function PulseScreen() {
  const router = useRouter();
  const { token, isLinked } = useAuth();
  const warzoneBriefing = useWarzoneBriefing();
  const { active, upcoming, loading: fleetsLoading } = useFleetsSchedule(isLinked ? token : null);
  const [headline, setHeadline] = useState<PostListUI | null>(null);
  const [aarFleet, setAarFleet] = useState<FleetItem | null>(null);

  const allFleets = useMemo(() => [...active, ...upcoming], [active, upcoming]);
  const pulseFleets = useMemo(() => pickPulseFleets(allFleets), [allFleets]);
  const liveFleets = pulseFleets.live ?? [];
  const tonightFleets = pulseFleets.tonight ?? [];
  const weekendFleets = pulseFleets.weekend ?? [];
  const fleetSectionTitle = pulseFleets.sectionTitle ?? 'Tonight';
  const hasFleetSection =
    liveFleets.length + tonightFleets.length + weekendFleets.length > 0;

  useEffect(() => {
    void fetchLatestPost().then(setHeadline).catch(() => setHeadline(null));
  }, []);

  useEffect(() => {
    if (!token || !isLinked) {
      setAarFleet(null);
      return;
    }
    void fetchRecentAarFleet(token).then(setAarFleet).catch(() => setAarFleet(null));
  }, [token, isLinked]);

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
    warzoneBriefing.amarrContested.length > 0 ||
    warzoneBriefing.minmatarContested.length > 0 ||
    warzoneBriefing.hotKills != null;

  const fleetSubtitle =
    fleetSectionTitle === 'Tonight'
      ? 'Ops scheduled for today'
      : 'Ops scheduled this weekend';

  return (
    <Screen padded={false}>
      <ScrollView contentContainerStyle={styles.scroll}>
        {isLinked && !fleetsLoading && hasFleetSection ? (
          <PulseSectionCard
            title={fleetSectionTitle}
            subtitle={fleetSubtitle}
            badge={liveFleets.length > 0 ? 'LIVE' : undefined}
            badgeLive={liveFleets.length > 0}
            footer={{ label: 'See all fleets →', onPress: () => router.push('/fleets') }}
          >
            {liveFleets.length > 0 ? (
              <PulseSubsection label="Live now">
                {liveFleets.map((f) => fleetRow(f, 'live', true))}
              </PulseSubsection>
            ) : null}
            {tonightFleets.length > 0 ? (
              <PulseSubsection label="Tonight">
                {tonightFleets.map((f) => fleetRow(f, 'upcoming'))}
              </PulseSubsection>
            ) : null}
            {weekendFleets.length > 0 ? (
              <PulseSubsection label="This weekend">
                {weekendFleets.map((f) => fleetRow(f, 'upcoming'))}
              </PulseSubsection>
            ) : null}
          </PulseSectionCard>
        ) : null}

        {hasWarzone ? <WarzonePanel briefing={warzoneBriefing} /> : null}

        {headline || aarFleet ? (
          <PulseSectionCard
            title="Minmatar"
            subtitle="Latest from the alliance"
            footer={{ label: 'See all news →', onPress: () => router.push('/(tabs)/news') }}
          >
            {headline ? (
              <PulsePostRow
                post={headline}
                onPress={() => router.push(`/post/${headline.post_id}`)}
              />
            ) : null}
            {aarFleet?.aar_link ? (
              <PulseFleetRow
                fleet={aarFleet}
                variant="aar"
                onPress={() => void Linking.openURL(aarFleet.aar_link!)}
              />
            ) : null}
          </PulseSectionCard>
        ) : null}
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
