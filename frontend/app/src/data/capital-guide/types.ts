export type CapitalTier = 'S' | 'C' | 'LC'

export const capitalTierLabels: Record<CapitalTier, string> = {
    S: 'Top tier',
    C: 'Common',
    LC: 'Less common',
}

export type GuideSection = {
    id: string
    title: string
    shortTitle?: string
    group?: string
}

export type CapitalHull = {
    id: string
    name: string
    shortName: string
    shipId: number
}

export type TierRow = {
    tier: string
    hullIds: string[]
    badge?: string
    label?: string
}

export type TierList = {
    id: string
    title: string
    lead: string
    rows: TierRow[]
}

export type MetaBlock =
    | { type: 'paragraph'; html: string }
    | { type: 'quote'; text: string }
    | { type: 'list'; items: string[] }
    | {
        type: 'table'
        headers: [string, string]
        rows: { cells: [string, string]; ship_id?: number }[]
    }

export type CrosstrainingRow = {
    capitals: string
    ships: readonly string[]
}

export type CapitalSkillPlan = {
    id: string
    title: string
    skills: readonly string[]
    copy_label: string
}

export type GuideInfoTable = {
    id: string
    title: string
    lead?: string
    headers: readonly string[]
    rows: readonly (readonly string[])[]
}
