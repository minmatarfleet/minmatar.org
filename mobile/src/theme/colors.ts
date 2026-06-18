export const colors = {
  fleetYellow: '#f1d9a0',
  fleetRed: '#b53620',
  fleetRedMuted: 'rgba(181, 54, 32, 0.15)',
  allianceBlue: '#2051B5',
  militiaPurple: '#7342B2',
  green: '#198754',
  greenMuted: 'rgba(25, 135, 84, 0.15)',
  black: '#121212',
  background: '#000000',
  surface: '#191919',
  surfaceRaised: '#1f1f1f',
  highlight: '#FFFFFF',
  faded: 'rgba(255, 255, 255, 0.5)',
  muted: 'rgba(255, 255, 255, 0.35)',
  border: 'rgba(255, 255, 255, 0.06)',
  borderHover: 'rgba(255, 255, 255, 0.12)',
  scrim: 'rgba(0, 0, 0, 0.55)',
} as const;

export type TagColor = 'fleet-red' | 'alliance-blue' | 'militia-purple' | 'green' | 'fleet-yellow';

export const tagColorMap: Record<TagColor, { background: string; text: string }> = {
  'fleet-red': { background: colors.fleetRed, text: colors.highlight },
  'alliance-blue': { background: colors.allianceBlue, text: colors.highlight },
  'militia-purple': { background: colors.militiaPurple, text: colors.highlight },
  green: { background: colors.green, text: colors.highlight },
  'fleet-yellow': { background: colors.fleetYellow, text: colors.black },
};
