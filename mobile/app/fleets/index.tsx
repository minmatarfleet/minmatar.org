import { useMemo } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { Stack, useRouter } from 'expo-router';
import { Text } from 'react-native-paper';

import { useAuth } from '@/src/auth/AuthContext';
import { isActiveFleet, isUpcomingFleet } from '@/src/api/mappers/fleets';
import { RequireAuth } from '@/src/auth/RequireAuth';
import { FleetCard } from '@/src/components/FleetCard';
import { LinkAccountPrompt } from '@/src/components/LinkAccountPrompt';
import { Screen } from '@/src/components/Screen';
import { SectionLabel } from '@/src/components/SectionLabel';
import { useFleetsSchedule } from '@/src/hooks/useFleets';
import type { FleetItem } from '@/src/types/fleets';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

type FleetListItem =
  | { key: string; type: 'section'; title: string }
  | { key: string; type: 'fleet'; fleet: FleetItem; highlighted: boolean };

function buildFleetList(fleets: FleetItem[]): FleetListItem[] {
  const active = fleets.filter(isActiveFleet);
  const upcoming = fleets.filter(isUpcomingFleet);
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

function FleetsContent() {
  const router = useRouter();
  const { token } = useAuth();
  const { fleets, loading, error, reload } = useFleetsSchedule(token);
  const items = useMemo(() => buildFleetList(fleets), [fleets]);

  if (loading && items.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.fleetYellow} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (items.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.emptyTitle}>No fleets scheduled</Text>
        <Text style={styles.emptyBody}>Check back later for upcoming operations.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={items}
      keyExtractor={(item) => item.key}
      contentContainerStyle={styles.list}
      refreshControl={
        <RefreshControl
          refreshing={loading}
          onRefresh={() => void reload()}
          tintColor={colors.fleetYellow}
          colors={[colors.fleetRed]}
        />
      }
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
  );
}

export default function FleetsScreen() {
  const { isLinked } = useAuth();

  return (
    <RequireAuth>
      <Stack.Screen options={{ title: 'Fleets', headerBackTitle: 'Pulse' }} />
      <Screen padded={false}>
        {isLinked ? (
          <FleetsContent />
        ) : (
          <View style={styles.promptWrap}>
            <LinkAccountPrompt />
          </View>
        )}
      </Screen>
    </RequireAuth>
  );
}

const styles = StyleSheet.create({
  list: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xxxl,
  },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xxxl,
    gap: spacing.sm,
  },
  promptWrap: {
    flex: 1,
    justifyContent: 'center',
    padding: spacing.lg,
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
  error: {
    ...typography.body,
    color: colors.fleetRed,
    textAlign: 'center',
  },
});
