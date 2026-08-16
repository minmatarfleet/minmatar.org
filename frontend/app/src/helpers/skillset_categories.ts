export const skillset_filter_ids = [
    'new_player',
    'subcapitals',
    'capitals',
] as const

export type SkillsetFilterId = (typeof skillset_filter_ids)[number]

/** Frontend category tags for doctrine skillsets (EveSkillset has no category field). */
export const skillset_category_by_name: Record<string, SkillsetFilterId> = {
    'Academy Starter Plan': 'new_player',
    'Magic 14': 'new_player',
    'Shield Logistics Cruisers': 'subcapitals',
    'Armor Logistics Cruisers': 'subcapitals',
    'Revelation/RNI': 'capitals',
    'Apostle': 'capitals',
}

export function get_skillset_category(name: string): SkillsetFilterId | null {
    return skillset_category_by_name[name] ?? null
}
