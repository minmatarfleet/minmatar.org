import { describe, expect, it } from 'vitest'
import { orbitRange, stepHelm, type HelmBody, type HelmOrder } from '../src/sim/helm.ts'
import { buildOffer, canApply, startingFit, suggestedHull } from '../src/sim/offers.ts'
import { HULLS } from '../src/sim/types.ts'
import {
  addDummy,
  createWorld,
  ehp,
  forceBoss,
  player,
  setOrder,
  spawnTarget,
  stepWorld,
  type World,
} from '../src/sim/world.ts'

const DT = 1 / 30

function run(world: World, seconds: number): void {
  const steps = Math.round(seconds / DT)
  for (let i = 0; i < steps; i += 1) stepWorld(world, DT)
}

function sandbox(hull: 'frigate' | 'gun' | 'drone' = 'frigate', seed = 3): World {
  return createWorld(hull, seed, { mode: 'sandbox', offers: false })
}

describe('helm', () => {
  it('holds an orbit near the commanded range', () => {
    const world = sandbox()
    const mark = addDummy(world, 12_000, 0)
    setOrder(world, { type: 'orbit', x: 0, y: 0, targetId: mark.id, range: 10_000, sign: 1 })
    run(world, 25)
    const distance = Math.hypot(player(world).x - mark.x, player(world).y - mark.y)
    expect(distance).toBeGreaterThan(8_000)
    expect(distance).toBeLessThan(12_000)
  })

  it('decays an orbit when a web cuts speed', () => {
    const world = sandbox()
    const mark = addDummy(world, 14_000, 0)
    const web = addDummy(world, 0, 0)
    web.webRange = 100_000
    setOrder(world, { type: 'orbit', x: 0, y: 0, targetId: mark.id, range: 10_000, sign: 1 })
    run(world, 55)
    const distance = Math.hypot(player(world).x - mark.x, player(world).y - mark.y)
    expect(distance).toBeLessThan(6_500)
    expect(orbitRange({ type: 'orbit', x: 0, y: 0, targetId: 0, range: 10_000, sign: 1 }, 200)).toBeLessThan(5_000)
  })

  it('keeps a chosen range', () => {
    const world = sandbox()
    const mark = addDummy(world, 28_000, 0)
    setOrder(world, { type: 'keep', x: 0, y: 0, targetId: mark.id, range: 12_000, sign: 1 })
    run(world, 40)
    const distance = Math.hypot(player(world).x - mark.x, player(world).y - mark.y)
    expect(distance).toBeGreaterThan(10_000)
    expect(distance).toBeLessThan(14_000)
  })

  it('aligns toward a manual point instead of snapping', () => {
    const body: HelmBody = { x: 0, y: 0, vx: 0, vy: 0, heading: Math.PI / 2, speed: 600, agility: 1.2 }
    const order: HelmOrder = { type: 'manual', x: 8_000, y: 0, targetId: 0, range: 8_000, sign: 0 }
    stepHelm(body, order, null, DT)
    expect(body.heading).toBeLessThan(Math.PI / 2)
    expect(body.heading).toBeGreaterThan(Math.PI / 2 - 0.2)
    for (let i = 0; i < 30 * 12; i += 1) stepHelm(body, order, null, DT)
    expect(body.x).toBeGreaterThan(3_000)
    expect(Math.abs(body.heading)).toBeLessThan(0.35)
  })

  it('leaves an orbit when the order becomes manual', () => {
    const world = sandbox()
    const mark = addDummy(world, 8_000, 0)
    setOrder(world, { type: 'orbit', x: 0, y: 0, targetId: mark.id, range: 6_000, sign: 1 })
    run(world, 8)
    setOrder(world, { type: 'manual', x: 0, y: 30_000, targetId: 0, range: 6_000, sign: 0 })
    const before = Math.hypot(player(world).x, player(world).y - 30_000)
    run(world, 6)
    const after = Math.hypot(player(world).x, player(world).y - 30_000)
    expect(player(world).order.type).toBe('manual')
    expect(after).toBeLessThan(before - 1_000)
  })
})

describe('belt rules', () => {
  it('pops the first splinter in under three seconds', () => {
    const world = createWorld('frigate', 2, { mode: 'belt', offers: false })
    run(world, 3)
    expect(world.firstKillTime).toBeGreaterThan(0)
    expect(world.firstKillTime).toBeLessThan(3)
  })

  it('cuts a microwarpdrive inside a scram and that approach dies', () => {
    const world = sandbox()
    world.fit.prop = 'mwd'
    world.fit.propOn = true
    const scram = addDummy(world, 0, 100)
    scram.scramRange = 50_000
    stepWorld(world, DT)
    expect(world.playerMotion.speed).toBeCloseTo(HULLS.frigate.speed, 0)
    expect(world.playerMotion.scrammed).toBe(true)

    const fight = sandbox('frigate', 5)
    fight.fit.prop = 'mwd'
    fight.fit.propOn = true
    forceBoss(fight, 'burn')
    const burn = fight.ships.find((ship) => ship.role === 'burn')
    expect(burn).toBeTruthy()
    setOrder(fight, { type: 'approach', x: 0, y: 0, targetId: burn!.id, range: 0, sign: 0 })
    run(fight, 35)
    expect(fight.outcome).toBe('dead')
    expect(fight.cause).toBe('scram')
  })

  it('lets an afterburner orbit outside the scram ring kill the Burn', () => {
    const world = sandbox('frigate', 7)
    world.fit.prop = 'ab'
    world.fit.propOn = true
    forceBoss(world, 'burn')
    const burn = world.ships.find((ship) => ship.role === 'burn')!
    setOrder(world, { type: 'orbit', x: 0, y: 0, targetId: burn.id, range: 11_000, sign: 1 })
    run(world, 50)
    expect(player(world).alive).toBe(true)
    expect(burn.alive).toBe(false)
    expect(world.playerMotion.scrammed).toBe(false)
  })

  it('does not damage the Mother while a splinter lives, and drones shoot the splinters', () => {
    const guns = sandbox('frigate', 1)
    forceBoss(guns, 'mother')
    guns.damageScale = 8
    for (const ship of guns.ships) {
      if (ship.role === 'mother' || ship.role === 'mother-splinter') {
        ship.x = 4_000
        ship.y = (ship.id % 7) * 180
      }
      if (ship.role === 'mother-splinter') {
        ship.shield = 20_000
        ship.shieldMax = 20_000
      }
    }
    const mother = guns.ships.find((ship) => ship.role === 'mother')!
    const before = ehp(mother)
    const guardsBefore = guns.ships.filter((ship) => ship.role === 'mother-splinter').reduce((sum, ship) => sum + ehp(ship), 0)
    run(guns, 4)
    const guardsAfter = guns.ships.filter((ship) => ship.role === 'mother-splinter').reduce((sum, ship) => sum + ehp(ship), 0)
    expect(guns.ships.some((ship) => ship.alive && ship.role === 'mother-splinter')).toBe(true)
    expect(ehp(mother)).toBe(before)
    expect(guardsAfter).toBeLessThan(guardsBefore)

    const drones = sandbox('drone', 1)
    forceBoss(drones, 'mother')
    for (const ship of drones.ships) {
      if (ship.role === 'mother' || ship.role === 'mother-splinter') {
        ship.x = 4_000
        ship.y = (ship.id % 7) * 180
      }
    }
    const motherTwo = drones.ships.find((ship) => ship.role === 'mother')!
    const splinter = drones.ships.find((ship) => ship.role === 'mother-splinter')!
    const motherHp = ehp(motherTwo)
    const splinterHp = ehp(splinter)
    run(drones, 6)
    expect(ehp(motherTwo)).toBe(motherHp)
    expect(ehp(splinter)).toBeLessThan(splinterHp)
  })

  it('holds the Controller while escorts live and a strong fit clears them', () => {
    const held = sandbox('gun', 4)
    forceBoss(held, 'controller')
    const controller = held.ships.find((ship) => ship.role === 'controller')!
    controller.shield -= 400
    const dipped = controller.shield
    run(held, 1)
    expect(controller.shield).toBeGreaterThan(dipped + 200)

    const clear = sandbox('gun', 9)
    clear.fit.ranks.artillery = 4
    clear.damageScale = 40
    clear.fit.prop = 'ab'
    clear.fit.propOn = true
    forceBoss(clear, 'controller')
    const boss = clear.ships.find((ship) => ship.role === 'controller')!
    setOrder(clear, { type: 'keep', x: 0, y: 0, targetId: boss.id, range: 20_000, sign: 1 })
    run(clear, 45)
    expect(clear.outcome).toBe('clear')
    expect(player(clear).alive).toBe(true)
  })
})

describe('evolutions and offers', () => {
  it('applies Hail, Spike, Feedback, and Pocket as one rule each', () => {
    const hail = sandbox()
    hail.fit.utility = 'web'
    hail.fit.evolutions = ['hail']
    const slowed = spawnTarget(hail, 1_500, 0, 8_000, 80)
    run(hail, 4)
    expect(slowed.slow).toBeGreaterThan(0)

    const plain = sandbox('gun')
    plain.fit.utility = 'painter'
    const small = spawnTarget(plain, 2_000, 0, 8_000, 40)
    run(plain, 5)
    const plainDrop = 8_001 - ehp(small)

    const spiked = sandbox('gun')
    spiked.fit.utility = 'painter'
    spiked.fit.evolutions = ['spike']
    const painted = spawnTarget(spiked, 2_000, 0, 8_000, 40)
    run(spiked, 5)
    const spikeDrop = 8_001 - ehp(painted)
    expect(spikeDrop).toBeGreaterThan(plainDrop * 1.4)

    const feedback = sandbox('drone')
    feedback.fit.families = ['drone', 'smartbomb']
    feedback.fit.ranks = { drone: 1, smartbomb: 1 }
    feedback.fit.evolutions = ['feedback']
    spawnTarget(feedback, 1_600, 0, 10, 80)
    const bystander = spawnTarget(feedback, 1_600, 400, 500, 80)
    run(feedback, 6)
    expect(ehp(bystander)).toBeLessThan(501)

    const pocket = sandbox()
    pocket.fit.prop = 'ab'
    pocket.fit.propOn = true
    pocket.fit.tank = 'buffer'
    pocket.fit.evolutions = ['pocket']
    const painter = addDummy(pocket, 0, 0)
    painter.paintRange = 80_000
    stepWorld(pocket, DT)
    expect(pocket.playerMotion.signature).toBeCloseTo(HULLS.frigate.signature * 0.8, 1)
    expect(player(pocket).shieldMax).toBe(HULLS.frigate.shield + 240)

    pocket.fit.evolutions = []
    stepWorld(pocket, DT)
    expect(pocket.playerMotion.signature).toBeGreaterThan(HULLS.frigate.signature * 0.8 + 5)
  })

  it('offers the prop fork early, the tank fork once, and no new family in the lesson slot after 6:30', () => {
    const fit = startingFit('frigate')
    const hull = HULLS.frigate
    const early = buildOffer(fit, hull, 20, () => 0.2, { tankForkShown: false })
    expect(early.some((card) => card.kind === 'prop' && card.prop === 'ab')).toBe(true)
    expect(early.some((card) => card.kind === 'prop' && card.prop === 'mwd')).toBe(true)

    fit.prop = 'ab'
    const state = { tankForkShown: false }
    const tanks = buildOffer(fit, hull, 120, () => 0.4, state)
    expect(tanks.map((card) => card.kind)).toEqual(['tank', 'tank', 'tank'])
    expect(state.tankForkShown).toBe(true)

    fit.families = ['autocannon', 'missile', 'artillery']
    fit.ranks = { autocannon: 1, missile: 1, artillery: 1 }
    const late = buildOffer(fit, hull, 400, () => 0.3, state)
    expect(late[0]?.kind).not.toBe('family')
    expect(canApply(fit, { kind: 'family', family: 'drone' }, hull)).toBe(false)
    expect(canApply(fit, { kind: 'family', family: 'smartbomb' }, hull)).toBe(false)
    expect(suggestedHull('scram', 'gun')).toBe('frigate')
    expect(suggestedHull('pulse', 'frigate')).toBe('gun')
    expect(suggestedHull('escorts', 'frigate')).toBe('drone')
  })
})
