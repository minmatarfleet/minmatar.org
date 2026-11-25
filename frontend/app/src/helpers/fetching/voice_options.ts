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

/**
 * The voice channel and Mumble access from the fleet form. Only the picked
 * option's fields are enabled, so only they post. A field that didn't post
 * (no channel list, Discord unreachable) is left out, so the API keeps the
 * fleet's value; it drops a channel itself when the option changes.
 */
export function posted_voice_fields(data:FormData): { voice_channel_id?: string | null, mumble_open?: boolean } {
    const fields: { voice_channel_id?: string | null, mumble_open?: boolean } = {}
    if (data.has('voice_channel_id'))
        fields.voice_channel_id = String(data.get('voice_channel_id')) || null
    if (data.has('mumble_open'))
        fields.mumble_open = data.get('mumble_open') === 'open'
    return fields
}
