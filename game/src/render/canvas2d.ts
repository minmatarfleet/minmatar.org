import { followCamera, project, type Camera } from './camera.ts'
import { gather, rockGlyphs, type Glyph } from './scene.ts'
import type { Rock } from './scene.ts'
import type { World } from '../sim/world.ts'

export interface Frame {
  name: 'canvas' | 'webgpu'
  resize: (width: number, height: number, dpr: number) => void
  draw: (world: World, rocks: Rock[], width: number, height: number) => void
}

export function createCanvasRenderer(canvas: HTMLCanvasElement): Frame {
  const context = canvas.getContext('2d')
  if (!context) throw new Error('canvas 2d unavailable')
  let width = 1
  let height = 1

  return {
    name: 'canvas',
    resize(cssWidth, cssHeight, dpr) {
      width = cssWidth
      height = cssHeight
      canvas.width = Math.max(1, Math.floor(cssWidth * dpr))
      canvas.height = Math.max(1, Math.floor(cssHeight * dpr))
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
    },
    draw(world, rocks) {
      const me = world.ships.find((ship) => ship.role === 'player')
      const camera = followCamera(me?.x ?? 0, me?.y ?? 0, me?.heading ?? 0, width / height)
      const sky = context.createLinearGradient(0, 0, 0, height)
      sky.addColorStop(0, '#12151c')
      sky.addColorStop(0.55, '#1a140f')
      sky.addColorStop(1, '#07080b')
      context.fillStyle = sky
      context.fillRect(0, 0, width, height)
      const scene = gather(world)
      const glyphs = [...rockGlyphs(rocks), ...scene.opaque, ...scene.alpha, ...scene.add]
      const drawn = glyphs
        .map((glyph) => ({ glyph, at: project(camera, glyph.x, glyph.y, glyph.z, width, height) }))
        .filter((entry): entry is { glyph: Glyph; at: { x: number; y: number; depth: number } } => entry.at !== null && entry.at.depth > 0 && entry.at.depth < 1)
        .sort((a, b) => b.at.depth - a.at.depth)
      for (const entry of drawn) paint(context, camera, entry.glyph, entry.at, width, height)
    },
  }
}

function paint(
  context: CanvasRenderingContext2D,
  camera: Camera,
  glyph: Glyph,
  at: { x: number; y: number },
  width: number,
  height: number,
): void {
  const edge = project(camera, glyph.x + glyph.scale, glyph.y, glyph.z, width, height)
  const radius = edge ? Math.max(1.5, Math.hypot(edge.x - at.x, edge.y - at.y)) : 4
  const [r, g, b, a] = glyph.rgba
  context.fillStyle = `rgba(${Math.round(r * 255)}, ${Math.round(g * 255)}, ${Math.round(b * 255)}, ${a})`
  context.strokeStyle = context.fillStyle
  if (glyph.mesh === 'ring') {
    context.beginPath()
    context.arc(at.x, at.y, radius, 0, Math.PI * 2)
    context.lineWidth = Math.max(1, radius * 0.015)
    context.stroke()
    return
  }
  if (glyph.mesh === 'sphere' || glyph.mesh === 'flame' || glyph.mesh === 'rock') {
    context.beginPath()
    context.arc(at.x, at.y, glyph.mesh === 'flame' ? radius * 0.45 : radius * (glyph.mesh === 'rock' ? 0.55 : 1), 0, Math.PI * 2)
    context.fill()
    return
  }
  if (glyph.mesh === 'shot') {
    const tail = project(camera, glyph.x - Math.cos(glyph.heading) * glyph.scale, glyph.y, glyph.z - Math.sin(glyph.heading) * glyph.scale, width, height)
    context.beginPath()
    context.moveTo(at.x, at.y)
    context.lineTo(tail?.x ?? at.x, tail?.y ?? at.y)
    context.lineWidth = 2
    context.stroke()
    return
  }
  const nose = project(camera, glyph.x + Math.cos(glyph.heading) * glyph.scale * 1.7, 0, glyph.z + Math.sin(glyph.heading) * glyph.scale * 1.7, width, height)
  const left = project(camera, glyph.x + Math.cos(glyph.heading + 2.4) * glyph.scale, 0, glyph.z + Math.sin(glyph.heading + 2.4) * glyph.scale, width, height)
  const right = project(camera, glyph.x + Math.cos(glyph.heading - 2.4) * glyph.scale, 0, glyph.z + Math.sin(glyph.heading - 2.4) * glyph.scale, width, height)
  if (!nose || !left || !right) return
  context.beginPath()
  context.moveTo(nose.x, nose.y)
  context.lineTo(left.x, left.y)
  context.lineTo(right.x, right.y)
  context.closePath()
  context.fill()
}
