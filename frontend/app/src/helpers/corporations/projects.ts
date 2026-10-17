import type { CorporationProject, CorporationProjectContributor } from '@dtypes/api.minmatar.org'
import type { TagColors } from '@dtypes/layout_components'
import type { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']

export type ProjectAction = 'attach' | 'detach' | 'refresh'

// ESI configuration keys. Anything newer falls back to a readable version of the key.
const KIND_LABELS: Record<string, UiKey> = {
    capture_fw_complex: 'corporations.projects.kind.capture_fw_complex',
    defend_fw_complex: 'corporations.projects.kind.defend_fw_complex',
    destroy_ship: 'corporations.projects.kind.destroy_ship',
    lost_ship: 'corporations.projects.kind.lost_ship',
    damage_ship: 'corporations.projects.kind.damage_ship',
    destroy_npc: 'corporations.projects.kind.destroy_npc',
    earn_loyalty_point: 'corporations.projects.kind.earn_loyalty_point',
    deliver_item: 'corporations.projects.kind.deliver_item',
    manufacture_item: 'corporations.projects.kind.manufacture_item',
    mine_material: 'corporations.projects.kind.mine_material',
    remote_boost_shield: 'corporations.projects.kind.remote_boost_shield',
    remote_repair_armor: 'corporations.projects.kind.remote_repair_armor',
    salvage_wreck: 'corporations.projects.kind.salvage_wreck',
    scan_signature: 'corporations.projects.kind.scan_signature',
    ship_insurance: 'corporations.projects.kind.ship_insurance',
    manual: 'corporations.projects.kind.manual',
}

const TARGET_LABELS: Record<string, UiKey> = {
    locations: 'corporations.projects.target.locations',
    ships: 'corporations.projects.target.ships',
    factions: 'corporations.projects.target.factions',
    identities: 'corporations.projects.target.identities',
    items: 'corporations.projects.target.items',
    materials: 'corporations.projects.target.materials',
    corporations: 'corporations.projects.target.corporations',
}

const STATE_LABELS: Record<string, UiKey> = {
    Active: 'corporations.projects.state.active',
    Completed: 'corporations.projects.state.completed',
    Closed: 'corporations.projects.state.closed',
    Expired: 'corporations.projects.state.expired',
    Deleted: 'corporations.projects.state.deleted',
}

const STATE_COLORS: Record<string, TagColors> = {
    Active: 'green',
    Completed: 'alliance-blue',
}

function humanize(key: string): string {
    const words = key.replace(/_/g, ' ').trim()
    return words ? words[0].toUpperCase() + words.slice(1) : ''
}

export function project_kind_label(kind: string, t: (key: UiKey) => string): string {
    const key = KIND_LABELS[kind]
    return key ? t(key) : humanize(kind)
}

export function project_target_label(kind: string, t: (key: UiKey) => string): string {
    const key = TARGET_LABELS[kind]
    return key ? t(key) : humanize(kind)
}

export function project_state_label(state: string, t: (key: UiKey) => string): string {
    const key = STATE_LABELS[state]
    return key ? t(key) : humanize(state)
}

/** Grey for anything that has stopped without completing. */
export function project_state_color(state: string): TagColors | string {
    return STATE_COLORS[state] ?? 'border-color'
}

export function project_percent(project: Pick<CorporationProject, 'progress_current' | 'progress_desired'>): number {
    if (!project.progress_desired)
        return 0
    return Math.min(100, Math.max(0, (project.progress_current / project.progress_desired) * 100))
}

/** ISK already paid out to contributors, when ESI reports the reward. */
export function project_isk_paid(project: Pick<CorporationProject, 'reward_initial' | 'reward_remaining'>): number | null {
    if (project.reward_initial == null || project.reward_remaining == null)
        return null
    return Math.max(0, project.reward_initial - project.reward_remaining)
}

/** Each contributor's share of the project's total recorded progress. */
export function contributor_share(row: CorporationProjectContributor, rows: CorporationProjectContributor[]): number {
    const total = rows.reduce((sum, item) => sum + item.contributed, 0)
    return total > 0 ? (row.contributed / total) * 100 : 0
}

export function parse_project_action(value: unknown): ProjectAction | null {
    return value === 'attach' || value === 'detach' || value === 'refresh' ? value : null
}

/** Active first, then the rest, most recently changed first within each. */
export function sort_projects<T extends Pick<CorporationProject, 'state' | 'last_modified'>>(projects: T[]): T[] {
    return [...projects].sort((a, b) => {
        const active = Number(b.state === 'Active') - Number(a.state === 'Active')
        if (active !== 0)
            return active
        return b.last_modified.localeCompare(a.last_modified)
    })
}
