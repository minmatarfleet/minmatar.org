/** Content model for the Fleet Roles guides (docs/fleets/fleet-role-training-plan.md). */

export type FleetRoleSlug =
    | 'damage'
    | 'remote-repair'
    | 'capacitor-warfare'
    | 'electronic-warfare'
    | 'fleet-support'
    | 'fleet-disruption'

/** Teaching diagrams, one component each in components/blocks/role-diagrams. */
export type RoleDiagramId =
    | 'fleet-snake'
    | 'paint-web-torpedoes'
    | 'boosh-logi'

/** A utility module in a lesson's module panel: its three biggest effects in a fight. */
export type RoleModuleCard = {
    type_id: number
    /** Full name, e.g. "Energy neutralizer". */
    name: string
    /** One or two words under its icon. */
    short: string
    /** The fitted module shown, e.g. "Heavy Energy Neutralizer II". */
    example: string
    impacts: { title: string; detail: string }[]
    /** A matching practice scenario elsewhere, e.g. in EVE Combat Sim. */
    practice?: { title: string; url: string }
    /** The module's EVE Academy section. */
    learn?: { title: string; url: string }
}

export type LessonFormat = 'video' | 'diagram' | 'read' | 'ammo' | 'links'

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
    video?: RoleVideo
    /** A screenshot from public/images, e.g. the fleet window from the New Player Fleet Guide. */
    image?: { src: string; alt: string; caption: string }
    /** An interactive panel of utility modules, shown after the text. */
    modules?: RoleModuleCard[]
    /** Diagrams shown after the text, in order. */
    diagrams?: RoleDiagramId[]
    /** Extra titled lists after the steps, e.g. "Break anchor when". HTML items; type_id shows that item's icon by the title. */
    lists?: { title: string; items: string[]; type_id?: number }[]
    /** Things not to do, most important first. HTML. */
    donts?: string[]
    /** "Do this" steps, in order. HTML. */
    steps?: string[]
    /** Short official clips (CCP's EVE Academy) played inline, each linking its source page. */
    clips?: { src: string; title: string; source: string; url: string }[]
    /** One outside simulation to practice the lesson in, shown as a large card that opens in a new tab. */
    practice?: RoleResource
    /** Outside tools to try the lesson in (format 'links'), e.g. a damage simulator. */
    links?: RoleResource[]
    /** Short note per weapon family for the ammo charts (format 'ammo'), keyed like ammo.json. */
    ammo_notes?: Record<string, string>
}

export type RoleMistake = {
    title: string
    fix: string
}

export type DrillKind = 'fleet' | 'setup' | 'optional'

export type RoleDrill = {
    /** Learning slug suffix: the drill's Learning is `<role>-drill-<id>`. */
    id: string
    title: string
    how: string
    kind: DrillKind
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
    name: string
    short_name: string
    /** Hero line under the title. */
    lede: string
    /** A few words for the Fleet Roles landing page. */
    tagline: string
    /** Capability classes from the capability engine that count as this role. */
    capabilities: string[]
    hero_type_id: number
    /** "Why this role wins fights": HTML paragraphs. */
    why: string[]
    /** Optional lead-in video for the Why section. */
    why_video?: RoleVideo
    ladder: RoleRung[]
    ladder_note?: string
    /**
     * Build the ship section from our current doctrines instead of a ladder:
     * every hull that flies a fit of this kind, with how often we fly it.
     * 'damage' = fits with three or more weapons and no remote repairers.
     * 'logistics' = fits with a remote repairer.
     * 'listed' = any doctrine fit of the hulls in ships_only.
     */
    ships_from_doctrines?: 'damage' | 'logistics' | 'listed'
    /** The hulls to show, in this order. A hull no doctrine flies still gets a card. */
    ships_only?: number[]
    /**
     * What each hull does for the role, shown under its name. A guide with
     * ship jobs shows its hulls as the role's ships, without doctrine tags.
     */
    ship_jobs?: Record<number, string>
    lessons: RoleLesson[]
    mistakes: RoleMistake[]
    drills: RoleDrill[]
    resources: RoleResource[]
    read_minutes: number
}
