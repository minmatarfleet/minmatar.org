/** Content model for the Fleet Roles guides (docs/fleets/fleet-role-training-plan.md). */

export type FleetRoleSlug =
    | 'damage'
    | 'remote-repair'
    | 'capacitor-warfare'
    | 'electronic-warfare'
    | 'positioning-warfare'

/** Simulator ids, one per component in components/blocks/role-sims. */
export type RoleSimId =
    | 'bubbles'
    | 'mjfg'
    | 'capacitor-curve'
    | 'neut-pressure'
    | 'jam-chance'
    | 'ecm-spread'
    | 'rep-race'
    | 'applied-damage'

export type LessonFormat = 'sim' | 'video' | 'diagram' | 'read'

export type RoleRung = {
    /** Rung number on the ladder; hulls that are alternatives share one. */
    rung: number
    ship_type_id: number
    name: string
    hull_class: string
    /** True when this rung is the Academy entry point. */
    academy?: boolean
    /** One line: what this hull does for the role. */
    job: string
}

export type RoleVideo = {
    youtube_id: string
    title: string
    /** Creator and year, e.g. "The Brave Dojo · 2023". */
    source: string
}

export type RoleLesson = {
    id: string
    title: string
    /** One line shown in the lesson list. */
    summary: string
    format: LessonFormat
    /** HTML paragraphs. Tokens like {probe_radius_km} are filled from the SDE constants. */
    body: string[]
    sim?: RoleSimId
    video?: RoleVideo
    /** A screenshot from public/images, e.g. the fleet window from the New Player Fleet Guide. */
    image?: { src: string; alt: string; caption: string }
}

export type RolePhase = {
    name: string
    /** What the FC says. */
    fc: string
    /** What you do. */
    you: string
}

export type RoleMistake = {
    title: string
    fix: string
}

export type DrillKind = 'sim' | 'fleet' | 'setup' | 'optional'

export type RoleDrill = {
    /** Learning slug suffix: the drill's Learning is `<role>-drill-<id>`. */
    id: string
    title: string
    how: string
    kind: DrillKind
    /** A simulator that completes this drill when beaten. */
    sim?: RoleSimId
}

/** `guide` is one of our own guides or site tools; the rest are outside. */
export type ResourceKind = 'guide' | 'video' | 'wiki' | 'ccp' | 'tool' | 'sim'

export type RoleResource = {
    kind: ResourceKind
    title: string
    source: string
    why: string
    url: string
}

export type FleetRoleGuide = {
    slug: FleetRoleSlug
    /** Guide slug in data/guides (route /learning/guides/<guide_slug>/). */
    guide_slug: string
    certificate_slug: string
    name: string
    short_name: string
    /** Hero line under the title. */
    lede: string
    /** Capability classes from the capability engine that count as this role. */
    capabilities: string[]
    hero_type_id: number
    /** "Why this role wins fights": HTML paragraphs. */
    why: string[]
    /** How the role shows up on our own fleets: HTML paragraphs under the Why section. */
    in_our_fleets: string[]
    /** Optional lead-in video for the Why section. */
    why_video?: RoleVideo
    ladder: RoleRung[]
    ladder_note?: string
    lessons: RoleLesson[]
    phases: RolePhase[]
    mistakes: RoleMistake[]
    drills: RoleDrill[]
    resources: RoleResource[]
    /** Featured simulator at the top of the Mechanics section. */
    featured_sim: RoleSimId
    read_minutes: number
}
