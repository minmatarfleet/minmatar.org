import { useEffect } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useRouter } from 'expo-router';

import { useAuth } from '@/src/auth/AuthContext';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export default function AuthCallbackScreen() {
  const router = useRouter();
  const { user } = useAuth();

  useEffect(() => {
    if (user) {
      router.replace('/(tabs)');
    }
  }, [router, user]);

  return (
    <View style={styles.wrap}>
      <ActivityIndicator color={colors.fleetYellow} />
      <Text style={styles.text}>Signing you in…</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.md,
    backgroundColor: colors.background,
  },
  text: {
    ...typography.body,
    color: colors.muted,
  },
});
