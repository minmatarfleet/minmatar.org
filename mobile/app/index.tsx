import { useEffect } from 'react';
import { ActivityIndicator, Alert, StyleSheet, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Redirect, useRouter } from 'expo-router';
import { Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAuth } from '@/src/auth/AuthContext';
import { FleetLogoSquare } from '@/src/components/FleetLogoSquare';
import { MinmatarButton } from '@/src/components/MinmatarButton';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export default function LandingScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user, isLoading, isAuthenticating, loginWithEve } = useAuth();

  useEffect(() => {
    if (user) {
      router.replace('/(tabs)/pulse');
    }
  }, [router, user]);

  if (isLoading) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator color={colors.fleetYellow} size="large" />
      </View>
    );
  }

  if (user) {
    return <Redirect href="/(tabs)/pulse" />;
  }

  return (
    <View style={styles.root}>
      <LinearGradient
        colors={['#1a0808', colors.background, '#0a0a14']}
        locations={[0, 0.55, 1]}
        style={StyleSheet.absoluteFill}
      />
      <View
        style={[
          styles.content,
          { paddingTop: insets.top + spacing.xxxl, paddingBottom: insets.bottom + spacing.xxxl },
        ]}
      >
        <View style={styles.hero}>
          <FleetLogoSquare size={88} />
          <Text style={styles.title}>Minmatar</Text>
          <Text style={styles.subtitle}>Alliance mobile</Text>
          <Text style={styles.tagline}>
            Pulse, fleets, and news — sign in with your EVE character to continue.
          </Text>
        </View>
        <View style={styles.actions}>
          <MinmatarButton
            label={isAuthenticating ? 'Opening EVE SSO…' : 'Log in with EVE Online'}
            fullWidth
            disabled={isAuthenticating}
            onPress={() => {
              void loginWithEve().catch((error: unknown) => {
                const message =
                  error instanceof Error ? error.message : 'Could not complete EVE login.';
                Alert.alert('Login failed', message);
              });
            }}
            style={styles.loginButton}
          />
          <Text style={styles.hint}>Secure login via EVE Single Sign-On</Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  loading: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
  },
  content: {
    flex: 1,
    paddingHorizontal: spacing.xxxl,
    justifyContent: 'space-between',
  },
  hero: { alignItems: 'center', gap: spacing.md },
  title: {
    ...typography.display,
    fontSize: 42,
    lineHeight: 46,
    color: colors.fleetYellow,
    marginTop: spacing.lg,
  },
  subtitle: {
    ...typography.overline,
    fontSize: 12,
    letterSpacing: 2.4,
    color: colors.faded,
  },
  tagline: {
    ...typography.body,
    color: colors.muted,
    textAlign: 'center',
    marginTop: spacing.lg,
    maxWidth: 300,
    lineHeight: 22,
  },
  actions: { gap: spacing.md, alignItems: 'center' },
  loginButton: { paddingVertical: 14 },
  hint: { ...typography.caption, color: colors.muted, textAlign: 'center' },
});
