export type HullId = 'frigate' | 'gun' | 'drone'

export type FamilyId = 'autocannon' | 'artillery' | 'missile' | 'drone' | 'smartbomb'

export type PropId = 'ab' | 'mwd'

export type TankId = 'shield' | 'armor' | 'buffer'

export type UtilityId = 'web' | 'painter'

export type EvolutionId = 'hail' | 'spike' | 'feedback' | 'pocket'

export type DeathCause = 'scram' | 'mother' | 'pulse' | 'escorts' | 'belt'

export type Card =
  | { kind: 'family'; family: FamilyId }
  | { kind: 'rank'; family: FamilyId }
  | { kind: 'prop'; prop: PropId }
  | { kind: 'tank'; tank: TankId }
  | { kind: 'utility'; utility: UtilityId }
  | { kind: 'evolution'; evolution: EvolutionId }

export interface Fit {
  hull: HullId
  families: FamilyId[]
  ranks: Partial<Record<FamilyId, number>>
  prop: PropId | 'none'
  propOn: boolean
  tank: TankId | 'none'
  tankRank: number
  utility: UtilityId | 'none'
  evolutions: EvolutionId[]
}

export interface HullDef {
  id: HullId
  name: string
  fantasy: string
  highs: number
  mids: number
  lows: number
  bay: boolean
  speed: number
  agility: number
  signature: number
  shield: number
  armor: number
  hull: number
  starter: FamilyId
}

export const HULLS: Record<HullId, HullDef> = {
  frigate: {
    id: 'frigate',
    name: 'Frigate',
    fantasy: 'Autocannons. Get close, stay small, orbit under their guns.',
    highs: 3,
    mids: 3,
    lows: 2,
    bay: false,
    speed: 620,
    agility: 2.4,
    signature: 42,
    shield: 280,
    armor: 220,
    hull: 210,
    starter: 'autocannon',
  },
  gun: {
    id: 'gun',
    name: 'Gun cruiser',
    fantasy: 'Artillery. Keep at range. Tiny things take an extra shot.',
    highs: 5,
    mids: 4,
    lows: 4,
    bay: false,
    speed: 310,
    agility: 1.15,
    signature: 130,
    shield: 620,
    armor: 740,
    hull: 560,
    starter: 'artillery',
  },
  drone: {
    id: 'drone',
    name: 'Drone cruiser',
    fantasy: 'A flight is already out. The bay does not spend a high slot.',
    highs: 3,
    mids: 4,
    lows: 4,
    bay: true,
    speed: 260,
    agility: 1.05,
    signature: 140,
    shield: 540,
    armor: 680,
    hull: 620,
    starter: 'drone',
  },
}

export const HIGH_FAMILIES: ReadonlySet<FamilyId> = new Set([ // pragma: allowlist secret
  'autocannon',
  'artillery',
  'missile',
  'smartbomb',
])

export function rankOf(fit: Fit, family: FamilyId): number {
  return fit.ranks[family] ?? 1
}
