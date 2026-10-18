import type { CharacterEvE, CorporationHistoryEvE } from '@dtypes/api.eveonline'
import { esi_request } from '@helpers/api.eveonline/client'

export async function get_character_by_id(character_id:number) {
    return await esi_request<CharacterEvE>(`/characters/${character_id}`, {
        error: 'Error fetching character',
    })
}

export async function get_corporation_history(character_id:number) {
    return await esi_request<CorporationHistoryEvE[]>(`/characters/${character_id}/corporationhistory/`, {
        error: 'Error fetching corporation history',
    })
}
