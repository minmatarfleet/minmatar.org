import { describe, expect, it } from 'vitest'
import { followCamera, groundAt, project } from '../src/render/camera.ts'
import { beltRocks, gather } from '../src/render/scene.ts'
import { createWorld, stepWorld } from '../src/sim/world.ts'

describe('camera', () => {
  it('projects the ship near the center and unprojects that pixel back onto the belt', () => {
    const camera = followCamera(0, 0, 0, 16 / 9)
    const screen = project(camera, 2_500, 0, 0, 1600, 900)
    expect(screen).toBeTruthy()
    expect(screen!.x).toBeGreaterThan(700)
    expect(screen!.x).toBeLessThan(900)
    expect(screen!.y).toBeGreaterThan(350)
    expect(screen!.y).toBeLessThan(550)
    const ground = groundAt(camera, screen!.x, screen!.y, 1600, 900)
    expect(ground).toBeTruthy()
    expect(ground!.x).toBeCloseTo(2_500, -2)
    expect(ground!.y).toBeCloseTo(0, -2)
  })

  it('draws the opening ships and the belt rocks', () => {
    const world = createWorld('frigate', 1, { mode: 'belt', offers: false })
    stepWorld(world, 1 / 30)
    const scene = gather(world)
    expect(scene.opaque.length).toBeGreaterThan(4)
    expect(beltRocks(1)).toHaveLength(70)
  })
})
