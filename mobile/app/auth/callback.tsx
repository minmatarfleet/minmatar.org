import { useEffect, useRef } from 'react';
import { ActivityIndicator, Alert, StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { useAuth } from '@/src/auth/AuthContext';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

function formatLoginError(code: string): string {
  switch (code) {
    case 'DENIED':
      return 'EVE login was cancelled or denied.';
    case 'NOT_CONFIGURED':
      return 'EVE SSO is not configured on the API server.';
    case 'LOGIN_FAILED':
      return 'Could not complete EVE login.';
    default:
      return code;
  }
}

export default function AuthCallbackScreen() {
  const router = useRouter();
  const { user, loginWithToken } = useAuth();
  const { token, error } = useLocalSearchParams<{ token?: string; error?: string }>();
  const handled = useRef(false);

  useEffect(() => {
    if (user) {
      router.replace('/(tabs)/pulse');
    }
  }, [router, user]);

  useEffect(() => {
    if (handled.current || user) {
      return;
    }

    if (error) {
      handled.current = true;
      Alert.alert('Login failed', formatLoginError(error), [
        { text: 'OK', onPress: () => router.replace('/') },
      ]);
      return;
    }

    if (!token || typeof token !== 'string') {
      return;
    }

    handled.current = true;
    void loginWithToken(token).catch((err: unknown) => {
      const message = err instanceof Error ? err.message : 'Could not complete EVE login.';
      Alert.alert('Login failed', message, [{ text: 'OK', onPress: () => router.replace('/') }]);
    });
  }, [error, loginWithToken, router, token, user]);

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
