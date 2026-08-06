export const CAPITALS_TRIBE_ID = 1
export const DREADS_GROUP_ID = 1
export const CARRIERS_GROUP_ID = 2
export const FAXES_GROUP_ID = 3

export const CAPITALS_TRIBE_NAME = 'Capitals'
export const DREADS_GROUP_NAME = 'Dreads'
export const CARRIERS_GROUP_NAME = 'Carriers'
export const FAXES_GROUP_NAME = 'Faxes'

export function capitals_tribe_path(tribe_id: number = CAPITALS_TRIBE_ID): string {
    return `/alliance/tribes/${tribe_id}/`
}

export function capitals_group_path(
    group_id: number,
    tribe_id: number = CAPITALS_TRIBE_ID,
): string {
    return `/alliance/tribes/${tribe_id}/${group_id}/`
}

export type CapitalsTribeCopyOptions = {
    subject_phrase: string
    teach_topic: string
    tribe_name: string
    group_name: string
    tribe_href: string
    group_href: string
}

export function build_capitals_tribe_copy(options: CapitalsTribeCopyOptions): string[] {
    const {
        subject_phrase,
        teach_topic,
        tribe_name,
        group_name,
        tribe_href,
        group_href,
    } = options

    return [
        `${subject_phrase} the <a href="${tribe_href}">${tribe_name} tribe</a> in Minmatar Fleet. As much as we'd love to teach ${teach_topic} through a bulleted list, it's best to just join that and talk to people — start with the <a href="${group_href}">${group_name} group</a>.`,
    ]
}
