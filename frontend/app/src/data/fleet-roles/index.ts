import type { FleetRoleGuide, FleetRoleSlug } from './types'
import { damage } from './damage'
import { remote_repair } from './remote-repair'
import { capacitor_warfare } from './capacitor-warfare'
import { electronic_warfare } from './electronic-warfare'
import { fleet_support } from './fleet-support'
import { fleet_disruption } from './fleet-disruption'
import { fill_facts } from './facts'

export type * from './types'
export { fill_facts, sim_facts } from './facts'

/** Hub order: Damage first (everyone starts there), then the support roles. */
/** In the order the landing page reads them: build, support, disrupt. */
export const fleet_role_guides: FleetRoleGuide[] = [
    damage,
    remote_repair,
    fleet_support,
    capacitor_warfare,
    electronic_warfare,
    fleet_disruption,
]

export const FLEET_ROLES_HUB_SLUG = 'fleet-roles'

/**
 * The guides are live: the Learning Center and the Training tab link them.
 * Set false (and mark them unlisted in data/guides) to hide them again.
 */
export const FLEET_ROLES_LISTED = true

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
            steps: lesson.steps?.map(fill_facts),
            donts: lesson.donts?.map(fill_facts),
            lists: lesson.lists?.map((list) => ({ ...list, items: list.items.map(fill_facts) })),
        })),
        mistakes: guide.mistakes.map((mistake) => ({ ...mistake, fix: fill_facts(mistake.fix) })),
    }
}

export function drill_learning_slug(guide: FleetRoleGuide, drill_id: string): string {
    return `${guide.slug}-drill-${drill_id}`
}

export const FLEET_ROLE_SLUGS: FleetRoleSlug[] = fleet_role_guides.map((guide) => guide.slug)
