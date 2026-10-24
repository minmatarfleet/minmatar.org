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


export type LeaderTimezones =
    | { kind: 'on_leave' }
    | { kind: 'observed', codes: string[], declared: string | null }
    | { kind: 'declared', code: string }
    | { kind: 'missing' }

// On Leave wins; then where they fleet, then what they declared, then nothing.
// `declared` is only set when it picks one bucket out of several observed.
export function leader_timezones(member: Pick<CorporationLeadershipMember, 'prime_time' | 'observed_prime_times' | 'on_leave'>): LeaderTimezones {
    if (member.on_leave)
        return { kind: 'on_leave' }
    const observed = member.observed_prime_times ?? []
    if (observed.length > 0) {
        const declared = observed.length > 1 && member.prime_time && observed.includes(member.prime_time)
            ? member.prime_time
            : null
        return { kind: 'observed', codes: observed, declared }
    }
    if (member.prime_time)
        return { kind: 'declared', code: member.prime_time }
    return { kind: 'missing' }
}
