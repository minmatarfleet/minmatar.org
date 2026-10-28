/** Speed below which an orbit command cannot hold the ring and the circle falls inward. */
export const ORBIT_HOLD_SPEED = 520

export interface HelmOrder {
  type: 'manual' | 'approach' | 'orbit' | 'keep'
  x: number
  y: number
  targetId: number
  range: number
  sign: number
}

export interface HelmBody {
  x: number
  y: number
  vx: number
  vy: number
  heading: number
  speed: number
  agility: number
}

export interface HelmPoint {
  x: number
  y: number
}

function wrap(angle: number): number {
  let value = angle
  while (value > Math.PI) value -= Math.PI * 2
  while (value < -Math.PI) value += Math.PI * 2
  return value
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}

export function orbitRange(order: HelmOrder, speed: number): number {
  if (order.type !== 'orbit') return order.range
  const factor = clamp(speed / ORBIT_HOLD_SPEED, 0.28, 1)
  return order.range * factor
}

export function stepHelm(body: HelmBody, order: HelmOrder, target: HelmPoint | null, dt: number): void {
  let desired = body.heading
  let throttle = 1
  if (order.type === 'manual') {
    const dx = order.x - body.x
    const dy = order.y - body.y
    const dist = Math.hypot(dx, dy)
    if (dist < 280) throttle = 0
    else desired = Math.atan2(dy, dx)
  } else if (target && order.type === 'approach') {
    desired = Math.atan2(target.y - body.y, target.x - body.x)
  } else if (target && order.type === 'orbit') {
    const range = Math.max(200, orbitRange(order, body.speed))
    const ang = Math.atan2(body.y - target.y, body.x - target.x)
    if (order.sign === 0) order.sign = 1
    const arc = (Math.max(body.speed, 80) / range) * 0.85
    const next = ang + order.sign * arc
    const wx = target.x + Math.cos(next) * range
    const wy = target.y + Math.sin(next) * range
    desired = Math.atan2(wy - body.y, wx - body.x)
  } else if (target && order.type === 'keep') {
    const dist = Math.hypot(target.x - body.x, target.y - body.y) || 1
    const tx = target.x + ((body.x - target.x) / dist) * order.range
    const ty = target.y + ((body.y - target.y) / dist) * order.range
    const err = Math.hypot(tx - body.x, ty - body.y)
    if (err < 450) {
      const ang = Math.atan2(body.y - target.y, body.x - target.x)
      if (order.sign === 0) order.sign = 1
      desired = ang + order.sign * (Math.PI / 2)
      throttle = 0.4
    } else {
      desired = Math.atan2(ty - body.y, tx - body.x)
    }
  }

  const maxTurn = body.agility * dt
  const diff = clamp(wrap(desired - body.heading), -maxTurn, maxTurn)
  body.heading += diff
  const maxSpeed = body.speed * throttle
  const blend = 1 - Math.exp(-2.4 * dt)
  body.vx += (Math.cos(body.heading) * maxSpeed - body.vx) * blend
  body.vy += (Math.sin(body.heading) * maxSpeed - body.vy) * blend
  body.x += body.vx * dt
  body.y += body.vy * dt
}
