import { createEar } from './audio.ts'
import { followCamera, groundAt } from './render/camera.ts'
import { createCanvasRenderer, type Frame } from './render/canvas2d.ts'
import { beltRocks, type Rock } from './render/scene.ts'
import { createGpuRenderer } from './render/webgpu.ts'
import { cardCopy, familyName, highsUsed, lowsUsed, midsUsed, suggestedHull } from './sim/offers.ts'
import { HULLS, type DeathCause, type HullId } from './sim/types.ts'
import {
  TICK,
  adjustRange,
  chooseCard,
  createWorld,
  manualToward,
  nextBoss,
  orderToward,
  player,
  selectAt,
  stepWorld,
  toggleProp,
  type World,
} from './sim/world.ts'
import './style.css'

function required<T extends Element>(selector: string): T {
  const node = document.querySelector(selector)
  if (!node) throw new Error(`missing ${selector}`)
  return node as T
}

const canvas = required<HTMLCanvasElement>('#view')
const pickPanel = required<HTMLElement>('#pick')
const hullRow = required<HTMLElement>('#hulls')
const clock = required<HTMLElement>('#clock')
const banner = required<HTMLElement>('#banner')
const upcoming = required<HTMLElement>('#next')
const bars = required<HTMLElement>('#bars')
const slots = required<HTMLElement>('#slots')
const helm = required<HTMLElement>('#helm')
const rangeReadout = required<HTMLElement>('#range')
const speedReadout = required<HTMLElement>('#speed')
const orderReadout = required<HTMLElement>('#order')
const targetReadout = required<HTMLElement>('#target')
const cards = required<HTMLElement>('#cards')
const endPanel = required<HTMLElement>('#end')
const backend = required<HTMLElement>('#backend')
const fpsReadout = required<HTMLElement>('#fps')

const ear = createEar()
const params = new URLSearchParams(location.search)
const rate = clamp(Number(params.get('rate') ?? 1) || 1, 1, 30)
let seed = Number(params.get('seed') ?? 1) || 1
let hull: HullId = 'frigate'
let world: World | null = null
let rocks: Rock[] = []
let renderer: Frame | null = null
let lastStamp = performance.now()
let accumulator = 0
let fps = 60
let cardKey = ''
let endKey = ''
let lastClick = 0
let lastSelected = 0
let heardShots = 0
let heardBooms = 0

for (const id of ['frigate', 'gun', 'drone'] as const) {
  const def = HULLS[id]
  const button = document.createElement('button')
  button.type = 'button'
  button.className = 'hull'
  const title = document.createElement('strong')
  title.textContent = def.name
  const slotsLine = document.createElement('em')
  slotsLine.textContent = `${def.highs} high · ${def.mids} mid · ${def.lows} low${def.bay ? ' · bay' : ''}`
  const fantasy = document.createElement('span')
  fantasy.textContent = def.fantasy
  button.append(title, slotsLine, fantasy)
  button.addEventListener('click', () => begin(id, seed))
  hullRow.append(button)
}

helm.addEventListener('click', (event) => {
  const target = event.target
  if (!(target instanceof HTMLButtonElement) || !world) return
  const order = target.dataset.order
  if (order === 'approach' || order === 'orbit' || order === 'keep') orderToward(world, order)
  if (target.dataset.action === 'prop') toggleProp(world)
})

canvas.addEventListener('pointerdown', (event) => {
  if (!world || !renderer) return
  const rect = canvas.getBoundingClientRect()
  const me = player(world)
  const camera = followCamera(me.x, me.y, me.heading, rect.width / rect.height)
  const ground = groundAt(camera, event.clientX - rect.left, event.clientY - rect.top, rect.width, rect.height)
  if (!ground) return
  const id = selectAt(world, ground.x, ground.y)
  const now = performance.now()
  if (id && id === lastSelected && now - lastClick < 350) orderToward(world, 'approach')
  else if (!id) manualToward(world, ground.x, ground.y)
  lastSelected = id
  lastClick = now
})

canvas.addEventListener('wheel', (event) => {
  if (!world) return
  event.preventDefault()
  adjustRange(world, event.deltaY < 0 ? 500 : -500)
}, { passive: false })

window.addEventListener('keydown', (event) => {
  if (!world) return
  if (event.key === '1' || event.key === '2' || event.key === '3') {
    if (chooseCard(world, Number(event.key) - 1)) ear.card()
  } else if (event.key === 'a' || event.key === 'A') orderToward(world, 'approach')
  else if (event.key === 'o' || event.key === 'O') orderToward(world, 'orbit')
  else if (event.key === 'k' || event.key === 'K') orderToward(world, 'keep')
  else if (event.key === 'f' || event.key === 'F') toggleProp(world)
})

window.addEventListener('resize', resize)
void boot()

function begin(nextHull: HullId, nextSeed: number): void {
  hull = nextHull
  seed = nextSeed
  world = createWorld(hull, seed)
  rocks = beltRocks(seed)
  pickPanel.hidden = true
  endPanel.hidden = true
  cards.hidden = true
  cardKey = ''
  endKey = ''
  heardShots = 0
  heardBooms = 0
  accumulator = 0
}

async function boot(): Promise<void> {
  resize()
  try {
    renderer = await createGpuRenderer(canvas)
  } catch (error) {
    console.error(error)
    renderer = null
  }
  if (!renderer) {
    renderer = createCanvasRenderer(canvas as HTMLCanvasElement)
    backend.textContent = 'Canvas fallback. This browser has no WebGPU device.'
  } else {
    backend.textContent = 'WebGPU'
  }
  resize()
  const requested = params.get('hull')
  if (requested === 'frigate' || requested === 'gun' || requested === 'drone') begin(requested, seed)
  requestAnimationFrame(frame)
}

function frame(stamp: number): void {
  const dt = Math.min(0.05, (stamp - lastStamp) / 1000)
  lastStamp = stamp
  fps += (1 / Math.max(dt, 0.001) - fps) * 0.05
  if (world && world.outcome === 'play' && !world.paused) {
    accumulator += dt * rate
    let steps = 0
    while (accumulator >= TICK && steps < 45) {
      stepWorld(world, TICK)
      accumulator -= TICK
      steps += 1
    }
  }
  if (world && renderer) renderer.draw(world, rocks, canvas.clientWidth, canvas.clientHeight)
  paintHud()
  requestAnimationFrame(frame)
}

function paintHud(): void {
  fpsReadout.textContent = `${Math.round(fps)} fps`
  if (!world) return
  const current = world
  const me = player(current)
  clock.textContent = clockText(current.time)
  const boss = nextBoss(current.time)
  upcoming.textContent = boss ? `${boss.name} ${clockText(boss.at - current.time)}` : 'Controller is on the belt'
  banner.textContent = current.banner && current.banner.age < 5 ? current.banner.text : ''
  bars.replaceChildren(
    bar('shield', me.shield, me.shieldMax),
    bar('armor', me.armor, me.armorMax),
    bar('hull', me.hull, me.hullMax),
  )
  const hullDef = HULLS[current.fit.hull]
  slots.textContent = [
    `High ${highsUsed(current.fit)}/${hullDef.highs}  ${current.fit.families.map((family) => familyName(family)).join(' · ')}`,
    `Mid ${midsUsed(current.fit)}/${hullDef.mids}  ${propLabel(current)}`,
    `Low ${lowsUsed(current.fit)}/${hullDef.lows}  ${current.fit.tank === 'none' ? 'empty' : current.fit.tank}`,
  ].join('\n')
  rangeReadout.textContent = `${(me.order.range / 1000).toFixed(1)} km`
  const moving = Math.hypot(me.vx, me.vy)
  speedReadout.textContent = current.playerMotion.scrammed
    ? `SCRAM  ${Math.round(moving)} m/s`
    : `${Math.round(moving)} / ${Math.round(current.playerMotion.speed)} m/s`
  speedReadout.classList.toggle('scram', current.playerMotion.scrammed)
  orderReadout.textContent = orderName(me.order.type)
  const selected = current.ships.find((ship) => ship.id === current.selectedId && ship.alive)
  targetReadout.textContent = selected ? selected.name : 'no selection'
  hear(current)
  paintCards(current)
  paintEnd(current)
}

function paintCards(current: World): void {
  const pending = current.pending
  if (!pending) {
    cards.hidden = true
    cardKey = ''
    return
  }
  const key = JSON.stringify(pending)
  if (key === cardKey) return
  cardKey = key
  cards.hidden = false
  cards.replaceChildren()
  pending.forEach((card, index) => {
    const copy = cardCopy(card)
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'card'
    const slot = document.createElement('em')
    slot.textContent = `${index + 1}  ${copy.slot}`
    const title = document.createElement('strong')
    title.textContent = copy.title
    const detail = document.createElement('span')
    detail.textContent = copy.detail
    button.append(slot, title, detail)
    button.addEventListener('click', () => {
      if (chooseCard(current, index)) ear.card()
    })
    cards.append(button)
  })
  ear.card()
}

function paintEnd(current: World): void {
  if (current.outcome === 'play') {
    endPanel.hidden = true
    endKey = ''
    return
  }
  const key = `${current.outcome}:${current.cause ?? ''}:${seed}`
  if (key === endKey) return
  endKey = key
  endPanel.hidden = false
  endPanel.replaceChildren()
  const title = document.createElement('h2')
  title.textContent = current.outcome === 'clear' ? 'The belt is clear.' : causeLine(current.cause ?? 'belt')
  const detail = document.createElement('p')
  detail.textContent = `${HULLS[current.fit.hull].name} · seed ${seed} · ${fitLine(current)}`
  endPanel.append(title, detail)
  endPanel.append(
    endButton('Retry this seed', () => begin(hull, seed)),
    endButton('New seed', () => begin(hull, (seed + 1 + Math.floor(Math.random() * 900)) >>> 0)),
    endButton(`Fly a ${HULLS[suggestedHull(current.cause ?? 'belt', hull)].name}`, () => {
      begin(suggestedHull(current.cause ?? 'belt', hull), seed)
    }),
  )
  if (current.outcome === 'clear') ear.win()
  else ear.die()
}

function hear(current: World): void {
  if (current.shots.length > heardShots) ear.shot()
  heardShots = current.shots.length
  if (current.booms.length > heardBooms) ear.boom()
  heardBooms = current.booms.length
}

function endButton(label: string, onClick: () => void): HTMLButtonElement {
  const button = document.createElement('button')
  button.type = 'button'
  button.textContent = label
  button.addEventListener('click', onClick)
  return button
}

function bar(kind: string, value: number, max: number): HTMLElement {
  const row = document.createElement('div')
  row.className = `bar ${kind}`
  const fill = document.createElement('span')
  fill.style.width = `${max <= 0 ? 0 : Math.max(0, Math.min(100, (value / max) * 100))}%`
  row.append(fill)
  return row
}

function propLabel(current: World): string {
  if (current.fit.prop === 'none') return 'no prop'
  const name = current.fit.prop === 'ab' ? 'afterburner' : 'microwarpdrive'
  const utility = current.fit.utility === 'none' ? '' : ` · ${current.fit.utility}`
  return `${name} ${current.fit.propOn ? 'on' : 'off'}${utility}`
}

function fitLine(current: World): string {
  const parts = current.fit.families.map((family) => familyName(family))
  if (current.fit.prop !== 'none') parts.push(current.fit.prop === 'ab' ? 'Afterburner' : 'Microwarpdrive')
  if (current.fit.utility !== 'none') parts.push(current.fit.utility === 'web' ? 'Web' : 'Painter')
  if (current.fit.tank !== 'none') parts.push(current.fit.tank)
  if (current.fit.evolutions.length > 0) parts.push(current.fit.evolutions.join(' '))
  return parts.join(', ')
}

function orderName(type: World['ships'][number]['order']['type']): string {
  switch (type) {
    case 'manual':
      return 'Manual'
    case 'approach':
      return 'Approach'
    case 'orbit':
      return 'Orbit'
    case 'keep':
      return 'Keep at Range'
    default: {
      const neverType: never = type
      return neverType
    }
  }
}

function causeLine(cause: DeathCause): string {
  switch (cause) {
    case 'scram':
      return 'Scrambled by the Burn. The microwarpdrive cut out.'
    case 'mother':
      return 'Strain Mother was still immune. Her splinters were up.'
    case 'pulse':
      return 'Died inside a smartbomb.'
    case 'escorts':
      return "The Controller's escorts were still repairing."
    case 'belt':
      return 'The belt, not a boss.'
    default: {
      const neverCause: never = cause
      return neverCause
    }
  }
}

function clockText(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  const minutes = Math.floor(safe / 60)
  const remain = safe % 60
  return `${minutes}:${remain.toString().padStart(2, '0')}`
}

function resize(): void {
  const dpr = Math.min(2, window.devicePixelRatio || 1)
  renderer?.resize(canvas.clientWidth, canvas.clientHeight, dpr)
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value))
}
