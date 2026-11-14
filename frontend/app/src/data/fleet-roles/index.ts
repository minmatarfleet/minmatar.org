import type { FleetRoleGuide, FleetRoleSlug, RoleSimId } from './types'
import { damage } from './damage'
import { remote_repair } from './remote-repair'
import { capacitor_warfare } from './capacitor-warfare'
import { electronic_warfare } from './electronic-warfare'
import { positioning_warfare } from './positioning-warfare'
import { fill_facts } from './facts'

export type * from './types'
export { fill_facts, sim_facts } from './facts'

/** Hub order: Damage first (everyone starts there), then the support roles. */
export const fleet_role_guides: FleetRoleGuide[] = [
    damage,
    remote_repair,
    capacitor_warfare,
    electronic_warfare,
    positioning_warfare,
]

export const FLEET_ROLES_HUB_SLUG = 'fleet-roles'

export function get_fleet_role(slug: string): FleetRoleGuide | undefined {
    return fleet_role_guides.find((guide) => guide.slug === slug)
}

export function get_fleet_role_by_guide(guide_slug: string): FleetRoleGuide | undefined {
    return fleet_role_guides.find((guide) => guide.guide_slug === guide_slug)
}

/**
 * The role guide for a capability-engine class (Training tab, doctrine pages).
 * "Support" is split between Capacitor and Electronic Warfare; it maps to the
 * hub so the pilot can pick.
 */
export function fleet_role_for_capability(capability: string): FleetRoleGuide | undefined {
    if (capability === 'Support') return undefined
    return fleet_role_guides.find((guide) => guide.capabilities.includes(capability))
}

/** Every simulator a guide uses, featured first, without repeats. */
export function guide_sims(guide: FleetRoleGuide): RoleSimId[] {
    const ids: RoleSimId[] = [guide.featured_sim]
    for (const lesson of guide.lessons) {
        if (lesson.sim && !ids.includes(lesson.sim)) ids.push(lesson.sim)
    }
    return ids
}

/** The guide with every {token} in its prose filled from the SDE constants. */
export function resolved_guide(guide: FleetRoleGuide): FleetRoleGuide {
    return {
        ...guide,
        lede: fill_facts(guide.lede),
        why: guide.why.map(fill_facts),
        lessons: guide.lessons.map((lesson) => ({
            ...lesson,
            summary: fill_facts(lesson.summary),
            body: lesson.body.map(fill_facts),
        })),
        mistakes: guide.mistakes.map((mistake) => ({ ...mistake, fix: fill_facts(mistake.fix) })),
    }
}

export function drill_learning_slug(guide: FleetRoleGuide, drill_id: string): string {
    return `${guide.slug}-drill-${drill_id}`
}

export const FLEET_ROLE_SLUGS: FleetRoleSlug[] = fleet_role_guides.map((guide) => guide.slug)
