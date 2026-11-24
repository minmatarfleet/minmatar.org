import type { FleetVoiceOption } from '@dtypes/api.minmatar.org'
import { get_fleet_voice_options } from '@helpers/api.minmatar.org/voice'

/** The fleet form's voice options. Never fatal: [] hides the picker. */
export async function fetch_voice_options(access_token:string): Promise<FleetVoiceOption[]> {
    try {
        return await get_fleet_voice_options(access_token) ?? []
    } catch (error) {
        console.log(`Voice options unavailable: ${error.message}`)
        return []
    }
}

/** `voice_option_id` from the fleet form, or undefined when it had no picker. */
export function posted_voice_option(data:FormData): number | null | undefined {
    const value = data.get('voice_option_id')
    if (value === null) return undefined
    const parsed = parseInt(String(value))
    return Number.isFinite(parsed) ? parsed : null
}
