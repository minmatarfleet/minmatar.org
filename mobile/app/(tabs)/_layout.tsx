import { Platform, StyleSheet, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { RequireAuth } from '@/src/auth/RequireAuth';
import { TopBar } from '@/src/components/TopBar';
import { colors } from '@/src/theme';
import { spacing, typography } from '@/src/theme/spacing';

export default function TabLayout() {
  const insets = useSafeAreaInsets();

  return (
    <RequireAuth>
      <View style={styles.container}>
        <TopBar />
        <Tabs
          initialRouteName="pulse"
          screenOptions={{
            headerShown: false,
            tabBarActiveTintColor: colors.fleetYellow,
            tabBarInactiveTintColor: colors.muted,
            tabBarStyle: {
              backgroundColor: colors.black,
              borderTopColor: colors.border,
              borderTopWidth: 1,
              height: 56 + insets.bottom,
              paddingBottom: insets.bottom,
              paddingTop: spacing.sm,
            },
            tabBarLabelStyle: {
              ...typography.overline,
              fontSize: 10,
              marginTop: 2,
            },
            tabBarItemStyle: {
              paddingVertical: spacing.xs,
            },
          }}
        >
          <Tabs.Screen
            name="pulse"
            options={{
              title: 'Pulse',
              tabBarIcon: ({ color, focused }) => (
                <View style={styles.iconWrap}>
                  {focused && <View style={styles.activeIndicator} />}
                  <MaterialCommunityIcons name="pulse" color={color} size={22} />
                </View>
              ),
            }}
          />
          <Tabs.Screen
            name="news"
            options={{
              title: 'News',
              tabBarIcon: ({ color, focused }) => (
                <View style={styles.iconWrap}>
                  {focused && <View style={styles.activeIndicator} />}
                  <MaterialCommunityIcons name="newspaper-variant-outline" color={color} size={22} />
                </View>
              ),
            }}
          />
          <Tabs.Screen
            name="activity"
            options={{
              title: 'Activity',
              tabBarIcon: ({ color, focused }) => (
                <View style={styles.iconWrap}>
                  {focused && <View style={styles.activeIndicator} />}
                  <MaterialCommunityIcons name="chart-timeline-variant" color={color} size={22} />
                </View>
              ),
            }}
          />
        </Tabs>
      </View>
    </RequireAuth>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  iconWrap: {
    alignItems: 'center',
    justifyContent: 'center',
    height: 28,
  },
  activeIndicator: {
    position: 'absolute',
    top: Platform.OS === 'ios' ? -10 : -8,
    width: 20,
    height: 2,
    backgroundColor: colors.fleetRed,
  },
});
