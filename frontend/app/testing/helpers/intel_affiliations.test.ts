import { describe, expect, it } from 'vitest'

import { i18n } from '@helpers/i18n'
import { ui } from '@i18n/ui'
import {
    INTEL_AFFILIATION_STATUSES,
    INTEL_ENTITY_KINDS,
    INTEL_ENTITY_STATUSES,
    INTEL_RELATIONS,
    affiliation_why,
    bloc_affiliation_sections,
    format_month_span,
    format_share,
    groups_first,
    intel_entity_image,
    parse_decision,
    parse_entity_kind,
    parse_id,
    parse_relation,
} from '@helpers/intel_affiliations'

const { t } = i18n(new URL('https://my.minmatar.org/'))
const has_key = (key: string) => Object.prototype.hasOwnProperty.call(ui.en, key)

const bloc = { id: 2, name: 'Snuffed Out', likely: false }

describe('intel affiliation key families', () => {
    it('cover every relation, kind and status the pages render', () => {
        const keys = [
            ...INTEL_RELATIONS.map((value) => `intel.affiliations.relation.${value}`),
            ...INTEL_ENTITY_KINDS.map((value) => `intel.affiliations.kind.${value}`),
            ...INTEL_AFFILIATION_STATUSES.map((value) => `intel.affiliations.status.${value}`),
            ...INTEL_ENTITY_STATUSES.map((value) => `intel.affiliations.entity_status.${value}`),
            ...['groups', 'associates', 'suggested', 'ended', 'rejected'].map((value) => `intel.affiliations.bloc.section.${value}`),
        ]
        expect(keys.filter((key) => !has_key(key))).toEqual([])
    })
})

describe('parsers', () => {
    it('accept only the API enums and positive ids', () => {
        expect(parse_entity_kind('corporation')).toBe('corporation')
        expect(parse_entity_kind('blocs')).toBeNull()
        expect(parse_relation('alt')).toBe('alt')
        expect(parse_relation('friend')).toBeNull()
        expect(parse_decision('rejected')).toBe('rejected')
        expect(parse_decision('suggested')).toBeNull()
        expect(parse_id('99010022')).toBe(99010022)
        expect(parse_id('0')).toBeNull()
        expect(parse_id('12abc')).toBeNull()
        expect(parse_id(null)).toBeNull()
    })
})

describe('formatting', () => {
    it('shows small shares with a decimal and big ones rounded', () => {
        expect(format_share(0.202)).toBe('20%')
        expect(format_share(0.019)).toBe('1.9%')
        expect(format_share(0.05)).toBe('5%')
        expect(format_share(0.0004)).toBe('<0.1%')
        expect(format_share(null)).toBe('–')
    })

    it('spans months', () => {
        expect(format_month_span('2025-11-01', '2026-10-01')).toBe('2025-11 – 2026-10')
        expect(format_month_span('2026-10-01', '2026-10-01')).toBe('2026-10')
        expect(format_month_span(null, '2026-10-01')).toBe('2026-10')
        expect(format_month_span(null, null)).toBe('')
    })

    it('picks the image for each kind', () => {
        expect(intel_entity_image('character', 1, 64)).toContain('/characters/1/portrait')
        expect(intel_entity_image('corporation', 2)).toContain('/corporations/2/logo')
        expect(intel_entity_image('alliance', 3)).toContain('/alliances/3/logo')
    })
})

describe('affiliation_why', () => {
    it('explains a pet in plain English', () => {
        const why = affiliation_why({
            entity: { kind: 'alliance', id: 99010022, name: 'Scary Wormhole People' },
            bloc,
            source: 'inferred',
            evidence: {
                partner: { kind: 'alliance', id: 99004901 },
                partner_name: 'Snuffed Out',
                kills_sampled: 2129,
                shared: 429,
                share: 0.202,
                reverse_share: 0.019,
                months_together: 12,
                months_active: 12,
                months_sampled: 24,
                against: 80,
                militia_shared: 0,
            },
        }, t)
        expect(why.join(' · ')).toBe(
            "Snuffed Out on 20% of its kills · together 12 of its 12 active months · it's 1.9% of Snuffed Out's kills · 429 kills together · 80 shot at each other",
        )
    })

    it('names a former membership', () => {
        const why = affiliation_why({
            entity: { kind: 'corporation', id: 1, name: 'TDSIN' },
            bloc,
            source: 'inferred',
            evidence: { partner_name: 'Snuffed Out', share: 0.3, member_since: '2023-04-02T00:00:00Z' },
        }, t)
        expect(why).toContain('was in Snuffed Out from 2023-04-02')
    })

    it('explains an associate and an NPC-corp pilot', () => {
        const why = affiliation_why({
            entity: { kind: 'character', id: 1, name: 'Pilot' },
            bloc,
            source: 'inferred',
            evidence: { shared: 12, months_together: 5, flies_for: null },
        }, t)
        expect(why).toEqual(['on 12 kills with Snuffed Out across 5 months', 'flies from an NPC corporation'])
    })

    it('says a hand-made row has no evidence', () => {
        expect(affiliation_why({ entity: { kind: 'alliance', id: 1, name: 'A' }, bloc, source: 'manual', evidence: {} }, t))
            .toEqual(['Added by hand'])
    })
})

describe('bloc sections', () => {
    const row = (id: number, kind: string, status: string, ended = false) => ({ id, entity: { kind, id, name: `${id}` }, status, ended })

    it('sorts rows by what they mean today', () => {
        const sections = bloc_affiliation_sections([
            row(1, 'alliance', 'confirmed'),
            row(2, 'character', 'confirmed'),
            row(3, 'corporation', 'suggested'),
            row(4, 'alliance', 'rejected', true),
            row(5, 'alliance', 'confirmed', true),
        ])
        expect(sections.groups.map((r) => r.id)).toEqual([1])
        expect(sections.associates.map((r) => r.id)).toEqual([2])
        expect(sections.suggested.map((r) => r.id)).toEqual([3])
        expect(sections.rejected.map((r) => r.id)).toEqual([4])
        expect(sections.ended.map((r) => r.id)).toEqual([5])
    })

    it('puts groups before pilots', () => {
        expect(groups_first([row(1, 'character', 'suggested'), row(2, 'alliance', 'suggested')]).map((r) => r.id)).toEqual([2, 1])
    })
})
