import type {
    IntelAffiliation,
    IntelEntityKind,
    IntelRelation,
} from '@dtypes/api.minmatar.org'
import type { TranslationKey } from '@helpers/i18n'
import type { EvEImageServiceSize } from '@dtypes/layout_components'
import { get_alliance_logo, get_corporation_logo, get_player_icon } from '@helpers/eve_image_server'

/**
 * View helpers for the intel affiliation database pages: the enums the API
 * accepts, paths, images, and the plain-English "why" line built from an
 * affiliation's evidence.
 */

export const INTEL_RELATIONS: IntelRelation[] = ['pet', 'alt', 'ally', 'associate', 'member']
export const INTEL_ENTITY_KINDS: IntelEntityKind[] = ['alliance', 'corporation', 'character']
/** Affiliation statuses, plus `ended` (a live row with no evidence for six months). */
export const INTEL_AFFILIATION_STATUSES = ['suggested', 'confirmed', 'rejected'] as const
/** Investigation status of an alliance, corporation or character. */
export const INTEL_ENTITY_STATUSES = ['new', 'queued', 'investigating', 'done', 'failed'] as const

export type IntelDecisionStatus = 'confirmed' | 'rejected'

export const parse_entity_kind = (value: string | null | undefined): IntelEntityKind | null =>
    INTEL_ENTITY_KINDS.find((kind) => kind === value) ?? null

export const parse_relation = (value: string | null | undefined): IntelRelation | null =>
    INTEL_RELATIONS.find((relation) => relation === value) ?? null

export const parse_decision = (value: string | null | undefined): IntelDecisionStatus | null =>
    value === 'confirmed' || value === 'rejected' ? value : null

/** A positive integer id from a query or form value, or null. */
export function parse_id(value: FormDataEntryValue | string | null | undefined): number | null {
    if (typeof value !== 'string' || !/^\d+$/.test(value.trim()))
        return null
    const id = parseInt(value, 10)
    return id > 0 ? id : null
}

export const is_group_kind = (kind: string) => kind === 'alliance' || kind === 'corporation'

export function intel_entity_image(kind: string, id: number, size: EvEImageServiceSize = 32): string {
    if (kind === 'character') return get_player_icon(id, size)
    if (kind === 'corporation') return get_corporation_logo(id, size)
    return get_alliance_logo(id, size)
}

export const intel_entity_path = (kind: string, id: number) => `/intel/affiliations/${kind}/${id}/`
export const intel_bloc_path = (id: number) => `/intel/affiliations/blocs/${id}/`

/** 0.202 -> "20%", 0.019 -> "1.9%", 0.0004 -> "<0.1%". */
export function format_share(share: number | null | undefined): string {
    if (share === null || share === undefined || !Number.isFinite(share))
        return '–'
    const percent = share * 100
    if (percent > 0 && percent < 0.1) return '<0.1%'
    return `${percent >= 10 ? Math.round(percent) : Number(percent.toFixed(1))}%`
}

/** "2025-11-01" -> "2025-11". */
export const format_month = (month: string | null | undefined): string => (month ? month.slice(0, 7) : '')

/** "2025-11" or "2025-11 – 2026-10", empty when neither end is known. */
export function format_month_span(first: string | null | undefined, last: string | null | undefined): string {
    const from = format_month(first)
    const to = format_month(last)
    if (!from || !to) return from || to
    return from === to ? from : `${from} – ${to}`
}

export const fill = (template: string, values: Record<string, string | number>): string =>
    template.replace(/\{(\w+)\}/g, (match, key) => (key in values ? String(values[key]) : match))

type Translate = (key: TranslationKey) => string

const number_of = (value: unknown): number | null =>
    typeof value === 'number' && Number.isFinite(value) ? value : null

/**
 * Why the database links a subject to its bloc, as short clauses to join
 * with " · ", e.g. "Snuffed Out on 20% of its kills · together 12 of its 12
 * active months · it's 1.9% of Snuffed Out's kills · 429 kills together".
 * Hand-made rows have no evidence and say so.
 */
export function affiliation_why(affiliation: Pick<IntelAffiliation, 'evidence' | 'entity' | 'bloc' | 'source'>, t: Translate): string[] {
    const evidence = (affiliation.evidence ?? {}) as Record<string, unknown>
    const parts: string[] = []

    if (typeof evidence.partner_name === 'string' || evidence.partner) {
        const partner = typeof evidence.partner_name === 'string' && evidence.partner_name ? evidence.partner_name : affiliation.bloc.name
        const share = number_of(evidence.share)
        const months_together = number_of(evidence.months_together)
        const months_active = number_of(evidence.months_active)
        const reverse_share = number_of(evidence.reverse_share)
        const shared = number_of(evidence.shared)
        const against = number_of(evidence.against)
        const militia_shared = number_of(evidence.militia_shared)

        if (share !== null)
            parts.push(fill(t('intel.affiliations.why.share'), { partner, share: format_share(share) }))
        if (months_together !== null)
            parts.push(months_active !== null ?
                fill(t('intel.affiliations.why.months'), { months: months_together, active: months_active }) :
                fill(t('intel.affiliations.why.months_only'), { months: months_together }))
        if (reverse_share !== null)
            parts.push(fill(t('intel.affiliations.why.reverse'), { partner, share: format_share(reverse_share) }))
        if (shared !== null)
            parts.push(fill(t('intel.affiliations.why.shared'), { count: shared }))
        if (against)
            parts.push(fill(t('intel.affiliations.why.against'), { count: against }))
        if (militia_shared)
            parts.push(fill(t('intel.affiliations.why.militia'), { count: militia_shared }))
        if (typeof evidence.member_since === 'string' && evidence.member_since)
            parts.push(fill(t('intel.affiliations.why.member_since'), { partner, date: evidence.member_since.slice(0, 10) }))
        return parts
    }

    const shared = number_of(evidence.shared)
    if (shared !== null) {
        const months = number_of(evidence.months_together) ?? 0
        parts.push(fill(t('intel.affiliations.why.associate'), { count: shared, bloc: affiliation.bloc.name, months }))
        if ('flies_for' in evidence && evidence.flies_for === null)
            parts.push(t('intel.affiliations.why.npc_corporation'))
        return parts
    }

    if (affiliation.source === 'manual')
        parts.push(t('intel.affiliations.why.manual'))
    return parts
}

export interface BlocAffiliationSections<Row> {
    groups:     Row[];
    associates: Row[];
    suggested:  Row[];
    rejected:   Row[];
    ended:      Row[];
}

/**
 * A bloc's rows by what they mean today: confirmed groups and associates,
 * suggestions waiting for review, rejections (they stick), and former ties
 * with no evidence for six months.
 */
export function bloc_affiliation_sections<Row extends Pick<IntelAffiliation, 'status' | 'ended' | 'entity'>>(rows: Row[]): BlocAffiliationSections<Row> {
    const sections: BlocAffiliationSections<Row> = { groups: [], associates: [], suggested: [], rejected: [], ended: [] }
    for (const row of rows) {
        if (row.status === 'rejected') sections.rejected.push(row)
        else if (row.ended) sections.ended.push(row)
        else if (row.status === 'suggested') sections.suggested.push(row)
        else if (row.entity.kind === 'character') sections.associates.push(row)
        else sections.groups.push(row)
    }
    return sections
}

/** Groups (they move whole rosters) before pilots, keeping the API's order within each. */
export const groups_first = <Row extends { entity: { kind: string } }>(rows: Row[]): Row[] => [
    ...rows.filter((row) => row.entity.kind !== 'character'),
    ...rows.filter((row) => row.entity.kind === 'character'),
]
