import { api_request, api_status_is } from '@helpers/api.minmatar.org/client'
import { get_public_api_url } from '@helpers/env'
import type {
    VoiceStatus,
    VoiceConnect,
    VoiceCertificate,
    VoiceFleet,
    FleetVoiceOption,
} from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/voice`

/** The EVE sign-in for /voice (public info only). The browser goes here,
 * so it uses the public API address, not the server-side one. */
export function voice_login_url(redirect_url:string, state:string) {
    return `${get_public_api_url()}/api/voice/login?redirect_url=${encodeURIComponent(redirect_url)}&state=${encodeURIComponent(state)}`
}

/** `token` is a voice session (guest) or a site session (member, who
 * always connects as their main). */
export async function get_voice_status(token:string) {
    return await api_request<VoiceStatus>(`${API_ENDPOINT}/status`, {
        token,
        error: 'Error fetching voice status',
    })
}

export async function post_voice_connect(token:string) {
    return await api_request<VoiceConnect>(`${API_ENDPOINT}/connect`, {
        method: 'POST',
        token,
        error: 'Error connecting to voice',
    })
}

export async function get_voice_certificates(token:string) {
    return await api_request<VoiceCertificate[]>(`${API_ENDPOINT}/certificates`, {
        token,
        error: 'Error fetching voice certificates',
    })
}

export async function delete_voice_certificate(token:string, certificate_id:number) {
    return await api_status_is(`${API_ENDPOINT}/certificates/${certificate_id}`, {
        method: 'DELETE',
        token,
        error: 'Error revoking voice certificate',
    }, 204)
}

export async function get_fleet_voice(token:string, fleet_id:number) {
    return await api_request<VoiceFleet>(`${API_ENDPOINT}/fleets/${fleet_id}`, {
        token,
        error: 'Error fetching fleet voice',
    })
}

export async function post_fleet_co_fc(token:string, fleet_id:number, character_id:number) {
    return await api_status_is(`${API_ENDPOINT}/fleets/${fleet_id}/co-fcs`, {
        method: 'POST',
        token,
        body: { character_id },
        error: 'Error adding co-FC',
    }, 204)
}

export async function delete_fleet_co_fc(token:string, fleet_id:number, character_id:number) {
    return await api_status_is(`${API_ENDPOINT}/fleets/${fleet_id}/co-fcs/${character_id}`, {
        method: 'DELETE',
        token,
        error: 'Error removing co-FC',
    }, 204)
}

export async function post_fleet_wings(token:string, fleet_id:number, wing_channels:Record<string, string>) {
    return await api_status_is(`${API_ENDPOINT}/fleets/${fleet_id}/wings`, {
        method: 'POST',
        token,
        body: { wing_channels },
        error: 'Error saving wings',
    }, 204)
}

export async function post_fleet_kick(token:string, fleet_id:number, character_id:number) {
    return await api_status_is(`${API_ENDPOINT}/fleets/${fleet_id}/kick`, {
        method: 'POST',
        token,
        body: { character_id },
        error: 'Error kicking pilot',
    }, 204)
}

export async function post_voice_ban(token:string, character_id:number, reason:string) {
    return await api_status_is(`${API_ENDPOINT}/bans`, {
        method: 'POST',
        token,
        body: { character_id, reason },
        error: 'Error banning pilot',
    }, 201)
}

export async function get_fleet_voice_options(token:string) {
    return await api_request<FleetVoiceOption[]>(`${import.meta.env.API_URL}/api/fleets/voice-options`, {
        token,
        error: 'Error fetching voice options',
    })
}
