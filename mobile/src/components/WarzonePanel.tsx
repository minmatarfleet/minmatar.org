import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';

import { PulseSectionCard, PulseSubsection } from '@/src/components/PulseSectionCard';
import { WarzoneHotRow } from '@/src/components/WarzoneHotRow';
import type { WarzoneBriefing } from '@/src/types/warzone';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

interface WarzonePanelProps {
  briefing: WarzoneBriefing;
}

export function WarzonePanel({ briefing }: WarzonePanelProps) {
  const { amarrContested, minmatarContested, hotKills } = briefing;
  const hasContent =
    amarrContested.length + minmatarContested.length + (hotKills ? 1 : 0) > 0;

  if (!hasContent) return null;

  return (
    <PulseSectionCard
      title="Warzone"
      subtitle="Contested %, 24h change, and kills per system"
      badge="24H"
    >
      {hotKills ? (
        <View style={styles.hotBlock}>
          <Text style={styles.hotLabel}>Most kills</Text>
          <WarzoneHotRow system={hotKills} variant="featured" />
        </View>
      ) : null}

      {amarrContested.length > 0 ? (
        <PulseSubsection label="Amarr contested">
          {amarrContested.map((system) => (
            <WarzoneHotRow key={system.system_id} system={system} />
          ))}
        </PulseSubsection>
      ) : null}

      {minmatarContested.length > 0 ? (
        <PulseSubsection label="Minmatar contested">
          {minmatarContested.map((system) => (
            <WarzoneHotRow key={system.system_id} system={system} />
          ))}
        </PulseSubsection>
      ) : null}
    </PulseSectionCard>
  );
}

const styles = StyleSheet.create({
  hotBlock: {
    marginBottom: spacing.sm,
  },
  hotLabel: {
    ...typography.overline,
    color: colors.fleetRed,
    fontSize: 10,
    letterSpacing: 1,
    marginBottom: spacing.sm,
  },
});
