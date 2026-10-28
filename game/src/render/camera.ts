export interface Vec3 {
  x: number
  y: number
  z: number
}

export interface Camera {
  eye: Vec3
  target: Vec3
  fov: number
  aspect: number
  near: number
  far: number
}

export function followCamera(shipX: number, shipY: number, heading: number, aspect: number): Camera {
  const back = 22_000
  const height = 14_000
  return {
    eye: {
      x: shipX - Math.cos(heading) * back,
      y: height,
      z: shipY - Math.sin(heading) * back,
    },
    target: { x: shipX + Math.cos(heading) * 2_500, y: 0, z: shipY + Math.sin(heading) * 2_500 },
    fov: 0.78,
    aspect,
    near: 200,
    far: 400_000,
  }
}

export function basis(camera: Camera): { right: Vec3; up: Vec3; forward: Vec3 } {
  const forward = normalize({
    x: camera.target.x - camera.eye.x,
    y: camera.target.y - camera.eye.y,
    z: camera.target.z - camera.eye.z,
  })
  const worldUp = { x: 0, y: 1, z: 0 }
  const right = normalize(cross(forward, worldUp))
  const up = cross(right, forward)
  return { right, up, forward }
}

export function viewProjection(camera: Camera): Float32Array {
  return multiply(perspective(camera.fov, camera.aspect, camera.near, camera.far), lookAt(camera.eye, camera.target))
}

export function project(camera: Camera, x: number, y: number, z: number, width: number, height: number): { x: number; y: number; depth: number } | null {
  const clip = transform(viewProjection(camera), x, y, z, 1)
  if (clip[3] <= 0) return null
  const ndcX = clip[0] / clip[3]
  const ndcY = clip[1] / clip[3]
  return {
    x: (ndcX * 0.5 + 0.5) * width,
    y: (1 - (ndcY * 0.5 + 0.5)) * height,
    depth: clip[2] / clip[3],
  }
}

export function groundAt(camera: Camera, screenX: number, screenY: number, width: number, height: number): { x: number; y: number } | null {
  const ndcX = (screenX / width) * 2 - 1
  const ndcY = 1 - (screenY / height) * 2
  const { right, up, forward } = basis(camera)
  const tan = Math.tan(camera.fov / 2)
  const dir = normalize({
    x: forward.x + right.x * ndcX * tan * camera.aspect + up.x * ndcY * tan,
    y: forward.y + right.y * ndcX * tan * camera.aspect + up.y * ndcY * tan,
    z: forward.z + right.z * ndcX * tan * camera.aspect + up.z * ndcY * tan,
  })
  if (dir.y >= -0.0001) return null
  const t = -camera.eye.y / dir.y
  return { x: camera.eye.x + dir.x * t, y: camera.eye.z + dir.z * t }
}

function lookAt(eye: Vec3, target: Vec3): Float32Array {
  const z = normalize({ x: eye.x - target.x, y: eye.y - target.y, z: eye.z - target.z })
  const x = normalize(cross({ x: 0, y: 1, z: 0 }, z))
  const y = cross(z, x)
  return new Float32Array([
    x.x, y.x, z.x, 0,
    x.y, y.y, z.y, 0,
    x.z, y.z, z.z, 0,
    -dot(x, eye), -dot(y, eye), -dot(z, eye), 1,
  ])
}

function perspective(fov: number, aspect: number, near: number, far: number): Float32Array {
  const f = 1 / Math.tan(fov / 2)
  const rangeInv = 1 / (near - far)
  return new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, far * rangeInv, -1,
    0, 0, near * far * rangeInv, 0,
  ])
}

function multiply(a: Float32Array, b: Float32Array): Float32Array {
  const out = new Float32Array(16)
  for (let col = 0; col < 4; col += 1) {
    for (let row = 0; row < 4; row += 1) {
      out[col * 4 + row] =
        a[row] * b[col * 4] +
        a[4 + row] * b[col * 4 + 1] +
        a[8 + row] * b[col * 4 + 2] +
        a[12 + row] * b[col * 4 + 3]
    }
  }
  return out
}

function transform(matrix: Float32Array, x: number, y: number, z: number, w: number): [number, number, number, number] {
  return [
    matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12] * w,
    matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13] * w,
    matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14] * w,
    matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15] * w,
  ]
}

function cross(a: Vec3, b: Vec3): Vec3 {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x }
}

function dot(a: Vec3, b: Vec3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z
}

function normalize(v: Vec3): Vec3 {
  const length = Math.hypot(v.x, v.y, v.z) || 1
  return { x: v.x / length, y: v.y / length, z: v.z / length }
}
