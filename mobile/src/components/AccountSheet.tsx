import { useState } from 'react';
import { Alert, Linking, Pressable, StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Text } from 'react-native-paper';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useAuth } from '@/src/auth/AuthContext';
import { BottomSheet } from '@/src/components/BottomSheet';
import { MinmatarButton } from '@/src/components/MinmatarButton';
import { MY_MINMATAR_URL } from '@/src/config/env';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';
import { getPlayerIcon } from '@/src/utils/eveImage';

interface AccountAvatarButtonProps {
  size?: number;
}

export function AccountAvatarButton({ size = 32 }: AccountAvatarButtonProps) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  if (!user) return null;

  const avatarUri = user.avatar ?? getPlayerIcon(user.characterId, 64);

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        style={({ pressed }) => [styles.avatarBtn, pressed && styles.pressed]}
        accessibilityRole="button"
        accessibilityLabel="Account menu"
      >
        <Image source={{ uri: avatarUri }} style={{ width: size, height: size, borderRadius: 4 }} contentFit="cover" />
      </Pressable>
      <AccountSheet visible={open} onClose={() => setOpen(false)} />
    </>
  );
}

interface AccountSheetProps {
  visible: boolean;
  onClose: () => void;
}

function AccountSheet({ visible, onClose }: AccountSheetProps) {
  const insets = useSafeAreaInsets();
  const { user, isLinked, logout } = useAuth();

  if (!user) return null;

  const avatarUri = user.avatar ?? getPlayerIcon(user.characterId, 128);

  const handleLogout = () => {
    Alert.alert('Log out?', 'You will need to sign in again with EVE SSO.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Log out',
        style: 'destructive',
        onPress: () => {
          onClose();
          void logout();
        },
      },
    ]);
  };

  return (
    <BottomSheet
      visible={visible}
      onClose={onClose}
      scrimAccessibilityLabel="Close account menu"
      sheetStyle={{
        borderTopWidth: 3,
        borderTopColor: colors.fleetRed,
        paddingBottom: Math.max(insets.bottom, spacing.lg),
      }}
    >
      <View style={styles.sheetHeader}>
            <Text style={styles.sheetTitle}>Account</Text>
            <Pressable onPress={onClose} hitSlop={12} style={styles.closeBtn}>
              <MaterialCommunityIcons name="close" size={22} color={colors.faded} />
            </Pressable>
          </View>

          <View style={styles.profile}>
            <Image source={{ uri: avatarUri }} style={styles.profileAvatar} contentFit="cover" />
            <Text style={styles.characterName}>{user.characterName}</Text>
            {user.username ? <Text style={styles.username}>@{user.username}</Text> : null}
          </View>

          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>my.minmatar.org</Text>
            <View style={[styles.statusBadge, isLinked ? styles.statusLinked : styles.statusUnlinked]}>
              <Text style={[styles.statusText, isLinked ? styles.statusTextLinked : styles.statusTextUnlinked]}>
                {isLinked ? 'Linked' : 'Not linked'}
              </Text>
            </View>
          </View>

          {!isLinked ? (
            <Text style={styles.linkHint}>
              Link this character on my.minmatar.org to see fleet schedules and ops.
            </Text>
          ) : null}

          <View style={styles.actions}>
            {!isLinked ? (
              <MinmatarButton
                label="Open my.minmatar.org"
                variant="secondary"
                fullWidth
                onPress={() => void Linking.openURL(MY_MINMATAR_URL)}
              />
            ) : null}
            <MinmatarButton label="Log out" variant="secondary" fullWidth onPress={handleLogout} />
          </View>
    </BottomSheet>
  );
}

const styles = StyleSheet.create({
  avatarBtn: {
    borderRadius: 4,
    overflow: 'hidden',
    backgroundColor: colors.surface,
  },
  pressed: {
    opacity: 0.85,
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  sheetTitle: {
    ...typography.overline,
    color: colors.muted,
    fontSize: 10,
  },
  closeBtn: {
    padding: spacing.xs,
  },
  profile: {
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    paddingBottom: spacing.lg,
    gap: spacing.sm,
  },
  profileAvatar: {
    width: 72,
    height: 72,
    borderRadius: 4,
    backgroundColor: colors.surfaceRaised,
  },
  characterName: {
    ...typography.bodyStrong,
    color: colors.highlight,
    fontSize: 16,
    textAlign: 'center',
  },
  username: {
    ...typography.caption,
    color: colors.muted,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
    backgroundColor: colors.surfaceRaised,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  statusLabel: {
    ...typography.caption,
    color: colors.faded,
  },
  statusBadge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: 4,
  },
  statusLinked: {
    backgroundColor: colors.greenMuted,
  },
  statusUnlinked: {
    backgroundColor: colors.fleetRedMuted,
  },
  statusText: {
    ...typography.overline,
    fontSize: 9,
  },
  statusTextLinked: {
    color: colors.green,
  },
  statusTextUnlinked: {
    color: colors.fleetYellow,
  },
  linkHint: {
    ...typography.caption,
    color: colors.muted,
    textAlign: 'center',
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    lineHeight: 18,
  },
  actions: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    gap: spacing.sm,
  },
});
