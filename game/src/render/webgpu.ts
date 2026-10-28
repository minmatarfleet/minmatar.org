/// <reference types="@webgpu/types" />
import { followCamera, viewProjection } from './camera.ts'
import { gather, rockGlyphs, type Glyph, type Rock } from './scene.ts'
import type { World } from '../sim/world.ts'

export interface Frame {
  name: 'webgpu' | 'canvas'
  resize: (width: number, height: number, dpr: number) => void
  draw: (world: World, rocks: Rock[], width: number, height: number) => void
}

const SHADER = /* wgsl */ `
struct Camera {
  viewProj: mat4x4<f32>,
}
@group(0) @binding(0) var<uniform> camera: Camera;

struct VsOut {
  @builtin(position) clip: vec4<f32>,
  @location(0) color: vec4<f32>,
  @location(1) lit: f32,
}

@vertex
fn vs(
  @location(0) pos: vec3<f32>,
  @location(1) world: vec4<f32>,
  @location(2) tint: vec4<f32>,
) -> VsOut {
  let c = cos(world.z);
  let s = sin(world.z);
  let p = pos * world.w;
  let rx = p.x * c - p.z * s;
  let rz = p.x * s + p.z * c;
  var out: VsOut;
  out.clip = camera.viewProj * vec4<f32>(world.x + rx, p.y, world.y + rz, 1.0);
  out.color = tint;
  out.lit = pos.y * 0.5 + 0.55;
  return out;
}

@fragment
fn fsOpaque(input: VsOut) -> @location(0) vec4<f32> {
  return vec4<f32>(input.color.rgb * clamp(input.lit, 0.35, 1.15), input.color.a);
}

@fragment
fn fsAdd(input: VsOut) -> @location(0) vec4<f32> {
  return input.color;
}
`

export async function createGpuRenderer(canvas: HTMLCanvasElement): Promise<Frame | null> {
  if (!navigator.gpu) return null
  const adapter = await navigator.gpu.requestAdapter()
  if (!adapter) return null
  const device = await adapter.requestDevice()
  const context = canvas.getContext('webgpu')
  if (!context) return null
  const format = navigator.gpu.getPreferredCanvasFormat()
  let width = 1
  let height = 1
  let depth: GPUTexture | null = null

  function configure(): void {
    context!.configure({ device, format, alphaMode: 'opaque' })
    depth?.destroy()
    depth = device.createTexture({
      size: { width: canvas.width, height: canvas.height },
      format: 'depth24plus',
      usage: GPUTextureUsage.RENDER_ATTACHMENT,
    })
  }

  const shader = device.createShaderModule({ code: SHADER })
  const compiled = await shader.getCompilationInfo()
  if (compiled.messages.some((message) => message.type === 'error')) {
    throw new Error(compiled.messages.map((message) => message.message).join('\n'))
  }
  const uniform = device.createBuffer({ size: 64, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST })
  const bindLayout = bindLayoutOf(device)
  const bind = device.createBindGroup({
    layout: bindLayout,
    entries: [{ binding: 0, resource: { buffer: uniform } }],
  })
  const pipelineLayout = device.createPipelineLayout({ bindGroupLayouts: [bindLayout] })
  const meshes = {
    ship: meshBuffer(device, shipMesh()),
    rock: meshBuffer(device, rockMesh()),
    shot: meshBuffer(device, streakMesh()),
    flame: meshBuffer(device, flameMesh()),
    ring: meshBuffer(device, ringMesh()),
    sphere: meshBuffer(device, sphereMesh()),
  }
  const capacity = 256
  const instanceBuffers = {
    opaque: instanceBuffer(device, capacity),
    alpha: instanceBuffer(device, capacity),
    add: instanceBuffer(device, capacity),
  }
  const opaquePipe = pipeline(device, shader, format, pipelineLayout, true, 'opaque')
  const addPipe = pipeline(device, shader, format, pipelineLayout, false, 'add')
  const alphaPipe = pipeline(device, shader, format, pipelineLayout, false, 'alpha')

  function drawGlyphs(pass: GPURenderPassEncoder, pipe: GPURenderPipeline, glyphs: Glyph[], instances: GPUBuffer): void {
    if (glyphs.length === 0) return
    const groups = new Map<Glyph['mesh'], Glyph[]>()
    for (const glyph of glyphs.slice(0, capacity)) {
      const list = groups.get(glyph.mesh) ?? []
      list.push(glyph)
      groups.set(glyph.mesh, list)
    }
    const ordered: Glyph[] = []
    const ranges: { mesh: Glyph['mesh']; start: number; count: number }[] = []
    for (const [mesh, list] of groups) {
      ranges.push({ mesh, start: ordered.length, count: list.length })
      ordered.push(...list)
    }
    const data = new Float32Array(ordered.length * 8)
    ordered.forEach((glyph, index) => {
      const offset = index * 8
      data[offset] = glyph.x
      data[offset + 1] = glyph.z
      data[offset + 2] = glyph.heading
      data[offset + 3] = glyph.scale
      data[offset + 4] = glyph.rgba[0]
      data[offset + 5] = glyph.rgba[1]
      data[offset + 6] = glyph.rgba[2]
      data[offset + 7] = glyph.rgba[3]
    })
    upload(device, instances, data)
    pass.setPipeline(pipe)
    pass.setBindGroup(0, bind)
    for (const range of ranges) {
      pass.setVertexBuffer(0, meshes[range.mesh].buffer)
      pass.setVertexBuffer(1, instances)
      pass.draw(meshes[range.mesh].count, range.count, 0, range.start)
    }
  }

  return {
    name: 'webgpu',
    resize(cssWidth, cssHeight, dpr) {
      width = cssWidth
      height = cssHeight
      canvas.width = Math.max(1, Math.floor(cssWidth * dpr))
      canvas.height = Math.max(1, Math.floor(cssHeight * dpr))
      configure()
    },
    draw(world, rocks) {
      if (!depth) return
      const me = world.ships.find((ship) => ship.role === 'player')
      const camera = followCamera(me?.x ?? 0, me?.y ?? 0, me?.heading ?? 0, width / height)
      upload(device, uniform, viewProjection(camera))
      const scene = gather(world)
      const encoder = device.createCommandEncoder()
      const view = context!.getCurrentTexture().createView()
      const pass = encoder.beginRenderPass({
        colorAttachments: [{
          view,
          clearValue: { r: 0.035, g: 0.04, b: 0.055, a: 1 },
          loadOp: 'clear',
          storeOp: 'store',
        }],
        depthStencilAttachment: {
          view: depth.createView(),
          depthClearValue: 1,
          depthLoadOp: 'clear',
          depthStoreOp: 'store',
        },
      })
      drawGlyphs(pass, opaquePipe, [...rockGlyphs(rocks), ...scene.opaque], instanceBuffers.opaque)
      drawGlyphs(pass, alphaPipe, scene.alpha, instanceBuffers.alpha)
      drawGlyphs(pass, addPipe, scene.add, instanceBuffers.add)
      pass.end()
      device.queue.submit([encoder.finish()])
    },
  }
}

function upload(device: GPUDevice, buffer: GPUBuffer, data: Float32Array): void {
  device.queue.writeBuffer(buffer, 0, data.buffer as ArrayBuffer, data.byteOffset, data.byteLength)
}

function instanceBuffer(device: GPUDevice, capacity: number): GPUBuffer {
  return device.createBuffer({
    size: capacity * 32,
    usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST,
  })
}

function bindLayoutOf(device: GPUDevice): GPUBindGroupLayout {
  return device.createBindGroupLayout({
    entries: [{ binding: 0, visibility: GPUShaderStage.VERTEX, buffer: { type: 'uniform' } }],
  })
}

function pipeline(
  device: GPUDevice,
  shader: GPUShaderModule,
  format: GPUTextureFormat,
  layout: GPUPipelineLayout,
  depthWrite: boolean,
  pass: 'opaque' | 'add' | 'alpha',
): GPURenderPipeline {
  const blend: GPUBlendState | undefined = pass === 'opaque'
    ? undefined
    : pass === 'add'
      ? {
          color: { srcFactor: 'src-alpha', dstFactor: 'one', operation: 'add' },
          alpha: { srcFactor: 'one', dstFactor: 'one', operation: 'add' },
        }
      : {
          color: { srcFactor: 'src-alpha', dstFactor: 'one-minus-src-alpha', operation: 'add' },
          alpha: { srcFactor: 'one', dstFactor: 'one-minus-src-alpha', operation: 'add' },
        }
  return device.createRenderPipeline({
    layout,
    vertex: {
      module: shader,
      entryPoint: 'vs',
      buffers: [
        { arrayStride: 12, attributes: [{ shaderLocation: 0, offset: 0, format: 'float32x3' }] },
        {
          arrayStride: 32,
          stepMode: 'instance',
          attributes: [
            { shaderLocation: 1, offset: 0, format: 'float32x4' },
            { shaderLocation: 2, offset: 16, format: 'float32x4' },
          ],
        },
      ],
    },
    fragment: {
      module: shader,
      entryPoint: pass === 'opaque' ? 'fsOpaque' : 'fsAdd',
      targets: [{ format, blend }],
    },
    primitive: { topology: 'triangle-list', cullMode: 'none' },
    depthStencil: { format: 'depth24plus', depthWriteEnabled: depthWrite, depthCompare: 'less' },
  })
}

function meshBuffer(device: GPUDevice, data: Float32Array): { buffer: GPUBuffer; count: number } {
  const buffer = device.createBuffer({ size: data.byteLength, usage: GPUBufferUsage.VERTEX | GPUBufferUsage.COPY_DST })
  upload(device, buffer, data)
  return { buffer, count: data.length / 3 }
}

function shipMesh(): Float32Array {
  const nose: Vec = [1.7, 0.12, 0]
  const left: Vec = [-1.05, 0.08, 0.72]
  const right: Vec = [-1.05, 0.08, -0.72]
  const top: Vec = [-0.35, 0.5, 0]
  const belly: Vec = [-0.15, -0.28, 0]
  return tris([
    [nose, left, top],
    [nose, top, right],
    [nose, belly, left],
    [nose, right, belly],
    [top, left, right],
    [belly, right, left],
  ])
}

function rockMesh(): Float32Array {
  const pts: Vec[] = [
    [0, 0.7, 0],
    [0.9, 0.1, 0.2],
    [0.1, 0, 0.85],
    [-0.8, 0.15, 0.3],
    [-0.2, 0.05, -0.9],
    [0.2, -0.65, 0.1],
  ]
  return tris([
    [pts[0]!, pts[1]!, pts[2]!],
    [pts[0]!, pts[2]!, pts[3]!],
    [pts[0]!, pts[3]!, pts[4]!],
    [pts[0]!, pts[4]!, pts[1]!],
    [pts[5]!, pts[2]!, pts[1]!],
    [pts[5]!, pts[3]!, pts[2]!],
    [pts[5]!, pts[4]!, pts[3]!],
    [pts[5]!, pts[1]!, pts[4]!],
  ])
}

function streakMesh(): Float32Array {
  const nose: Vec = [1.5, 0, 0]
  const up: Vec = [0, 0.08, 0]
  const side: Vec = [0, 0, 0.08]
  const tail: Vec = [-0.3, 0, 0]
  const down: Vec = [0, -0.08, 0]
  const other: Vec = [0, 0, -0.08]
  return tris([
    [nose, up, side],
    [nose, side, down],
    [nose, down, other],
    [nose, other, up],
    [tail, side, up],
    [tail, down, side],
    [tail, other, down],
    [tail, up, other],
  ])
}

function flameMesh(): Float32Array {
  return tris([
    [[0.2, 0, 0], [-1.3, 0.25, 0.25], [-1.3, 0.25, -0.25]],
    [[0.2, 0, 0], [-1.3, -0.1, 0.2], [-1.3, -0.1, -0.2]],
  ])
}

function ringMesh(): Float32Array {
  const segments = 48
  const inner = 0.96
  const positions: number[] = []
  for (let i = 0; i < segments; i += 1) {
    const a0 = (i / segments) * Math.PI * 2
    const a1 = ((i + 1) / segments) * Math.PI * 2
    const ring: [Vec, Vec, Vec][] = [
      [[Math.cos(a0) * inner, 0, Math.sin(a0) * inner], [Math.cos(a0), 0, Math.sin(a0)], [Math.cos(a1), 0, Math.sin(a1)]],
      [[Math.cos(a0) * inner, 0, Math.sin(a0) * inner], [Math.cos(a1), 0, Math.sin(a1)], [Math.cos(a1) * inner, 0, Math.sin(a1) * inner]],
    ]
    for (const tri of ring) positions.push(...tri.flat())
  }
  return new Float32Array(positions)
}

function sphereMesh(): Float32Array {
  const lat = 6
  const lon = 8
  const point = (i: number, j: number): Vec => {
    const theta = (i / lat) * Math.PI
    const phi = (j / lon) * Math.PI * 2
    return [Math.sin(theta) * Math.cos(phi), Math.cos(theta) * 0.35, Math.sin(theta) * Math.sin(phi)]
  }
  const faces: [Vec, Vec, Vec][] = []
  for (let i = 0; i < lat; i += 1) {
    for (let j = 0; j < lon; j += 1) {
      const a = point(i, j)
      const b = point(i + 1, j)
      const c = point(i, j + 1)
      const d = point(i + 1, j + 1)
      faces.push([a, b, c], [c, b, d])
    }
  }
  return tris(faces)
}

type Vec = [number, number, number]

function tris(faces: [Vec, Vec, Vec][]): Float32Array {
  return new Float32Array(faces.flat(2))
}
