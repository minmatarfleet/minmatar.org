import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { Redirect } from 'expo-router';
import type { ReactNode } from 'react';
import { Text } from 'react-native-paper';

import { useAuth } from '@/src/auth/AuthContext';
import { colors } from '@/src/theme';
import { typography } from '@/src/theme/spacing';

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.fleetYellow} size="large" />
        <Text style={styles.loadingText}>Loading…</Text>
      </View>
    );
  }

  if (!user) {
    return <Redirect href="/" />;
  }

  return children;
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
    backgroundColor: colors.background,
  },
  loadingText: {
    ...typography.body,
    color: colors.muted,
  },
});
