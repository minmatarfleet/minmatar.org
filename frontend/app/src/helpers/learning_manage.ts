/** Shared bits of the Manage learning screen. */

/** Content kinds, in the order the Kind select lists them (backend ContentKind). */
export const GUIDE_KINDS = ['guide', 'blog', 'page', 'youtube', 'external', 'other'] as const

/** A guide-kind page lives here; its link is this plus the slug. */
export const GUIDE_PATH_PREFIX = '/learning/guides/'

/** A certificate's page. */
export const CERTIFICATE_PATH_PREFIX = '/learning/certificates/'

export const guide_url = (slug: string) => `${GUIDE_PATH_PREFIX}${slug}/`

/** Lowercase, dashes: what the backend's slugify keeps. */
export const slugify = (text: string): string =>
    text
        .toLowerCase()
        .normalize('NFKD')
        .replace(/[^\w\s-]/g, '')
        .trim()
        .replace(/[\s_-]+/g, '-')
        .replace(/^-+|-+$/g, '')

/** Fired when a certificate row moves; the list then saves its order. */
export const CERTIFICATE_ORDER_EVENT = 'certificates-reordered'

/** Fired when a guide moves inside a certificate's form (saved with Save). */
export const CERTIFICATE_GUIDES_EVENT = 'certificate-guides-reordered'

/** Fired when a skill moves inside a skillset's form (saved with Save). */
export const SKILLSET_SKILLS_EVENT = 'skillset-skills-reordered'

/** Certificate personas (backend Persona). */
export const PERSONAS = ['alliance', 'militia', 'other'] as const

/** Each skill once, at the highest level listed: older skillsets list a
 *  skill once per level ("Drones 1", "Drones 2"...), which the API refuses
 *  to save. Keeps the order of first appearance. */
export function distinct_skills(skills: { name: string; level: number }[]): { name: string; level: number }[] {
    const levels = new Map<string, number>()
    for (const skill of skills) levels.set(skill.name, Math.max(levels.get(skill.name) ?? 0, skill.level))
    return [...levels].map(([name, level]) => ({ name, level }))
}
