import { stepHelm, type HelmOrder } from './helm.ts'
import { applyCard, buildOffer, cardCopy, startingFit, type OfferState } from './offers.ts'
import {
  HULLS,
  rankOf,
  type Card,
  type DeathCause,
  type FamilyId,
  type Fit,
  type HullId,
} from './types.ts'

export const ARENA_RADIUS = 120_000
export const SCRAM_RANGE = 8_000
export const TICK = 1 / 30

export type ShipRole =
  | 'player'
  | 'trash'
  | 'burn'
  | 'mother'
  | 'mother-splinter'
  | 'bomber'
  | 'controller'
  | 'escort'
  | 'drone'
  | 'dummy'

export type ShipKind = 'player' | 'splinter' | 'frigate' | 'cruiser' | 'battlecruiser' | 'logi' | 'drone'

export interface Ship {
  id: number
  kind: ShipKind
  team: 'player' | 'hostile'
  role: ShipRole
  name: string
  x: number
  y: number
  vx: number
  vy: number
  heading: number
  radius: number
  signature: number
  sigBase: number
  shield: number
  shieldMax: number
  armor: number
  armorMax: number
  hull: number
  hullMax: number
  speed: number
  agility: number
  alive: boolean
  scramRange: number
  webRange: number
  paintRange: number
  gunDamage: number
  gunInterval: number
  gunRange: number
  gunCd: number
  pulseInterval: number
  pulseRadius: number
  pulseDamage: number
  pulseCd: number
  pulseTelegraph: number
  order: HelmOrder
  slow: number
  hit: number
  boss: boolean
  heal: number
}

export interface Shot {
  x: number
  y: number
  vx: number
  vy: number
  heading: number
  speed: number
  damage: number
  life: number
  team: 'player' | 'hostile'
  family: FamilyId | 'npc'
  homing: boolean
  targetId: number
  splash: number
}

export interface Boom {
  x: number
  y: number
  age: number
  radius: number
}

export interface Banner {
  text: string
  age: number
}

export interface World {
  mode: 'belt' | 'sandbox'
  offers: boolean
  seed: number
  rng: () => number
  time: number
  nextId: number
  ships: Ship[]
  shots: Shot[]
  booms: Boom[]
  fit: Fit
  offerState: OfferState
  selectedId: number
  paused: boolean
  pending: Card[] | null
  xp: number
  level: number
  kills: number
  firstKillTime: number
  quietUntil: number
  trashCd: number
  spawned: { burn: boolean; mother: boolean; bomber: boolean; controller: boolean }
  controllerAge: number
  outcome: 'play' | 'dead' | 'clear'
  cause: DeathCause | null
  banner: Banner | null
  inPulse: boolean
  pulseDepth: number
  hurtAgo: number
  speedOverride: number
  damageScale: number
  escortKind: 'web' | 'painter'
  playerMotion: { speed: number; signature: number; agility: number; scrammed: boolean; webbed: boolean }
}

export function mulberry32(seed: number): () => number {
  let value = seed >>> 0
  return () => {
    value = (value + 0x6d2b79f5) | 0
    let t = Math.imul(value ^ (value >>> 15), 1 | value)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function bomberEscort(seed: number): 'web' | 'painter' {
  return seed % 2 === 0 ? 'web' : 'painter'
}

export function createWorld(hull: HullId, seed = 1, options?: { mode?: 'belt' | 'sandbox'; offers?: boolean }): World {
  const world: World = {
    mode: options?.mode ?? 'belt',
    offers: options?.offers ?? true,
    seed,
    rng: mulberry32(seed),
    time: 0,
    nextId: 1,
    ships: [],
    shots: [],
    booms: [],
    fit: startingFit(hull),
    offerState: { tankForkShown: false },
    selectedId: 0,
    paused: false,
    pending: null,
    xp: 0,
    level: 1,
    kills: 0,
    firstKillTime: -1,
    quietUntil: 0,
    trashCd: 0.4,
    spawned: { burn: false, mother: false, bomber: false, controller: false },
    controllerAge: 0,
    outcome: 'play',
    cause: null,
    banner: null,
    inPulse: false,
    pulseDepth: 0,
    hurtAgo: 10,
    speedOverride: 0,
    damageScale: 1,
    escortKind: bomberEscort(seed),
    playerMotion: { speed: 0, signature: 0, agility: 0, scrammed: false, webbed: false },
  }
  const player = makeShip(world, {
    kind: 'player',
    team: 'player',
    role: 'player',
    name: HULLS[hull].name,
    shield: HULLS[hull].shield,
    armor: HULLS[hull].armor,
    hull: HULLS[hull].hull,
    speed: HULLS[hull].speed,
    agility: HULLS[hull].agility,
    signature: HULLS[hull].signature,
    radius: 80,
  })
  player.order = { type: 'manual', x: 0, y: 0, targetId: 0, range: 8_000, sign: 0 }
  if (world.mode === 'belt') {
    for (let i = 0; i < 4; i += 1) spawnSplinter(world, 2_800 + world.rng() * 3_200)
  }
  return world
}

export function player(world: World): Ship {
  const ship = world.ships.find((entry) => entry.role === 'player')
  if (!ship) throw new Error('missing player')
  return ship
}

export function addDummy(world: World, x: number, y: number): Ship {
  return makeShip(world, {
    kind: 'cruiser',
    team: 'hostile',
    role: 'dummy',
    name: 'Mark',
    x,
    y,
    shield: 1_000_000_000,
    armor: 0,
    hull: 1,
    speed: 0,
    agility: 0,
    signature: 200,
    radius: 120,
  })
}

export function setOrder(world: World, order: HelmOrder): void {
  player(world).order = order
}

export function adjustRange(world: World, delta: number): void {
  const ship = player(world)
  ship.order.range = clamp(ship.order.range + delta, 500, 40_000)
}

export function toggleProp(world: World): void {
  if (world.fit.prop === 'none') return
  world.fit.propOn = !world.fit.propOn
}

export function chooseCard(world: World, index: number): boolean {
  const card = world.pending?.[index]
  if (!card) return false
  const ok = applyCard(world.fit, card, HULLS[world.fit.hull])
  if (!ok) return false
  world.pending = null
  world.paused = false
  world.banner = { text: `${cardCopy(card).title} fitted.`, age: 0 }
  return true
}

export function forceBoss(world: World, which: 'burn' | 'mother' | 'bomber' | 'controller'): void {
  spawnBoss(world, which)
  world.spawned[which] = true
}

export function spawnTarget(world: World, x: number, y: number, hp = 5_000, signature = 80): Ship {
  return makeShip(world, {
    x,
    y,
    kind: 'frigate',
    team: 'hostile',
    role: 'trash',
    name: 'Mark',
    shield: hp,
    armor: 0,
    hull: 1,
    speed: 0,
    agility: 0,
    signature,
    radius: 80,
  })
}

export function stepWorld(world: World, dt: number): void {
  if (world.outcome !== 'play') return
  if (world.paused) return
  world.time += dt
  world.inPulse = false
  world.hurtAgo += dt
  if (world.banner) world.banner.age += dt
  for (const ship of world.ships) {
    if (ship.hit > 0) ship.hit = Math.max(0, ship.hit - dt)
    if (ship.slow > 0) ship.slow = Math.max(0, ship.slow - dt)
  }
  if (world.mode === 'belt') runTimeline(world, dt)
  syncDrones(world)
  const me = player(world)
  const scrammed = world.ships.some((ship) => ship.alive && ship.scramRange > 0 && dist(ship, me) < ship.scramRange)
  const webbed = world.ships.some((ship) => ship.alive && ship.team === 'hostile' && ship.webRange > 0 && dist(ship, me) < ship.webRange)
  const painted = world.ships.some((ship) => ship.alive && ship.team === 'hostile' && ship.paintRange > 0 && dist(ship, me) < ship.paintRange)
  const motion = playerMotion(world, scrammed, webbed, painted)
  world.playerMotion = motion
  for (const ship of world.ships) {
    if (!ship.alive || ship.role === 'dummy' || ship.role === 'player') continue
    assignOrder(world, ship)
  }
  integrateBodies(world, dt, motion)
  contain(me, dt)
  fireGuns(world, dt)
  stepShots(world, dt)
  stepPulses(world, dt)
  repair(world, dt)
  reap(world, dt)
  if (world.offers) grantLevels(world)
}

function integrateBodies(world: World, dt: number, motion: World['playerMotion']): void {
  for (const ship of world.ships) {
    if (!ship.alive || ship.role === 'dummy') continue
    const target = findShip(world, ship.order.targetId)
    const speed = ship.role === 'player'
      ? motion.speed * (ship.slow > 0 ? 0.55 : 1)
      : ship.speed * (ship.slow > 0 ? 0.55 : 1) * (webbedByPlayer(world, ship) ? 0.45 : 1)
    const agility = ship.role === 'player' ? motion.agility : ship.agility
    const body = {
      x: ship.x,
      y: ship.y,
      vx: ship.vx,
      vy: ship.vy,
      heading: ship.heading,
      speed: world.speedOverride > 0 && ship.role === 'player' ? world.speedOverride : speed,
      agility,
    }
    stepHelm(body, ship.order, target, dt)
    ship.x = body.x
    ship.y = body.y
    ship.vx = body.vx
    ship.vy = body.vy
    ship.heading = body.heading
  }
}

function runTimeline(world: World, dt: number): void {
  if (world.time >= 90 && !world.spawned.burn) {
    world.spawned.burn = true
    spawnBoss(world, 'burn')
    world.banner = { text: 'The Burn lights its microwarpdrive.', age: 0 }
  }
  if (world.time >= 210 && !world.spawned.mother) {
    world.spawned.mother = true
    spawnBoss(world, 'mother')
    world.banner = { text: 'Strain Mother is immune while her splinters live.', age: 0 }
  }
  if (world.time >= 330 && !world.spawned.bomber) {
    world.spawned.bomber = true
    spawnBoss(world, 'bomber')
    const line = world.escortKind === 'web'
      ? 'Bomber Alvum lands with three webs.'
      : 'Bomber Alvum lands with a painter.'
    world.banner = { text: line, age: 0 }
  }
  if (world.time >= 480 && !world.spawned.controller) {
    world.spawned.controller = true
    spawnBoss(world, 'controller')
    world.banner = { text: 'Logistics frigates are holding the Controller.', age: 0 }
  }
  const controller = world.ships.find((ship) => ship.role === 'controller' && ship.alive)
  if (controller) world.controllerAge += dt
  if (world.time < world.quietUntil) return
  world.trashCd -= dt
  if (world.trashCd > 0) return
  world.trashCd = world.time < 90 ? 1.25 : world.time < 210 ? 1.7 : 2.3
  const cap = world.time < 90 ? 14 : world.time < 210 ? 18 : 22
  const hostiles = world.ships.filter((ship) => ship.alive && ship.team === 'hostile' && !ship.boss).length
  if (hostiles >= cap) return
  const roll = world.rng()
  if (world.time < 100 || roll < 0.55) spawnSplinter(world, 4_000 + world.rng() * 8_000)
  else if (world.time < 220 || roll < 0.82) spawnRaider(world)
  else spawnCruiser(world)
}

function spawnBoss(world: World, which: 'burn' | 'mother' | 'bomber' | 'controller'): void {
  const me = player(world)
  const at = (distance: number, angle: number) => ({
    x: me.x + Math.cos(angle) * distance,
    y: me.y + Math.sin(angle) * distance,
  })
  const angle = world.rng() * Math.PI * 2
  if (which === 'burn') {
    const pos = at(16_000, angle)
    makeShip(world, {
      ...pos,
      kind: 'frigate',
      team: 'hostile',
      role: 'burn',
      name: 'The Burn',
      boss: true,
      shield: 900,
      armor: 1400,
      hull: 2200,
      speed: 640,
      agility: 1.8,
      signature: 55,
      radius: 70,
      scramRange: SCRAM_RANGE,
      gunDamage: 42,
      gunInterval: 0.42,
      gunRange: 9_000,
    })
    for (let i = 0; i < 4; i += 1) spawnSplinter(world, 2_000, pos.x, pos.y)
    return
  }
  if (which === 'mother') {
    const pos = at(14_000, angle)
    makeShip(world, {
      ...pos,
      kind: 'cruiser',
      team: 'hostile',
      role: 'mother',
      name: 'Strain Mother',
      boss: true,
      shield: 800,
      armor: 1600,
      hull: 1600,
      speed: 280,
      agility: 0.8,
      signature: 160,
      radius: 160,
      gunDamage: 10,
      gunInterval: 1.4,
      gunRange: 16_000,
    })
    for (let i = 0; i < 6; i += 1) {
      const splinter = spawnSplinter(world, 800 + i * 120, pos.x, pos.y)
      splinter.role = 'mother-splinter'
      splinter.name = 'Webbing splinter'
      splinter.webRange = 11_000
      splinter.shield = 40
      splinter.armor = 40
      splinter.hull = 80
      splinter.shieldMax = 40
      splinter.armorMax = 40
      splinter.hullMax = 80
    }
    return
  }
  if (which === 'bomber') {
    const pos = at(18_000, angle)
    makeShip(world, {
      ...pos,
      kind: 'cruiser',
      team: 'hostile',
      role: 'bomber',
      name: 'Bomber Alvum',
      boss: true,
      shield: 700,
      armor: 1800,
      hull: 1700,
      speed: 340,
      agility: 0.9,
      signature: 150,
      radius: 150,
      gunDamage: 28,
      gunInterval: 1.6,
      gunRange: 26_000,
      pulseInterval: 9,
      pulseRadius: 7_000,
      pulseDamage: 220,
      pulseCd: 4,
    })
    if (world.escortKind === 'web') {
      for (let i = 0; i < 3; i += 1) {
        const wing = spawnRaider(world, pos.x, pos.y)
        wing.role = 'escort'
        wing.name = 'Web frigate'
        wing.webRange = 10_000
      }
    } else {
      const wing = spawnRaider(world, pos.x, pos.y)
      wing.role = 'escort'
      wing.name = 'Painter frigate'
      wing.paintRange = 30_000
    }
    return
  }
  const pos = at(24_000, angle)
  makeShip(world, {
    ...pos,
    kind: 'battlecruiser',
    team: 'hostile',
    role: 'controller',
    name: 'Alvus Controller',
    boss: true,
    shield: 1400,
    armor: 1800,
    hull: 1600,
    speed: 420,
    agility: 0.7,
    signature: 280,
    radius: 220,
    gunDamage: 55,
    gunInterval: 1.8,
    gunRange: 32_000,
    pulseInterval: 8,
    pulseRadius: 8_000,
    pulseDamage: 260,
    pulseCd: 6,
  })
  for (let i = 0; i < 4; i += 1) {
    const logi = makeShip(world, {
      x: pos.x + Math.cos(i) * 2_000,
      y: pos.y + Math.sin(i) * 2_000,
      kind: 'logi',
      team: 'hostile',
      role: 'escort',
      name: 'Logistics frigate',
      shield: 200,
      armor: 180,
      hull: 160,
      speed: 500,
      agility: 1.6,
      signature: 50,
      radius: 60,
      gunDamage: 8,
      gunInterval: 1.2,
      gunRange: 8_000,
      heal: 260,
    })
    void logi
  }
}

function syncDrones(world: World): void {
  if (!world.fit.families.includes('drone')) {
    for (const drone of world.ships) {
      if (drone.role === 'drone') drone.alive = false
    }
    return
  }
  const wanted = 2 + rankOf(world.fit, 'drone')
  const living = world.ships.filter((ship) => ship.role === 'drone' && ship.alive)
  const me = player(world)
  while (living.length < wanted) {
    const drone = makeShip(world, {
      x: me.x + world.rng() * 400,
      y: me.y,
      kind: 'drone',
      team: 'player',
      role: 'drone',
      name: 'Drone',
      shield: 40,
      armor: 30,
      hull: 40,
      speed: 900,
      agility: 2.8,
      signature: 30,
      radius: 30,
      gunDamage: 16 * (1 + 0.25 * (rankOf(world.fit, 'drone') - 1)),
      gunInterval: 0.7,
      gunRange: 14_000,
    })
    living.push(drone)
  }
}

function assignOrder(world: World, ship: Ship): void {
  const me = player(world)
  if (ship.role === 'drone') {
    ship.order = { type: 'orbit', x: 0, y: 0, targetId: me.id, range: 1_400 + (ship.id % 4) * 280, sign: ship.order.sign || 1 }
    return
  }
  if (ship.role === 'mother') {
    ship.order = { type: 'keep', x: 0, y: 0, targetId: me.id, range: 14_000, sign: ship.order.sign }
    return
  }
  if (ship.role === 'bomber') {
    ship.order = { type: 'keep', x: 0, y: 0, targetId: me.id, range: 16_000, sign: ship.order.sign }
    return
  }
  if (ship.role === 'controller') {
    if (world.controllerAge < 45) {
      ship.order = { type: 'keep', x: 0, y: 0, targetId: me.id, range: 22_000, sign: ship.order.sign }
    } else {
      ship.order = { type: 'approach', x: 0, y: 0, targetId: me.id, range: 0, sign: 0 }
    }
    return
  }
  if (ship.role === 'escort') {
    const controller = world.ships.find((entry) => entry.role === 'controller' && entry.alive)
    if (controller) {
      ship.order = { type: 'orbit', x: 0, y: 0, targetId: controller.id, range: 3_200, sign: ship.order.sign || 1 }
      return
    }
  }
  if (ship.kind === 'cruiser') {
    ship.order = { type: 'keep', x: 0, y: 0, targetId: me.id, range: 10_000, sign: ship.order.sign }
    return
  }
  ship.order = { type: 'approach', x: 0, y: 0, targetId: me.id, range: 0, sign: 0 }
}

function fireGuns(world: World, dt: number): void {
  for (const ship of world.ships) {
    if (ship.team === 'hostile') ship.signature = ship.sigBase
  }
  const me = player(world)
  const gunTarget = pickTarget(world, me, 40_000)
  if (world.fit.utility === 'painter' && gunTarget) {
    const painted = world.fit.evolutions.includes('spike') ? 220 : gunTarget.sigBase * 1.25
    gunTarget.signature = Math.max(gunTarget.sigBase, painted)
  }
  for (const family of world.fit.families) {
    if (family === 'drone') continue
    const state = familyState(world, family)
    state.cd -= dt
    if (state.cd > 0) continue
    if (family === 'smartbomb') {
      state.telegraph = 0.85
      state.cd = 7.5
      continue
    }
    const range = family === 'autocannon' ? 15_000 : family === 'artillery' ? 34_000 : 30_000
    const target = pickTarget(world, me, range)
    if (!target) continue
    const rank = rankOf(world.fit, family)
    const volley = world.fit.hull === 'gun' && (family === 'artillery' || family === 'autocannon') ? rank : 1
    for (let i = 0; i < volley; i += 1) {
      launch(world, me, target, family, i, volley)
    }
    state.cd = family === 'autocannon' ? 0.32 : family === 'artillery' ? 2.05 : 1.35
  }
  if (mePulse(world).telegraph > 0) {
    mePulse(world).telegraph -= dt
    if (mePulse(world).telegraph <= 0) {
      pulseAt(world, me, 5_200, 80 * (1 + 0.35 * (rankOf(world.fit, 'smartbomb') - 1)) * world.damageScale, 'player')
    }
  }
  for (const ship of world.ships) {
    if (!ship.alive || ship.role === 'player' || ship.role === 'dummy') continue
    if (ship.gunInterval <= 0) continue
    ship.gunCd -= dt
    if (ship.gunCd > 0) continue
    const target = ship.team === 'player' ? pickTarget(world, ship, ship.gunRange) : (dist(ship, me) <= ship.gunRange ? me : null)
    if (!target) continue
    ship.gunCd = ship.gunInterval
    const family: FamilyId | 'npc' = ship.role === 'drone' ? 'drone' : 'npc'
    const damage = ship.role === 'drone' ? ship.gunDamage : ship.gunDamage * incomingFactor(world.playerMotion.signature)
    const speed = ship.role === 'drone' ? 2_400 : 1_800
    launchRaw(world, ship, target, damage, family, speed, false, 0, 0, ship.gunRange / speed + 0.6)
  }
}

function stepShots(world: World, dt: number): void {
  for (const shot of world.shots) {
    shot.life -= dt
    if (shot.homing) {
      const target = findShip(world, shot.targetId)
      if (target?.alive) {
        const desired = Math.atan2(target.y - shot.y, target.x - shot.x)
        let diff = desired - shot.heading
        while (diff > Math.PI) diff -= Math.PI * 2
        while (diff < -Math.PI) diff += Math.PI * 2
        shot.heading += clamp(diff, -2.2 * dt, 2.2 * dt)
        shot.vx = Math.cos(shot.heading) * shot.speed
        shot.vy = Math.sin(shot.heading) * shot.speed
      }
    }
    shot.x += shot.vx * dt
    shot.y += shot.vy * dt
    if (shot.life <= 0) continue
    for (const ship of world.ships) {
      if (!ship.alive || ship.team === shot.team) continue
      if (Math.hypot(ship.x - shot.x, ship.y - shot.y) > ship.radius + 160) continue
      const amount = appliedDamage(world, shot.damage, shot.family, ship)
      hurt(world, ship, amount, shot.family, shot.team)
      if (shot.splash > 0) {
        for (const other of world.ships) {
          if (!other.alive || other.team === shot.team || other.id === ship.id) continue
          if (Math.hypot(other.x - ship.x, other.y - ship.y) < shot.splash) {
            hurt(world, other, amount * 0.45, shot.family, shot.team)
          }
        }
      }
      shot.life = 0
      break
    }
  }
  world.shots = world.shots.filter((shot) => shot.life > 0).slice(-120)
}

function stepPulses(world: World, dt: number): void {
  for (const ship of world.ships) {
    if (!ship.alive || ship.pulseInterval <= 0) continue
    if (ship.role === 'controller' && world.controllerAge < 45) continue
    ship.pulseCd -= dt
    if (ship.pulseTelegraph > 0) {
      ship.pulseTelegraph -= dt
      if (ship.pulseTelegraph <= 0) pulseAt(world, ship, ship.pulseRadius, ship.pulseDamage, 'hostile')
      continue
    }
    if (ship.pulseCd <= 0) {
      ship.pulseTelegraph = 1.15
      ship.pulseCd = ship.pulseInterval
    }
  }
}

function pulseAt(world: World, origin: Ship, radius: number, damage: number, team: 'player' | 'hostile'): void {
  if (world.pulseDepth > 2) return
  world.pulseDepth += 1
  world.booms.push({ x: origin.x, y: origin.y, age: 0, radius })
  for (const ship of world.ships) {
    if (!ship.alive || ship.team === team) continue
    if (Math.hypot(ship.x - origin.x, ship.y - origin.y) > radius) continue
    if (ship.role === 'player') world.inPulse = true
    hurt(world, ship, damage, 'smartbomb', team)
  }
  world.pulseDepth -= 1
}

function repair(world: World, dt: number): void {
  const controller = world.ships.find((ship) => ship.role === 'controller' && ship.alive)
  if (controller) {
    let heal = 0
    for (const escort of world.ships) {
      if (escort.alive && escort.role === 'escort' && escort.heal > 0) heal += escort.heal
    }
    if (heal > 0) {
      let left = heal * dt
      const shieldRoom = controller.shieldMax - controller.shield
      const toShield = Math.min(shieldRoom, left)
      controller.shield += toShield
      left -= toShield
      controller.armor = Math.min(controller.armorMax, controller.armor + left)
    }
  }
  const fit = world.fit
  if (world.hurtAgo > 4) return
  const me = player(world)
  const amount = (34 + fit.tankRank * 18) * dt
  if (fit.tank === 'shield') me.shield = Math.min(me.shieldMax, me.shield + amount)
  if (fit.tank === 'armor') me.armor = Math.min(me.armorMax, me.armor + amount)
}

function reap(world: World, dt: number): void {
  for (const boom of world.booms) boom.age += dt
  world.booms = world.booms.filter((boom) => boom.age < 0.9)
  world.ships = world.ships.filter((ship) => ship.alive || ship.role === 'player')
}

function hurt(world: World, ship: Ship, amount: number, family: FamilyId | 'npc', team: 'player' | 'hostile'): void {
  if (!ship.alive || amount <= 0) return
  if (ship.role === 'mother') {
    const guard = world.ships.some((entry) => entry.alive && entry.role === 'mother-splinter')
    if (guard) return
  }
  let left = amount * (1 - Math.min(0.45, world.fit.tankRank * 0.12) * (ship.role === 'player' ? 1 : 0))
  const take = (current: number) => {
    const used = Math.min(current, left)
    left -= used
    return current - used
  }
  ship.shield = take(ship.shield)
  ship.armor = take(ship.armor)
  ship.hull = take(ship.hull)
  ship.hit = 0.12
  if (family === 'autocannon' && world.fit.evolutions.includes('hail') && team === 'player') ship.slow = 1.3
  if (ship.role === 'player') {
    world.hurtAgo = 0
    if (ship.hull <= 0) {
      ship.hull = 0
      ship.alive = false
      world.outcome = 'dead'
      world.cause = deathCause(world)
      world.paused = true
      world.booms.push({ x: ship.x, y: ship.y, age: 0, radius: 1_600 })
    }
    return
  }
  if (ship.hull <= 0) {
    ship.alive = false
    world.kills += 1
    if (world.firstKillTime < 0) world.firstKillTime = world.time
    world.booms.push({ x: ship.x, y: ship.y, age: 0, radius: ship.boss ? 3_200 : 900 })
    const gain = ship.boss ? 48 : ship.kind === 'splinter' ? 6 : ship.kind === 'frigate' ? 14 : 22
    if (world.mode === 'belt') world.xp += gain
    if (ship.boss) {
      world.quietUntil = world.time + 12
      world.xp += 28
      world.banner = { text: `${ship.name} breaks apart.`, age: 0 }
    }
    if (ship.role === 'controller') {
      world.outcome = 'clear'
      world.paused = true
      world.banner = { text: 'The belt is clear.', age: 0 }
    }
    if (family === 'drone' && world.fit.evolutions.includes('feedback') && world.pulseDepth === 0) {
      pulseAt(world, ship, 1_800, 36, 'player')
    }
  }
}

function deathCause(world: World): DeathCause {
  const me = player(world)
  if (world.inPulse) return 'pulse'
  const burn = world.ships.find((ship) => ship.role === 'burn' && ship.alive)
  if (world.playerMotion.scrammed && burn && dist(burn, me) < SCRAM_RANGE + 800) return 'scram'
  const mother = world.ships.find((ship) => ship.role === 'mother' && ship.alive)
  const guards = world.ships.some((ship) => ship.alive && ship.role === 'mother-splinter')
  if (mother && guards) return 'mother'
  const controller = world.ships.find((ship) => ship.role === 'controller' && ship.alive)
  const escorts = world.ships.some((ship) => ship.alive && ship.role === 'escort' && ship.heal > 0)
  if (controller && escorts) return 'escorts'
  return 'belt'
}

function grantLevels(world: World): void {
  const need = xpForNext(world.level)
  if (world.xp < need || world.pending) return
  world.xp -= need
  world.level += 1
  world.pending = buildOffer(world.fit, HULLS[world.fit.hull], world.time, world.rng, world.offerState)
  world.paused = true
}

function playerMotion(world: World, scrammed: boolean, webbed: boolean, painted: boolean): World['playerMotion'] {
  const hull = HULLS[world.fit.hull]
  let prop = world.fit.propOn ? world.fit.prop : 'none'
  if (scrammed && prop === 'mwd') prop = 'none'
  let speed = hull.speed
  let agility = hull.agility
  let signature = hull.signature
  if (prop === 'ab') {
    speed *= 1.8
    agility *= 1.35
    signature *= 0.8
  } else if (prop === 'mwd') {
    speed *= 3.3
    agility *= 0.62
    signature *= 2.5
  }
  if (painted) signature *= 1.45
  if (world.fit.evolutions.includes('pocket') && world.fit.prop === 'ab') signature = hull.signature * 0.8
  if (webbed) speed *= 0.38
  const me = player(world)
  const bonus = world.fit.tank === 'buffer' ? 240 + world.fit.tankRank * 180 : 0
  const shieldMax = hull.shield + bonus
  if (shieldMax > me.shieldMax) me.shield += shieldMax - me.shieldMax
  me.shieldMax = shieldMax
  me.shield = Math.min(me.shield, me.shieldMax)
  return { speed, signature, agility, scrammed, webbed }
}

function appliedDamage(world: World, damage: number, family: FamilyId | 'npc', target: Ship): number {
  let amount = family === 'npc' ? damage : damage * world.damageScale
  if (family === 'artillery' || family === 'missile') {
    const spiked = family === 'artillery' && world.fit.evolutions.includes('spike') && target.signature >= 200
    const factor = spiked ? 1 : Math.min(1, target.signature / 90)
    amount *= Math.max(0.45, factor)
  }
  if (family === 'autocannon') amount *= 1 + 0.4 * (rankOf(world.fit, 'autocannon') - 1)
  if (family === 'artillery') amount *= 1 + 0.28 * (rankOf(world.fit, 'artillery') - 1)
  if (family === 'missile') amount *= 1 + 0.3 * (rankOf(world.fit, 'missile') - 1)
  return amount
}

function launch(world: World, from: Ship, target: Ship, family: FamilyId, index: number, volley: number): void {
  const base = family === 'autocannon' ? 62 : family === 'artillery' ? 170 : 78
  const speed = family === 'artillery' ? 1_050 : family === 'missile' ? 1_250 : 3_000
  const spread = (index - (volley - 1) / 2) * 0.08
  const reach = family === 'autocannon' ? 15_000 : family === 'artillery' ? 34_000 : 30_000
  launchRaw(world, from, target, base, family, speed, family === 'missile', family === 'missile' ? 700 : 0, spread, reach / speed + 0.6)
}

function launchRaw(
  world: World,
  from: Ship,
  target: Ship,
  damage: number,
  family: FamilyId | 'npc',
  speed: number,
  homing: boolean,
  splash: number,
  spread = 0,
  life = 3.2,
): void {
  if (world.shots.length >= 120) return
  const heading = Math.atan2(target.y - from.y, target.x - from.x) + spread
  world.shots.push({
    x: from.x + Math.cos(heading) * (from.radius + 20),
    y: from.y + Math.sin(heading) * (from.radius + 20),
    vx: Math.cos(heading) * speed,
    vy: Math.sin(heading) * speed,
    heading,
    speed,
    damage,
    life,
    team: from.team,
    family,
    homing,
    targetId: target.id,
    splash,
  })
}

function pickTarget(world: World, from: Ship, range: number): Ship | null {
  const motherGuarded = world.ships.some((ship) => ship.alive && ship.role === 'mother-splinter')
  let best: Ship | null = null
  let bestScore = Infinity
  for (const ship of world.ships) {
    if (!ship.alive || ship.team === from.team || ship.role === 'dummy') continue
    if (ship.role === 'mother' && motherGuarded) continue
    const distance = dist(from, ship)
    if (distance > range) continue
    let score = distance
    if (ship.role === 'mother-splinter') score -= 120_000
    if (ship.role === 'escort') score -= 60_000
    if (score < bestScore) {
      best = ship
      bestScore = score
    }
  }
  return best
}

function webbedByPlayer(world: World, ship: Ship): boolean {
  if (world.fit.utility !== 'web' || ship.team !== 'hostile') return false
  return dist(ship, player(world)) < 10_000
}

function contain(ship: Ship, dt: number): void {
  const distance = Math.hypot(ship.x, ship.y)
  if (distance <= ARENA_RADIUS) return
  const scale = ARENA_RADIUS / distance
  ship.x *= scale
  ship.y *= scale
  const inward = Math.atan2(-ship.y, -ship.x)
  ship.heading += clamp(wrapAngle(inward - ship.heading), -1.5 * dt, 1.5 * dt)
}

function xpForNext(level: number): number {
  if (level <= 1) return 24
  if (level === 2) return 36
  if (level === 3) return 52
  return 40 + level * 8
}

function incomingFactor(signature: number): number {
  return Math.min(1.55, 0.5 + signature / 120)
}

function familyState(world: World, family: FamilyId): { cd: number; telegraph: number } {
  const table = states(world)
  const existing = table[family]
  if (existing) return existing
  const created = { cd: 0.2, telegraph: 0 }
  table[family] = created
  return created
}

function mePulse(world: World): { cd: number; telegraph: number } {
  return familyState(world, 'smartbomb')
}

const gunStates = new WeakMap<World, Partial<Record<FamilyId, { cd: number; telegraph: number }>>>()

function states(world: World): Partial<Record<FamilyId, { cd: number; telegraph: number }>> {
  let table = gunStates.get(world)
  if (!table) {
    table = {}
    gunStates.set(world, table)
  }
  return table
}

function spawnSplinter(world: World, distance: number, x?: number, y?: number): Ship {
  const me = player(world)
  const angle = world.rng() * Math.PI * 2
  return makeShip(world, {
    x: x ?? me.x + Math.cos(angle) * distance,
    y: y ?? me.y + Math.sin(angle) * distance,
    kind: 'splinter',
    team: 'hostile',
    role: 'trash',
    name: 'Splinter',
    shield: 20,
    armor: 20,
    hull: 70,
    speed: 280,
    agility: 2.2,
    signature: 48,
    radius: 36,
    gunDamage: 7,
    gunInterval: 0.8,
    gunRange: 2_200,
  })
}

function spawnRaider(world: World, x?: number, y?: number): Ship {
  const me = player(world)
  const angle = world.rng() * Math.PI * 2
  const distance = 8_000 + world.rng() * 6_000
  return makeShip(world, {
    x: x ?? me.x + Math.cos(angle) * distance,
    y: y ?? me.y + Math.sin(angle) * distance,
    kind: 'frigate',
    team: 'hostile',
    role: 'trash',
    name: 'Raider',
    shield: 120,
    armor: 140,
    hull: 160,
    speed: 480,
    agility: 1.7,
    signature: 60,
    radius: 60,
    gunDamage: 16,
    gunInterval: 0.7,
    gunRange: 7_000,
  })
}

function spawnCruiser(world: World): Ship {
  const me = player(world)
  const angle = world.rng() * Math.PI * 2
  const distance = 12_000 + world.rng() * 6_000
  return makeShip(world, {
    x: me.x + Math.cos(angle) * distance,
    y: me.y + Math.sin(angle) * distance,
    kind: 'cruiser',
    team: 'hostile',
    role: 'trash',
    name: 'Wrecker',
    shield: 280,
    armor: 360,
    hull: 320,
    speed: 260,
    agility: 0.85,
    signature: 150,
    radius: 140,
    gunDamage: 24,
    gunInterval: 1.3,
    gunRange: 14_000,
  })
}

function makeShip(world: World, partial: Partial<Ship> & Pick<Ship, 'kind' | 'team' | 'role' | 'name'>): Ship {
  const shield = partial.shield ?? 0
  const armor = partial.armor ?? 0
  const hull = partial.hull ?? 1
  const ship: Ship = {
    id: world.nextId,
    kind: partial.kind,
    team: partial.team,
    role: partial.role,
    name: partial.name,
    x: partial.x ?? 0,
    y: partial.y ?? 0,
    vx: 0,
    vy: 0,
    heading: partial.heading ?? 0,
    radius: partial.radius ?? 50,
    signature: partial.signature ?? 40,
    sigBase: partial.sigBase ?? partial.signature ?? 40,
    shield,
    shieldMax: partial.shieldMax ?? shield,
    armor,
    armorMax: partial.armorMax ?? armor,
    hull,
    hullMax: partial.hullMax ?? hull,
    speed: partial.speed ?? 0,
    agility: partial.agility ?? 1,
    alive: true,
    scramRange: partial.scramRange ?? 0,
    webRange: partial.webRange ?? 0,
    paintRange: partial.paintRange ?? 0,
    gunDamage: partial.gunDamage ?? 0,
    gunInterval: partial.gunInterval ?? 0,
    gunRange: partial.gunRange ?? 0,
    gunCd: 0.3,
    pulseInterval: partial.pulseInterval ?? 0,
    pulseRadius: partial.pulseRadius ?? 0,
    pulseDamage: partial.pulseDamage ?? 0,
    pulseCd: partial.pulseCd ?? 0,
    pulseTelegraph: 0,
    order: partial.order ?? { type: 'approach', x: 0, y: 0, targetId: 0, range: 8_000, sign: 0 },
    slow: 0,
    hit: 0,
    boss: partial.boss ?? false,
    heal: partial.heal ?? 0,
  }
  world.nextId += 1
  world.ships.push(ship)
  return ship
}

function findShip(world: World, id: number): Ship | null {
  if (!id) return null
  return world.ships.find((ship) => ship.id === id && ship.alive) ?? null
}

function dist(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

function wrapAngle(angle: number): number {
  let value = angle
  while (value > Math.PI) value -= Math.PI * 2
  while (value < -Math.PI) value += Math.PI * 2
  return value
}

export function ehp(ship: Ship): number {
  return ship.shield + ship.armor + ship.hull
}

export function playerTelegraph(world: World): number {
  return states(world).smartbomb?.telegraph ?? 0
}

export function nextBoss(time: number): { name: string; at: number } | null {
  if (time < 90) return { name: 'The Burn', at: 90 }
  if (time < 210) return { name: 'Strain Mother', at: 210 }
  if (time < 330) return { name: 'Bomber Alvum', at: 330 }
  if (time < 480) return { name: 'Alvus Controller', at: 480 }
  return null
}

export function selectAt(world: World, x: number, y: number): number {
  let best = 0
  let bestDist = 1_600
  for (const ship of world.ships) {
    if (!ship.alive || ship.role === 'player' || ship.role === 'drone') continue
    const distance = Math.hypot(ship.x - x, ship.y - y)
    if (distance < bestDist) {
      best = ship.id
      bestDist = distance
    }
  }
  world.selectedId = best
  return best
}

export function orderToward(world: World, type: 'approach' | 'orbit' | 'keep'): void {
  const selected = findShip(world, world.selectedId)
    ?? pickTarget(world, player(world), 80_000)
  if (!selected) return
  world.selectedId = selected.id
  const current = player(world).order
  player(world).order = {
    type,
    x: 0,
    y: 0,
    targetId: selected.id,
    range: current.range || 8_000,
    sign: current.sign || 1,
  }
}

export function manualToward(world: World, x: number, y: number): void {
  world.selectedId = 0
  const current = player(world).order
  player(world).order = { type: 'manual', x, y, targetId: 0, range: current.range, sign: 0 }
}
