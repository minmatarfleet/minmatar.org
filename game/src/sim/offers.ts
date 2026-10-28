import {
  HIGH_FAMILIES,
  HULLS,
  type Card,
  type EvolutionId,
  type FamilyId,
  type Fit,
  type HullDef,
  type HullId,
  rankOf,
} from './types.ts'

export interface OfferState {
  tankForkShown: boolean
}

export function startingFit(hullId: HullId): Fit {
  const hull = HULLS[hullId]
  return {
    hull: hullId,
    families: [hull.starter],
    ranks: { [hull.starter]: 1 },
    prop: 'none',
    propOn: false,
    tank: 'none',
    tankRank: 0,
    utility: 'none',
    evolutions: [],
  }
}

export function highsUsed(fit: Fit): number {
  return fit.families.filter((family) => HIGH_FAMILIES.has(family)).length
}

export function midsUsed(fit: Fit): number {
  return (fit.prop === 'none' ? 0 : 1) + (fit.utility === 'none' ? 0 : 1)
}

export function lowsUsed(fit: Fit): number {
  if (fit.tank === 'none') return 0
  return 1 + fit.tankRank
}

export function canApply(fit: Fit, card: Card, hull: HullDef): boolean {
  switch (card.kind) {
    case 'family':
      return canAddFamily(fit, card.family, hull)
    case 'rank':
      return fit.families.includes(card.family) && rankOf(fit, card.family) < 4
    case 'prop':
      return fit.prop === 'none' && midsUsed(fit) < hull.mids
    case 'tank':
      if (fit.tank === 'none') return lowsUsed(fit) < hull.lows
      return fit.tank === card.tank && lowsUsed(fit) < hull.lows
    case 'utility':
      return fit.utility === 'none' && midsUsed(fit) < hull.mids
    case 'evolution':
      return evolutionReady(fit, card.evolution) && !fit.evolutions.includes(card.evolution)
    default: {
      const neverCard: never = card
      return neverCard
    }
  }
}

export function applyCard(fit: Fit, card: Card, hull: HullDef): boolean {
  if (!canApply(fit, card, hull)) return false
  switch (card.kind) {
    case 'family':
      fit.families.push(card.family)
      fit.ranks[card.family] = 1
      return true
    case 'rank':
      fit.ranks[card.family] = rankOf(fit, card.family) + 1
      return true
    case 'prop':
      fit.prop = card.prop
      fit.propOn = true
      return true
    case 'tank':
      if (fit.tank === 'none') fit.tank = card.tank
      else fit.tankRank += 1
      return true
    case 'utility':
      fit.utility = card.utility
      return true
    case 'evolution':
      fit.evolutions.push(card.evolution)
      return true
    default: {
      const neverCard: never = card
      return neverCard
    }
  }
}

export function buildOffer(fit: Fit, hull: HullDef, time: number, rng: () => number, state: OfferState): Card[] {
  if (fit.prop === 'none' && time < 150) {
    return fill([
      { kind: 'prop', prop: 'ab' },
      { kind: 'prop', prop: 'mwd' },
      pickWild(fit, hull, time, rng),
    ], fit, hull, time, rng)
  }
  if (fit.tank === 'none' && !state.tankForkShown && time >= 100) {
    state.tankForkShown = true
    return [
      { kind: 'tank', tank: 'shield' },
      { kind: 'tank', tank: 'armor' },
      { kind: 'tank', tank: 'buffer' },
    ]
  }
  const lesson = lessonCard(fit, hull, time, rng)
  const second = time >= 390 ? rankLean(fit, hull, rng) : pickWild(fit, hull, time, rng, true)
  const third = pickWild(fit, hull, time, rng)
  return fill([lesson, second, third], fit, hull, time, rng)
}

export function cardCopy(card: Card): { slot: string; title: string; detail: string } {
  switch (card.kind) {
    case 'family':
      return { slot: slotOfFamily(card.family), title: familyName(card.family), detail: familyDetail(card.family) }
    case 'rank':
      return { slot: slotOfFamily(card.family), title: `${familyName(card.family)} rank`, detail: 'The same family, harder.' }
    case 'prop':
      return card.prop === 'ab'
        ? { slot: 'Mid', title: 'Afterburner', detail: 'Slower, aligns harder, stays small. A scram does not cut it.' }
        : { slot: 'Mid', title: 'Microwarpdrive', detail: 'Fast and fat on signature. A scram shuts it off.' }
    case 'tank':
      return card.tank === 'shield'
        ? { slot: 'Low', title: 'Shield booster', detail: 'Repairs shield while you are being shot.' }
        : card.tank === 'armor'
          ? { slot: 'Low', title: 'Armor repairer', detail: 'Repairs armor while you are being shot.' }
          : { slot: 'Low', title: 'Buffer plate', detail: 'A larger shield. With an afterburner it can become Pocket.' }
    case 'utility':
      return card.utility === 'web'
        ? { slot: 'Mid', title: 'Stasis webifier', detail: 'Slows ships near you. With autocannons it becomes Hail.' }
        : { slot: 'Mid', title: 'Target painter', detail: 'Paints your target. With artillery it becomes Spike.' }
    case 'evolution':
      return evolutionCopy(card.evolution)
    default: {
      const neverCard: never = card
      return neverCard
    }
  }
}

export function suggestedHull(cause: string, current: HullId): HullId {
  if (cause === 'scram') return 'frigate'
  if (cause === 'pulse') return 'gun'
  if (cause === 'escorts' || cause === 'mother') return 'drone'
  if (current === 'frigate') return 'gun'
  if (current === 'gun') return 'drone'
  return 'frigate'
}

export function familyName(family: FamilyId): string {
  switch (family) {
    case 'autocannon':
      return 'Autocannons'
    case 'artillery':
      return 'Artillery'
    case 'missile':
      return 'Missiles'
    case 'drone':
      return 'Drones'
    case 'smartbomb':
      return 'Smartbomb'
    default: {
      const neverFamily: never = family
      return neverFamily
    }
  }
}

function canAddFamily(fit: Fit, family: FamilyId, hull: HullDef): boolean {
  if (fit.families.includes(family) || fit.families.length >= 3) return false
  if (family === 'drone') return hull.bay
  if (HIGH_FAMILIES.has(family) && highsUsed(fit) >= hull.highs) return false
  return true
}

function evolutionReady(fit: Fit, evolution: EvolutionId): boolean {
  switch (evolution) {
    case 'hail':
      return fit.families.includes('autocannon') && fit.utility === 'web'
    case 'spike':
      return fit.families.includes('artillery') && fit.utility === 'painter'
    case 'feedback':
      return fit.families.includes('drone') && fit.families.includes('smartbomb')
    case 'pocket':
      return fit.prop === 'ab' && fit.tank === 'buffer'
    default: {
      const neverEvolution: never = evolution
      return neverEvolution
    }
  }
}

function lessonCard(fit: Fit, hull: HullDef, time: number, rng: () => number): Card {
  if (time >= 330) {
    const rank = rankLean(fit, hull, rng)
    if (time < 390 || rank.kind !== 'family') return rank
  }
  const owned = fit.families.find((family) => rankOf(fit, family) < 4)
  if (owned && time >= 200) return { kind: 'rank', family: owned }
  return pickWild(fit, hull, time, rng, true)
}

function rankLean(fit: Fit, hull: HullDef, rng: () => number): Card {
  const owned = fit.families.filter((family) => rankOf(fit, family) < 4)
  if (owned.length > 0) return { kind: 'rank', family: owned[Math.floor(rng() * owned.length)] ?? owned[0]! }
  if (fit.tank !== 'none' && lowsUsed(fit) < hull.lows) return { kind: 'tank', tank: fit.tank }
  return pickWild(fit, hull, 400, rng, true)
}

function pickWild(fit: Fit, hull: HullDef, time: number, rng: () => number, preferRank = false): Card {
  const bag: Card[] = []
  const ready = (['hail', 'spike', 'feedback', 'pocket'] as const).filter((evolution) => evolutionReady(fit, evolution) && !fit.evolutions.includes(evolution))
  for (const evolution of ready) bag.push({ kind: 'evolution', evolution })
  if (fit.utility === 'none' && midsUsed(fit) < hull.mids) {
    if (fit.families.includes('autocannon')) bag.push({ kind: 'utility', utility: 'web' })
    if (fit.families.includes('artillery')) bag.push({ kind: 'utility', utility: 'painter' })
    if (!fit.families.includes('autocannon') && !fit.families.includes('artillery')) {
      bag.push({ kind: 'utility', utility: rng() < 0.5 ? 'web' : 'painter' })
    }
  }
  if (preferRank || rng() < 0.55) {
    for (const family of fit.families) {
      if (rankOf(fit, family) < 4) bag.push({ kind: 'rank', family })
    }
  }
  if (time < 390) {
    const families: FamilyId[] = ['autocannon', 'artillery', 'missile', 'drone', 'smartbomb']
    for (const family of families) {
      if (canAddFamily(fit, family, hull)) bag.push({ kind: 'family', family })
    }
  }
  if (fit.tank !== 'none' && lowsUsed(fit) < hull.lows) bag.push({ kind: 'tank', tank: fit.tank })
  if (bag.length === 0) return { kind: 'rank', family: fit.families[0] ?? hull.starter }
  return bag[Math.floor(rng() * bag.length)] ?? bag[0]!
}

function fill(cards: Card[], fit: Fit, hull: HullDef, time: number, rng: () => number): Card[] {
  const result: Card[] = []
  for (const card of cards) {
    if (!result.some((other) => sameCard(other, card)) && canApply(fit, card, hull)) result.push(card)
  }
  let guard = 0
  while (result.length < 3 && guard < 12) {
    guard += 1
    const extra = pickWild(fit, hull, time, rng)
    if (!result.some((other) => sameCard(other, extra)) && canApply(fit, extra, hull)) result.push(extra)
  }
  while (result.length < 3) {
    const family = fit.families.find((entry) => rankOf(fit, entry) < 4) ?? fit.families[0] ?? hull.starter
    const filler: Card = { kind: 'rank', family }
    if (canApply(fit, filler, hull) && !result.some((other) => sameCard(other, filler))) result.push(filler)
    else break
  }
  return result.slice(0, 3)
}

function sameCard(a: Card, b: Card): boolean {
  return JSON.stringify(a) === JSON.stringify(b)
}

function slotOfFamily(family: FamilyId): string {
  if (family === 'drone') return 'Bay'
  return 'High'
}

function familyDetail(family: FamilyId): string {
  switch (family) {
    case 'autocannon':
      return 'Fast short guns. They like a close orbit.'
    case 'artillery':
      return 'Slow, heavy, and poor into a small signature.'
    case 'missile':
      return 'They turn toward a target, then splash.'
    case 'drone':
      return 'A flight orbits you and picks its own targets.'
    case 'smartbomb':
      return 'A pulse around your hull. It warns, then it hits.'
    default: {
      const neverFamily: never = family
      return neverFamily
    }
  }
}

function evolutionCopy(evolution: EvolutionId): { slot: string; title: string; detail: string } {
  switch (evolution) {
    case 'hail':
      return { slot: 'High', title: 'Hail', detail: 'Autocannon hits slow what they strike.' }
    case 'spike':
      return { slot: 'High', title: 'Spike', detail: 'Painted targets take the full artillery shot.' }
    case 'feedback':
      return { slot: 'Bay', title: 'Feedback', detail: 'A drone kill throws a small pulse.' }
    case 'pocket':
      return { slot: 'Low', title: 'Pocket', detail: 'Signature stays at the afterburner value.' }
    default: {
      const neverEvolution: never = evolution
      return neverEvolution
    }
  }
}
