/** Routing for the tribe structure dialogs (TribeStructureButton). */

export const STRUCTURE_MODES = ['new_tribe', 'new_group', 'rename', 'archive', 'restore'] as const
export type StructureMode = typeof STRUCTURE_MODES[number]

export interface StructureAction {
    mode:       StructureMode;
    tribe_id:   number | null;
    group_id:   number | null;
}

function positive_id(value: string | null): number | null {
    const id = Number.parseInt(value ?? '', 10)
    return Number.isFinite(id) && id > 0 ? id : null
}

/**
 * The action a structure form posts, or null when it doesn't make sense:
 * an unknown mode, or a mode that needs a tribe without one.
 */
export function parse_structure_action(params: URLSearchParams): StructureAction | null {
    const mode = params.get('action') as StructureMode
    if (!STRUCTURE_MODES.includes(mode))
        return null
    const tribe_id = positive_id(params.get('tribe_id'))
    const group_id = positive_id(params.get('group_id'))
    if (mode !== 'new_tribe' && !tribe_id)
        return null
    if (mode === 'new_group' && group_id)
        return null
    return { mode, tribe_id, group_id: mode === 'new_tribe' ? null : group_id }
}

/** The page of a tribe, or of one of its groups. */
export function tribe_page_path(tribe_id: number, group_id: number | null = null): string {
    return group_id ? `/alliance/tribes/${tribe_id}/${group_id}` : `/alliance/tribes/${tribe_id}`
}
