export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
} as const;

export const radii = {
  none: 0,
  sm: 2,
  md: 4,
} as const;

export const typography = {
  overline: {
    fontFamily: 'Montserrat_600SemiBold',
    fontSize: 10,
    letterSpacing: 1.2,
    textTransform: 'uppercase' as const,
  },
  caption: {
    fontFamily: 'Montserrat_400Regular',
    fontSize: 12,
    lineHeight: 16,
  },
  body: {
    fontFamily: 'Montserrat_400Regular',
    fontSize: 14,
    lineHeight: 20,
  },
  bodyStrong: {
    fontFamily: 'Montserrat_600SemiBold',
    fontSize: 14,
    lineHeight: 20,
  },
  title: {
    fontFamily: 'Norwester',
    fontSize: 18,
    lineHeight: 22,
    textTransform: 'uppercase' as const,
  },
  titleLg: {
    fontFamily: 'Norwester',
    fontSize: 22,
    lineHeight: 26,
    textTransform: 'uppercase' as const,
  },
  display: {
    fontFamily: 'Norwester',
    fontSize: 26,
    lineHeight: 30,
    textTransform: 'uppercase' as const,
  },
} as const;
