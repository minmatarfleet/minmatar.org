import { useEffect, useState } from 'react';
import { StyleSheet } from 'react-native';
import { Text } from 'react-native-paper';
import { colors } from '@/src/theme';
import { typography } from '@/src/theme/spacing';

interface CountdownProps {
  date: Date;
}

function formatCountdown(target: Date): string {
  const diff = target.getTime() - Date.now();
  if (diff <= 0) return 'Starting now';

  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
  const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

  const parts: string[] = [];
  if (days > 0) parts.push(`${days}d`);
  if (hours > 0 || days > 0) parts.push(`${hours}h`);
  parts.push(`${minutes}m`);

  return parts.join(' ');
}

export function Countdown({ date }: CountdownProps) {
  const [text, setText] = useState(() => formatCountdown(date));

  useEffect(() => {
    const interval = setInterval(() => {
      setText(formatCountdown(date));
    }, 30_000);
    return () => clearInterval(interval);
  }, [date]);

  return <Text style={styles.countdown}>{text}</Text>;
}

const styles = StyleSheet.create({
  countdown: {
    ...typography.title,
    color: colors.fleetYellow,
    fontSize: 20,
    lineHeight: 24,
    fontVariant: ['tabular-nums'],
  },
});
