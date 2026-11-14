/**
 * Coordinate helpers for the sims' inline SVG pictures. Shared by the Astro
 * frontmatter (static parts) and the Alpine scripts (bound parts), so both
 * draw in the same frame.
 */
import { SIM } from '@helpers/sims/constants'
import { peak_recharge_rate } from '@helpers/sims/capacitor'
import { CAP_CURVE_SECONDS, NEUT_SECONDS, REP_SECONDS } from '@helpers/sims/scenarios'

export interface ChartBox {
    x: number
    y: number
    width: number
    height: number
    x_max: number
    y_max: number
    x_min?: number
    y_min?: number
}

export const chart_x = (box: ChartBox, value: number) => {
    const min = box.x_min ?? 0
    return box.x + ((value - min) / (box.x_max - min)) * box.width
}

export const chart_y = (box: ChartBox, value: number) => {
    const min = box.y_min ?? 0
    return box.y + box.height - ((Math.min(box.y_max, Math.max(min, value)) - min) / (box.y_max - min)) * box.height
}

/** SVG `points` for a polyline through (x, y) pairs. */
export function chart_points(box: ChartBox, points: [number, number][]): string {
    return points.map(([x, y]) => `${chart_x(box, x).toFixed(2)},${chart_y(box, y).toFixed(2)}`).join(' ')
}

/** Axis ticks for a chart: value and position. */
export function ticks(box: ChartBox, axis: 'x' | 'y', step: number) {
    const min = axis === 'x' ? box.x_min ?? 0 : box.y_min ?? 0
    const max = axis === 'x' ? box.x_max : box.y_max
    const out: { value: number, at: number }[] = []
    for (let v = min; v <= max + 1e-9; v += step)
        out.push({ value: Number(v.toFixed(6)), at: axis === 'x' ? chart_x(box, v) : chart_y(box, v) })
    return out
}

/** MJFG: the on-grid panel (km around the fleet) and the landing map. */
export const MJFG_GRID = { cx: 50, cy: 50, per_km: 5.2 }
export const MJFG_MAP = { x0: 104, y0: 4, per_km: 0.42, x_min: -114, y_max: 114 }

export const grid_x = (x_km: number) => MJFG_GRID.cx + x_km * MJFG_GRID.per_km
export const grid_y = (y_km: number) => MJFG_GRID.cy - y_km * MJFG_GRID.per_km
export const map_x = (x_km: number) => MJFG_MAP.x0 + (x_km - MJFG_MAP.x_min) * MJFG_MAP.per_km
export const map_y = (y_km: number) => MJFG_MAP.y0 + (MJFG_MAP.y_max - y_km) * MJFG_MAP.per_km

export const COMPASS = ['east', 'north-east', 'north', 'north-west', 'west', 'south-west', 'south', 'south-east']
export const compass = (degrees: number) => COMPASS[Math.round((((degrees % 360) + 360) % 360) / 45) % 8]

// Chart frames, shared by each sim's frontmatter (axes) and script (bound lines).

const cap_peak = peak_recharge_rate(SIM.guardian_cap_gj, SIM.guardian_cap_recharge_s)
export const CAP_CURVE_BOX: ChartBox = { x: 14, y: 10, width: 76, height: 70, x_max: 100, y_max: Math.ceil(cap_peak / 2) * 2 + 2 }
export const CAP_TRACE_BOX: ChartBox = { x: 114, y: 10, width: 80, height: 70, x_max: CAP_CURVE_SECONDS, y_max: 100 }
export const NEUT_BOX: ChartBox = { x: 16, y: 44, width: 178, height: 44, x_max: NEUT_SECONDS, y_max: 100 }
/** Neut range strip: km to x. */
export const NEUT_STRIP = { x0: 16, per_km: 4.2 }
export const REP_BOX: ChartBox = { x: 16, y: 8, width: 178, height: 74, x_max: REP_SECONDS, y_max: 100 }
export const APPLIED_BOX: ChartBox = { x: 16, y: 8, width: 178, height: 66, x_max: 90, y_max: 100 }
