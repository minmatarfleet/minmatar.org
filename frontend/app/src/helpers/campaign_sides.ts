/** A campaign's parties grouped by side, for the header and the card. */
import type { CampaignParty } from '@dtypes/api.minmatar.org'
import { get_alliance_logo, get_corporation_logo, get_player_icon } from '@helpers/eve_image_server'

export type CampaignSide = 'enemy' | 'ally' | 'third_party'

export const CAMPAIGN_SIDES: { side: CampaignSide; label_key: 'campaigns.parties.enemies' | 'campaigns.parties.allies' | 'campaigns.parties.third_parties' }[] = [
    { side: 'enemy', label_key: 'campaigns.parties.enemies' },
    { side: 'ally', label_key: 'campaigns.parties.allies' },
    { side: 'third_party', label_key: 'campaigns.parties.third_parties' },
]

/** Against, With and Third parties, in that order. Third parties always shows on the full view so it can be filled. */
export function campaign_sides(parties: CampaignParty[]) {
    return CAMPAIGN_SIDES.map(({ side, label_key }) => ({
        side,
        label_key,
        parties: parties.filter((party) => party.side === side),
    }))
}

/** A short ticker when there is one, else the name. */
export function party_label(party: { ticker?: string | null; name: string }): string {
    const ticker = (party.ticker || '').trim()
    if (ticker && /^[A-Za-z0-9._ -]{2,6}$/.test(ticker))
        return ticker
    return party.name
}

export function party_logo(party: CampaignParty): string | null {
    if (party.alliance_id) return get_alliance_logo(party.alliance_id, 32)
    if (party.corporation_id) return get_corporation_logo(party.corporation_id, 32)
    if (party.character_id) return get_player_icon(party.character_id, 32)
    return null
}
