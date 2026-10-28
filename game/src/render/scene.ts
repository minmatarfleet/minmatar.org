import { mulberry32, player, playerTelegraph, type Ship, type World } from '../sim/world.ts'

export interface Rock {
  x: number
  y: number
  scale: number
  heading: number
}

export interface Glyph {
  mesh: 'ship' | 'rock' | 'shot' | 'ring' | 'sphere' | 'flame'
  pass: 'opaque' | 'add' | 'alpha'
  x: number
  y: number
  z: number
  heading: number
  scale: number
  rgba: [number, number, number, number]
}

export function beltRocks(seed: number): Rock[] {
  const rng = mulberry32(seed ^ 0x51ed)
  const rocks: Rock[] = []
  for (let i = 0; i < 70; i += 1) {
    const angle = rng() * Math.PI * 2
    const distance = 3_000 + rng() * 100_000
    rocks.push({
      x: Math.cos(angle) * distance,
      y: Math.sin(angle) * distance,
      scale: 500 + rng() * 1_700,
      heading: rng() * Math.PI * 2,
    })
  }
  return rocks
}

export function gather(world: World): { opaque: Glyph[]; add: Glyph[]; alpha: Glyph[] } {
  const opaque: Glyph[] = []
  const add: Glyph[] = []
  const alpha: Glyph[] = []
  const me = player(world)
  for (const ship of world.ships) {
    if (!ship.alive && ship.role !== 'player') continue
    const scale = hullScale(world, ship)
    const rgba = shipColor(ship, world.selectedId)
    opaque.push({ mesh: 'ship', pass: 'opaque', x: ship.x, y: 0, z: ship.y, heading: ship.heading, scale, rgba })
    if (boosting(world, ship)) {
      add.push({
        mesh: 'flame',
        pass: 'add',
        x: ship.x - Math.cos(ship.heading) * scale * 1.15,
        y: scale * 0.15,
        z: ship.y - Math.sin(ship.heading) * scale * 1.15,
        heading: ship.heading,
        scale: scale * 0.85,
        rgba: ship.role === 'burn' ? [1, 0.42, 0.12, 0.9] : [0.45, 0.72, 1, 0.8],
      })
    }
    if (ship.scramRange > 0) alpha.push(ring(ship.x, ship.y, ship.scramRange, [0.86, 0.24, 0.16, 0.8]))
    if (ship.webRange > 0 && ship.webRange < 40_000) alpha.push(ring(ship.x, ship.y, ship.webRange, [0.62, 0.45, 0.95, 0.45]))
    if (ship.paintRange > 0 && ship.paintRange < 40_000) alpha.push(ring(ship.x, ship.y, ship.paintRange, [0.95, 0.82, 0.35, 0.35]))
    if (ship.pulseTelegraph > 0 && ship.pulseRadius > 0) {
      const shown = ship.pulseRadius * (1 - ship.pulseTelegraph / 1.15)
      alpha.push({
        mesh: 'sphere',
        pass: 'alpha',
        x: ship.x,
        y: 0,
        z: ship.y,
        heading: 0,
        scale: Math.max(200, shown),
        rgba: [1, 0.45, 0.12, 0.18],
      })
    }
  }
  const telegraph = playerTelegraph(world)
  if (telegraph > 0) {
    alpha.push({
      mesh: 'sphere',
      pass: 'alpha',
      x: me.x,
      y: 0,
      z: me.y,
      heading: 0,
      scale: 5_200 * (1 - telegraph / 0.85),
      rgba: [0.95, 0.55, 0.2, 0.16],
    })
  }
  const anchor = world.ships.find((ship) => ship.id === me.order.targetId && ship.alive)
  if (anchor && (me.order.type === 'orbit' || me.order.type === 'keep')) {
    alpha.push(ring(anchor.x, anchor.y, me.order.range, [0.55, 0.82, 0.78, 0.85]))
  }
  if (me.order.type === 'manual') alpha.push(ring(me.order.x, me.order.y, 400, [0.86, 0.72, 0.42, 0.7]))
  for (const shot of world.shots) {
    add.push({
      mesh: 'shot',
      pass: 'add',
      x: shot.x,
      y: 90,
      z: shot.y,
      heading: shot.heading,
      scale: shot.family === 'artillery' ? 780 : shot.family === 'missile' ? 640 : 420,
      rgba: shot.team === 'player' ? [0.95, 0.84, 0.55, 0.95] : [1, 0.45, 0.32, 0.9],
    })
  }
  for (const boom of world.booms) {
    const life = 1 - boom.age / 0.9
    add.push({
      mesh: 'sphere',
      pass: 'add',
      x: boom.x,
      y: 0,
      z: boom.y,
      heading: 0,
      scale: boom.radius * (0.35 + boom.age),
      rgba: [1, 0.62, 0.28, 0.35 * life],
    })
  }
  return { opaque, add, alpha }
}

export function rockGlyphs(rocks: Rock[]): Glyph[] {
  return rocks.map((rock) => ({
    mesh: 'rock',
    pass: 'opaque' as const,
    x: rock.x,
    y: 0,
    z: rock.y,
    heading: rock.heading,
    scale: rock.scale,
    rgba: [0.34, 0.32, 0.29, 1] as [number, number, number, number],
  }))
}

function ring(x: number, z: number, scale: number, rgba: [number, number, number, number]): Glyph {
  return { mesh: 'ring', pass: 'alpha', x, y: 40, z, heading: 0, scale, rgba }
}

function boosting(world: World, ship: Ship): boolean {
  if (!ship.alive) return false
  if (ship.role === 'burn') return true
  if (ship.role === 'controller' && world.controllerAge > 45) return true
  return ship.role === 'player' && world.fit.propOn && world.fit.prop !== 'none' && !world.playerMotion.scrammed
}

function hullScale(world: World, ship: Ship): number {
  if (ship.role === 'player') return world.fit.hull === 'frigate' ? 720 : 980
  if (ship.role === 'drone') return 240
  switch (ship.kind) {
    case 'splinter':
      return 360
    case 'frigate':
      return 560
    case 'logi':
      return 520
    case 'cruiser':
      return 1_000
    case 'battlecruiser':
      return 1_450
    case 'player':
      return 780
    case 'drone':
      return 240
    default: {
      const neverKind: never = ship.kind
      return neverKind
    }
  }
}

function shipColor(ship: Ship, selectedId: number): [number, number, number, number] {
  let rgba: [number, number, number, number]
  if (ship.role === 'player') rgba = [0.9, 0.74, 0.42, 1]
  else if (ship.role === 'drone') rgba = [0.42, 0.78, 0.82, 1]
  else if (ship.role === 'burn') rgba = [0.95, 0.28, 0.16, 1]
  else if (ship.role === 'mother') rgba = [0.62, 0.7, 0.38, 1]
  else if (ship.role === 'mother-splinter') rgba = [0.55, 0.62, 0.32, 1]
  else if (ship.role === 'bomber') rgba = [0.72, 0.4, 0.22, 1]
  else if (ship.role === 'controller') rgba = [0.82, 0.62, 0.28, 1]
  else if (ship.role === 'escort') rgba = [0.32, 0.66, 0.58, 1]
  else if (ship.kind === 'cruiser') rgba = [0.62, 0.34, 0.28, 1]
  else if (ship.kind === 'frigate') rgba = [0.7, 0.32, 0.28, 1]
  else rgba = [0.55, 0.58, 0.54, 1]
  if (ship.id === selectedId) rgba = [Math.min(1, rgba[0] + 0.25), Math.min(1, rgba[1] + 0.25), Math.min(1, rgba[2] + 0.2), 1]
  if (ship.hit > 0) rgba = [1, 0.9, 0.8, 1]
  if (!ship.alive) rgba = [0.3, 0.3, 0.3, 1]
  return rgba
}
