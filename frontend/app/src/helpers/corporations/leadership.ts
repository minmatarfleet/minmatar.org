import type { CorporationLeadershipMember } from '@dtypes/api.minmatar.org'

// Fleet-time buckets folded to the three zones recruits recognise.
const ZONE_OF: Record<string, 'EU' | 'AU' | 'US'> = {
    EU: 'EU',
    AP: 'AU',
    US: 'US',
    AP_EU: 'EU',
    EU_US: 'US',
    US_AP: 'AU',
}

// Where a leader actually flies, falling back to the zone they declared.
export function prime_codes(member: Pick<CorporationLeadershipMember, 'prime_time' | 'observed_prime_times'>): ('EU' | 'AU' | 'US')[] {
    const source = member.observed_prime_times?.length
        ? member.observed_prime_times
        : member.prime_time ? [member.prime_time] : []
    const zones: ('EU' | 'AU' | 'US')[] = []
    for (const code of source) {
        const zone = ZONE_OF[code]
        if (zone && !zones.includes(zone))
            zones.push(zone)
    }
    return zones
}

