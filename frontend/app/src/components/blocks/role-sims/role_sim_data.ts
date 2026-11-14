/**
 * Shared Alpine state for the fleet-role simulators: sticky target ticks,
 * the "Beaten" flag in localStorage, Reset, and Alpine.data registration.
 *
 * Every sim keeps its controls in `state`, computes everything from it with a
 * pure scenario function (helpers/sims/scenarios.ts) and reads the result
 * through `r()`. RoleSim.astro calls `track()` from an x-effect, so a target
 * ticks the moment the controls meet it and stays ticked until Reset.
 */
import type { TargetSpec } from '@helpers/sims/scenarios'

export const BEATEN_EVENT = 'fleet-role-sim:beaten'
export const storage_key = (sim_id: string) => `fleet-role-sim:${sim_id}`

export function read_beaten(sim_id: string): boolean {
    try {
        return window.localStorage.getItem(storage_key(sim_id)) === '1'
    } catch {
        return false
    }
}

export function write_beaten(sim_id: string) {
    try {
        window.localStorage.setItem(storage_key(sim_id), '1')
    } catch {
        // Storage blocked (private window, embedded preview): the sim still works.
    }
}

interface RoleSimConfig<S extends object, R extends { met: Record<string, boolean> }> {
    targets: TargetSpec[]
    defaults: () => S
    compute: (state: S) => R
    /** Extra methods (picture helpers). `this` is the Alpine component. */
    methods?: Record<string, (this: any, ...args: any[]) => unknown>
}

export function role_sim_data<S extends object, R extends { met: Record<string, boolean> }>(config: RoleSimConfig<S, R>) {
    return () => {
        // Per-instance memo outside Alpine's reactive proxy, so reading it in
        // several bindings never triggers another render.
        let memo_key = ''
        let memo_value: R | null = null
        const blank = () => Object.fromEntries(config.targets.map((t) => [t.id, false])) as Record<string, boolean>

        return {
            __role_sim: true,
            sim_id: '',
            state: config.defaults(),
            done: blank(),
            beaten: false,
            just_beaten: false,

            init(this: any) {
                this.sim_id = this.$el.dataset.simId ?? ''
                this.beaten = read_beaten(this.sim_id)
            },

            r(this: any): R {
                const key = JSON.stringify(this.state)
                if (key !== memo_key || memo_value === null) {
                    memo_value = config.compute(JSON.parse(key) as S)
                    memo_key = key
                }
                return memo_value
            },

            track(this: any) {
                const met = this.r().met
                for (const target of config.targets)
                    if (met[target.id] && !this.done[target.id]) this.done[target.id] = true
                if (config.targets.every((t) => this.done[t.id]) && !this.just_beaten) {
                    this.just_beaten = true
                    if (!this.beaten) {
                        this.beaten = true
                        write_beaten(this.sim_id)
                    }
                    window.dispatchEvent(new CustomEvent(BEATEN_EVENT, { detail: { id: this.sim_id } }))
                }
            },

            ticked(this: any) {
                return config.targets.filter((t) => this.done[t.id]).length
            },

            reset(this: any) {
                this.state = config.defaults()
                this.done = blank()
                this.just_beaten = false
            },

            ...(config.methods ?? {}),
        }
    }
}

/**
 * Register a sim's Alpine.data factory. Before Alpine starts this waits for
 * `alpine:init`; after a ClientRouter navigation (Alpine already running, the
 * element possibly initialised before this module loaded) it registers and
 * re-initialises any instance that came up without its data.
 */
export function register_role_sim(name: string, factory: () => object) {
    const w = window as any
    if (w.Alpine && typeof w.Alpine.data === 'function') {
        w.Alpine.data(name, factory)
        document.querySelectorAll<HTMLElement>(`[x-data="${name}"]`).forEach((el: any) => {
            if (el._x_dataStack?.[0]?.__role_sim) return
            w.Alpine.destroyTree(el)
            w.Alpine.initTree(el)
        })
        return
    }
    document.addEventListener('alpine:init', () => w.Alpine.data(name, factory), { once: true })
}
