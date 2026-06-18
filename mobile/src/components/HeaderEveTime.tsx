import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { colors } from '@/src/theme';
import { typography } from '@/src/theme/spacing';

function formatEveTime(date: Date): string {
  const hours = date.getUTCHours().toString().padStart(2, '0');
  const minutes = date.getUTCMinutes().toString().padStart(2, '0');
  return `${hours}:${minutes}`;
}

export function HeaderEveTime() {
  const [eveTime, setEveTime] = useState(() => formatEveTime(new Date()));

  useEffect(() => {
    const interval = setInterval(() => setEveTime(formatEveTime(new Date())), 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>EVE</Text>
      <Text style={styles.time}>{eveTime}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignItems: 'flex-end',
    marginRight: 0,
  },
  label: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 8,
  },
  time: {
    ...typography.bodyStrong,
    color: colors.faded,
    fontSize: 13,
    fontVariant: ['tabular-nums'],
  },
});
