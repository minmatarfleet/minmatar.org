import { get_system_moons } from '@helpers/api.minmatar.org/moons'
import type { SystemMoon } from '@dtypes/api.minmatar.org'
import type { MoonUI } from '@dtypes/layout_components'

export async function fetch_scanned_moons(access_token, system_name:string) {
    let system_moons:SystemMoon[]

    system_moons = await get_system_moons(access_token, system_name)

    return system_moons.map((moon) => {
        return {
            id: moon.id,
            name: `${moon.system} ${moon.planet} - Moon ${moon.moon}`,
            monthly_revenue: moon.detail?.monthly_revenue,
        } as MoonUI
    })
}