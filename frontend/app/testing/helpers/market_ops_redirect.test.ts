import { describe, expect, it } from 'vitest'

import type { Location } from '@dtypes/api.minmatar.org'
import {
    AMAMAKE_LOCATION_ID,
    R_6KYM_2_LOCATION_ID,
    find_location_by_query,
    has_ops_deep_link_params,
    ops_params_need_canonicalization,
    ops_redirect_path,
    ops_redirect_target,
    resolve_ops_location_id,
} from '@helpers/market_ops_redirect'

const locations: Location[] = [
    {
        location_id: AMAMAKE_LOCATION_ID,
        location_name: 'Amamake - 5 times nearly AT winners',
        short_name: 'Amamake',
        solar_system_id: 1,
        solar_system_name: 'Amamake',
        region_id: null,
        market_active: true,
        prices_active: true,
        freight_active: true,
        staging_active: true,
    },
    {
        location_id: R_6KYM_2_LOCATION_ID,
        location_name: 'R-6KYM - Casper Anchored It',
        short_name: 'R-6KYM',
        solar_system_id: 2,
        solar_system_name: 'R-6KYM',
        region_id: null,
        market_active: true,
        prices_active: true,
        freight_active: true,
        staging_active: true,
    },
]

describe('market_ops_redirect', () => {
    it('resolves location_id param', () => {
        const params = new URLSearchParams({ location_id: String(R_6KYM_2_LOCATION_ID) })
        expect(resolve_ops_location_id(locations, params)).toBe(R_6KYM_2_LOCATION_ID)
    })

    it('resolves full location_name param', () => {
        const params = new URLSearchParams({
            location_name: 'Amamake - 5 times nearly AT winners',
        })
        expect(resolve_ops_location_id(locations, params)).toBe(AMAMAKE_LOCATION_ID)
    })

    it('resolves staging slug aliases', () => {
        expect(
            resolve_ops_location_id(locations, new URLSearchParams({ location_name: 'r6_2' })),
        ).toBe(R_6KYM_2_LOCATION_ID)
        expect(
            resolve_ops_location_id(locations, new URLSearchParams({ location_name: 'amamake' })),
        ).toBe(AMAMAKE_LOCATION_ID)
    })

    it('resolves short_name param', () => {
        const params = new URLSearchParams({ location_name: 'R-6KYM' })
        expect(find_location_by_query(locations, params)?.location_id).toBe(R_6KYM_2_LOCATION_ID)
    })

    it('prefers valid location_id over location_name', () => {
        const params = new URLSearchParams({
            location_id: String(R_6KYM_2_LOCATION_ID),
            location_name: 'Amamake - 5 times nearly AT winners',
        })
        expect(resolve_ops_location_id(locations, params)).toBe(R_6KYM_2_LOCATION_ID)
    })

    it('detects stale deep-link params', () => {
        expect(has_ops_deep_link_params(new URLSearchParams({ location_name: 'amamake' }))).toBe(true)
        expect(has_ops_deep_link_params(new URLSearchParams({ doctrine_id: '12' }))).toBe(true)
        expect(has_ops_deep_link_params(new URLSearchParams())).toBe(false)
    })

    it('requires canonicalization for stale params', () => {
        expect(
            ops_params_need_canonicalization(
                new URLSearchParams({
                    location_name: 'Amamake - 5 times nearly AT winners',
                    doctrine_id: '12',
                }),
                AMAMAKE_LOCATION_ID,
            ),
        ).toBe(true)
        expect(
            ops_params_need_canonicalization(
                new URLSearchParams({ location_id: String(AMAMAKE_LOCATION_ID) }),
                AMAMAKE_LOCATION_ID,
            ),
        ).toBe(false)
    })

    it('builds ops redirect paths', () => {
        const translatePath = (path: string) => path
        expect(ops_redirect_path(translatePath, AMAMAKE_LOCATION_ID))
            .toBe(`/market/ops/?location_id=${AMAMAKE_LOCATION_ID}`)
        expect(ops_redirect_path(translatePath)).toBe('/market/ops/')
    })

    it('returns undefined for unrecognized location_id', () => {
        const params = new URLSearchParams({ location_id: '9999999999999' })
        expect(find_location_by_query(locations, params)).toBeUndefined()
        expect(resolve_ops_location_id(locations, params)).toBeUndefined()
    })

    it('returns undefined for invalid location_id param', () => {
        const params = new URLSearchParams({ location_id: 'not-a-number' })
        expect(find_location_by_query(locations, params)).toBeUndefined()
        expect(resolve_ops_location_id(locations, params)).toBeUndefined()
    })

    it('requires canonicalization for invalid location_id param', () => {
        expect(
            ops_params_need_canonicalization(
                new URLSearchParams({ location_id: 'not-a-number' }),
            ),
        ).toBe(true)
    })

    it('redirects unrecognized location_id to default ops page', () => {
        const translatePath = (path: string) => path
        const params = new URLSearchParams({ location_id: '9999999999999' })
        expect(ops_redirect_target(translatePath, locations, params))
            .toBe('/market/ops/')
    })

    it('redirects invalid location_id to default ops page', () => {
        const translatePath = (path: string) => path
        const params = new URLSearchParams({ location_id: 'not-a-number' })
        expect(ops_redirect_target(translatePath, locations, params))
            .toBe('/market/ops/')
    })

    it('redirects resolved location_id to canonical ops deep link', () => {
        const translatePath = (path: string) => path
        const params = new URLSearchParams({ location_id: String(AMAMAKE_LOCATION_ID) })
        expect(ops_redirect_target(translatePath, locations, params))
            .toBe(`/market/ops/?location_id=${AMAMAKE_LOCATION_ID}`)
    })
})
