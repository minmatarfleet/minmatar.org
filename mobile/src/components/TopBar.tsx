import { ActivityIndicator, Alert, Pressable, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Button, Text } from 'react-native-paper';
import { FleetLogoSquare } from '@/src/components/FleetLogoSquare';
import { HeaderEveTime } from '@/src/components/HeaderEveTime';
import { useAuth } from '@/src/auth/AuthContext';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export function TopBar() {
  const insets = useSafeAreaInsets();
  const { user, isAuthenticating, loginWithEve, logout } = useAuth();

  return (
    <View style={[styles.wrap, { paddingTop: insets.top }]}>
      <View style={styles.bar}>
        <FleetLogoSquare size={36} />
        <View style={styles.right}>
          <HeaderEveTime />
          {user ? (
            <Pressable onPress={logout} style={styles.userWrap} accessibilityRole="button">
              {user.avatar ? (
                <Image source={{ uri: user.avatar }} style={styles.avatar} contentFit="cover" />
              ) : null}
              <Text style={styles.userName} numberOfLines={1}>
                {user.characterName}
              </Text>
            </Pressable>
          ) : (
            <Button
              mode="contained"
              compact
              loading={isAuthenticating}
              disabled={isAuthenticating}
              onPress={() => {
                void loginWithEve().catch((error: unknown) => {
                  const message =
                    error instanceof Error ? error.message : 'Could not complete EVE login.';
                  Alert.alert('Login failed', message);
                });
              }}
              style={styles.loginButton}
              labelStyle={styles.loginLabel}
            >
              Log in
            </Button>
          )}
        </View>
      </View>
      {isAuthenticating ? (
        <View style={styles.loadingRow}>
          <ActivityIndicator size="small" color={colors.fleetYellow} />
          <Text style={styles.loadingText}>Opening EVE SSO…</Text>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.black,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    gap: spacing.md,
  },
  right: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: spacing.md,
  },
  loginButton: {
    backgroundColor: colors.fleetRed,
    borderRadius: 4,
  },
  loginLabel: {
    ...typography.overline,
    fontSize: 11,
    marginHorizontal: spacing.sm,
    marginVertical: 2,
  },
  userWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    maxWidth: 160,
  },
  avatar: {
    width: 28,
    height: 28,
    borderRadius: 4,
    backgroundColor: colors.surface,
  },
  userName: {
    ...typography.overline,
    color: colors.highlight,
    flexShrink: 1,
  },
  loadingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.sm,
    paddingBottom: spacing.sm,
  },
  loadingText: {
    ...typography.overline,
    color: colors.muted,
  },
});
