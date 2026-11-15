/**
 * The four EVE damage types and the glyphs we draw for them. CCP does not
 * serve its damage-type icons through the Image Server, and our third-party
 * rules forbid shipping art extracted from the client, so these are our own:
 * EM a lightning bolt, thermal a flame, kinetic a shell, explosive a burst.
 * Paths sit in a 16 × 16 box so HTML icons and SVG charts share them.
 */
export const DAMAGE_TYPES = ['em', 'thermal', 'kinetic', 'explosive'] as const
export type DamageType = typeof DAMAGE_TYPES[number]

export const DAMAGE_GLYPHS: Record<DamageType, string> = {
    em: 'M9.5 0.5 L2.5 9 H7 L5.8 15.5 L13.5 6.2 H8.8 Z',
    thermal: 'M8 0.5 C9.2 3.4 12.8 5.6 12.8 10 A4.8 4.8 0 0 1 3.2 10 C3.2 7.4 4.6 5.8 5.8 4.4 C6 6.2 6.8 7.4 7.8 7.8 C7.4 5.6 7.4 3 8 0.5 Z',
    kinetic: 'M1 5.5 H8.5 C12 5.5 15 6.8 15 8 C15 9.2 12 10.5 8.5 10.5 H1 Z M3.5 5.5 V10.5',
    explosive: 'M8 0.5 L9.5 5.3 L14.6 3.6 L11.2 7.6 L15.5 10.4 L10.2 10.6 L10.6 15.5 L8 11.6 L5.4 15.5 L5.8 10.6 L0.5 10.4 L4.8 7.6 L1.4 3.6 L6.5 5.3 Z',
}
