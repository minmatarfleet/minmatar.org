/** 2D top-down geometry shared by the positioning sims. Units are metres. */

export interface Vec2 {
    x: number
    y: number
}

export const vec = (x: number, y: number): Vec2 => ({ x, y })
export const add = (a: Vec2, b: Vec2): Vec2 => ({ x: a.x + b.x, y: a.y + b.y })
export const sub = (a: Vec2, b: Vec2): Vec2 => ({ x: a.x - b.x, y: a.y - b.y })
export const scale = (a: Vec2, k: number): Vec2 => ({ x: a.x * k, y: a.y * k })
export const dot = (a: Vec2, b: Vec2) => a.x * b.x + a.y * b.y
export const length = (a: Vec2) => Math.hypot(a.x, a.y)
export const distance = (a: Vec2, b: Vec2) => length(sub(a, b))

/** Unit vector at `degrees` counter-clockwise from +x (y up). */
export const heading_vector = (degrees: number): Vec2 => {
    const r = (degrees * Math.PI) / 180
    return { x: Math.cos(r), y: Math.sin(r) }
}
