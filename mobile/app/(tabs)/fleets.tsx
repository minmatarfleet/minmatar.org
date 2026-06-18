import { useMemo } from 'react';
import { FlatList, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { Text } from 'react-native-paper';
import { Screen } from '@/src/components/Screen';
import { FleetCard } from '@/src/components/FleetCard';
import { SectionLabel } from '@/src/components/SectionLabel';
import { getSortedFleets } from '@/src/data/mockFleets';
import type { FleetItem } from '@/src/types/fleets';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

type FleetListItem =
  | { key: string; type: 'section'; title: string }
  | { key: string; type: 'fleet'; fleet: FleetItem; highlighted: boolean };

function isActiveFleet(fleet: FleetItem): boolean {
  return fleet.status !== 'cancelled' && !!fleet.tracking && !fleet.tracking.end_time;
}

function buildFleetList(fleets: FleetItem[]): FleetListItem[] {
  const active = fleets.filter(isActiveFleet);
  const upcoming = fleets.filter((f) => !isActiveFleet(f) && f.status === 'pending');
  const history = fleets.filter((f) => !active.includes(f) && !upcoming.includes(f));

  const items: FleetListItem[] = [];

  if (active.length > 0) {
    items.push({ key: 'section-live', type: 'section', title: 'Live now' });
    active.forEach((fleet) => {
      items.push({ key: `fleet-${fleet.id}`, type: 'fleet', fleet, highlighted: true });
    });
  }

  if (upcoming.length > 0) {
    items.push({ key: 'section-upcoming', type: 'section', title: 'Upcoming' });
    upcoming.forEach((fleet) => {
      items.push({ key: `fleet-${fleet.id}`, type: 'fleet', fleet, highlighted: false });
    });
  }

  if (history.length > 0) {
    items.push({ key: 'section-history', type: 'section', title: 'Recent' });
    history.forEach((fleet) => {
      items.push({ key: `fleet-${fleet.id}`, type: 'fleet', fleet, highlighted: false });
    });
  }

  return items;
}

export default function FleetsScreen() {
  const router = useRouter();
  const items = useMemo(() => buildFleetList(getSortedFleets()), []);

  if (items.length === 0) {
    return (
      <Screen>
        <View style={styles.emptyWrap}>
          <Text style={styles.emptyTitle}>No fleets scheduled</Text>
          <Text style={styles.emptyBody}>Check back later for upcoming operations.</Text>
        </View>
      </Screen>
    );
  }

  return (
    <Screen padded={false}>
      <FlatList
        data={items}
        keyExtractor={(item) => item.key}
        contentContainerStyle={styles.list}
        renderItem={({ item }) => {
          if (item.type === 'section') {
            return <SectionLabel variant="section" title={item.title} />;
          }
          return (
            <FleetCard
              fleet={item.fleet}
              highlighted={item.highlighted}
              onPress={() => router.push(`/fleet/${item.fleet.id}`)}
            />
          );
        }}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xxxl,
  },
  emptyWrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xxxl,
    gap: spacing.sm,
  },
  emptyTitle: {
    ...typography.title,
    color: colors.highlight,
    fontSize: 16,
  },
  emptyBody: {
    ...typography.body,
    color: colors.muted,
    textAlign: 'center',
  },
});
