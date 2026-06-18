import { MD3DarkTheme, configureFonts } from 'react-native-paper';
import type { MD3Theme } from 'react-native-paper';
import { colors } from './colors';

const fontConfig = {
  fontFamily: 'Montserrat_400Regular',
};

const headingFontConfig = {
  fontFamily: 'Norwester',
};

export const minmatarTheme: MD3Theme = {
  ...MD3DarkTheme,
  roundness: 0,
  colors: {
    ...MD3DarkTheme.colors,
    primary: colors.fleetRed,
    onPrimary: colors.fleetYellow,
    primaryContainer: colors.fleetRed,
    onPrimaryContainer: colors.fleetYellow,
    secondary: colors.allianceBlue,
    onSecondary: colors.highlight,
    background: colors.background,
    onBackground: colors.fleetYellow,
    surface: colors.surface,
    onSurface: colors.fleetYellow,
    surfaceVariant: colors.surface,
    onSurfaceVariant: colors.faded,
    outline: colors.border,
    elevation: {
      level0: 'transparent',
      level1: colors.surface,
      level2: colors.surface,
      level3: colors.surface,
      level4: colors.surface,
      level5: colors.surface,
    },
  },
  fonts: configureFonts({
    config: {
      ...fontConfig,
      displayLarge: headingFontConfig,
      displayMedium: headingFontConfig,
      displaySmall: headingFontConfig,
      headlineLarge: headingFontConfig,
      headlineMedium: headingFontConfig,
      headlineSmall: headingFontConfig,
      titleLarge: headingFontConfig,
      titleMedium: { ...fontConfig, fontFamily: 'Montserrat_600SemiBold' },
      titleSmall: { ...fontConfig, fontFamily: 'Montserrat_600SemiBold' },
      bodyLarge: fontConfig,
      bodyMedium: fontConfig,
      bodySmall: fontConfig,
      labelLarge: { ...fontConfig, fontFamily: 'Montserrat_600SemiBold' },
      labelMedium: fontConfig,
      labelSmall: fontConfig,
    },
  }),
};

export { colors } from './colors';
export { spacing, typography, radii } from './spacing';
