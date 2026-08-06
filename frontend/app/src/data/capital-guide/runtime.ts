import { get_fittings } from '@helpers/api.minmatar.org/ships'
import { get_tribe, get_tribe_group } from '@helpers/api.minmatar.org/tribes'
import type { Fitting, TribeCharacterRef } from '@dtypes/api.minmatar.org'
import {
    CAPITALS_TRIBE_ID,
    capitals_group_path,
    capitals_tribe_path,
    build_capitals_tribe_copy,
} from './tribes'

export type CapitalGuideRuntimeOptions = {
    group_id: number
    tribe_name_fallback: string
    group_name_fallback: string
    subject_phrase: string
    teach_topic: string
    translate_path: (path: string) => string
    tribe_id?: number
}

export type CapitalGuideRuntime = {
    fitting_library: Fitting[]
    capitals_chief: TribeCharacterRef | null
    group_chief: TribeCharacterRef | null
    tribe: string[]
}

export async function load_capital_guide_runtime(
    options: CapitalGuideRuntimeOptions,
): Promise<CapitalGuideRuntime> {
    const tribe_id = options.tribe_id ?? CAPITALS_TRIBE_ID

    const [fittings_result, tribe_result] = await Promise.all([
        get_fittings().catch(() => [] as Fitting[]),
        Promise.all([
            get_tribe(tribe_id),
            get_tribe_group(tribe_id, options.group_id),
        ]).catch(() => null),
    ])

    const capitals_tribe = tribe_result?.[0] ?? null
    const group = tribe_result?.[1] ?? null

    return {
        fitting_library: fittings_result,
        capitals_chief: capitals_tribe?.chief ?? null,
        group_chief: group?.chief ?? null,
        tribe: build_capitals_tribe_copy({
            subject_phrase: options.subject_phrase,
            teach_topic: options.teach_topic,
            tribe_name: capitals_tribe?.name ?? options.tribe_name_fallback,
            group_name: group?.name ?? options.group_name_fallback,
            tribe_href: options.translate_path(capitals_tribe_path(tribe_id)),
            group_href: options.translate_path(capitals_group_path(options.group_id, tribe_id)),
        }),
    }
}
