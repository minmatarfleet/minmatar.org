import { describe, expect, it } from 'vitest'
import {
    alliance_health_href,
    alliance_health_section_hash,
    parse_alliance_health_bucket,
    read_alliance_health_list_state,
    write_alliance_health_list_params,
    patch_from_alliance_health_params,
} from '@helpers/alliance_health_url'

describe('alliance_health_url', () => {
    it('falls back to the default bucket', () => {
        expect(parse_alliance_health_bucket('trials', 'nope')).toBe('current')
        expect(parse_alliance_health_bucket('trials', 'passing')).toBe('passing')
    })

    it('omits defaults from the query string', () => {
        const params = new URLSearchParams()
        write_alliance_health_list_params(
            params,
            'trials',
            {
                bucket: 'current',
                corp: 'all',
                q: '',
                by: 'fleets',
                dir: 'desc',
                page: 1,
            },
            { bucket: 'current', corp: 'all', by: 'fleets', dir: 'desc', page: 1 },
        )
        expect(params.toString()).toBe('')
    })

    it('writes non-default filters and buckets', () => {
        const params = new URLSearchParams()
        write_alliance_health_list_params(
            params,
            'trials',
            {
                bucket: 'passing',
                corp: 'FOSFO',
                q: 'bob',
                by: 'name',
                dir: 'asc',
                page: 2,
            },
            { bucket: 'current', corp: 'all', by: 'fleets', dir: 'desc', page: 1 },
        )
        expect(read_alliance_health_list_state(params, 'trials', {
            bucket: 'current',
            corp: 'all',
            by: 'fleets',
            dir: 'desc',
            page: 1,
        })).toEqual({
            bucket: 'passing',
            corp: 'FOSFO',
            q: 'bob',
            by: 'name',
            dir: 'asc',
            page: 2,
        })
        expect(alliance_health_href('/alliance/health', params, alliance_health_section_hash('trials'))).toBe(
            '/alliance/health?trials=passing&trials_corp=FOSFO&trials_q=bob&trials_by=name&trials_dir=asc&trials_p=2#health-trials',
        )
    })

    it('only reports params that are actually in the URL', () => {
        const params = new URLSearchParams('trials=passing&onboarding_corp=FOSFO')
        expect(patch_from_alliance_health_params(params, 'trials')).toEqual({
            bucket: 'passing',
        })
        expect(patch_from_alliance_health_params(params, 'onboarding')).toEqual({
            corp: 'FOSFO',
        })
        expect(patch_from_alliance_health_params(params, 'leave')).toEqual({})
    })

    it('clears a stale page when switching buckets', () => {
        const params = new URLSearchParams('trials_p=2')
        write_alliance_health_list_params(
            params,
            'trials',
            { bucket: 'passing', page: 1 },
            { bucket: 'current', page: 1 },
        )
        expect(params.get('trials')).toBe('passing')
        expect(params.has('trials_p')).toBe(false)
    })
})
