import { useEffect } from 'react';
import { StatusBar } from 'expo-status-bar';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import {
  Montserrat_400Regular,
  Montserrat_600SemiBold,
} from '@expo-google-fonts/montserrat';
import 'react-native-reanimated';

import { minmatarTheme } from '@/src/theme';
import { colors } from '@/src/theme/colors';
import { typography } from '@/src/theme/spacing';
import { AuthProvider } from '@/src/auth/AuthContext';

export { ErrorBoundary } from 'expo-router';

export const unstable_settings = {
  initialRouteName: '(tabs)',
};

SplashScreen.preventAutoHideAsync();

const stackScreenOptions = {
  headerStyle: { backgroundColor: colors.black },
  headerTintColor: colors.fleetYellow,
  headerTitleStyle: {
    ...typography.bodyStrong,
    color: colors.highlight,
  },
  headerShadowVisible: false,
  headerBackTitleVisible: false,
  contentStyle: { backgroundColor: colors.background },
};

export default function RootLayout() {
  const [loaded, error] = useFonts({
    Montserrat_400Regular,
    Montserrat_600SemiBold,
    Norwester: require('../assets/fonts/norwester.woff'),
  });

  useEffect(() => {
    if (error) throw error;
  }, [error]);

  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync();
    }
  }, [loaded]);

  if (!loaded) {
    return null;
  }

  return (
    <SafeAreaProvider>
      <AuthProvider>
        <PaperProvider theme={minmatarTheme}>
          <StatusBar style="light" />
          <Stack screenOptions={stackScreenOptions}>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="auth/callback" options={{ headerShown: false }} />
            <Stack.Screen name="post/[post_id]" />
            <Stack.Screen name="fleet/[fleet_id]" />
          </Stack>
        </PaperProvider>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
