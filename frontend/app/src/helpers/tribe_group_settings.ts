/**
 * The group page's Settings tab: each section (Discord, Publishing) saves on
 * its own, so each builds only its part of TribeGroupPublishingPatch.
 */
import type {
    PublishingKind,
    PublishingPolicy,
    TribeGroupPublishing,
    TribeGroupPublishingPatch,
} from '@dtypes/api.minmatar.org'

export type TribeGroupSettingsSection = 'discord' | 'publishing'

export const PUBLISHING_KINDS: PublishingKind[] = ['post', 'fleet', 'event']
export const PUBLISHING_POLICIES: PublishingPolicy[] = ['chiefs', 'chosen', 'members']

export function parse_settings_section(value: string | null | undefined): TribeGroupSettingsSection | null {
    return value === 'discord' || value === 'publishing' ? value : null
}

interface FormValues {
    get(name: string): FormDataEntryValue | null;
    getAll(name: string): FormDataEntryValue[];
}

const policy = (value: FormDataEntryValue | null): PublishingPolicy =>
    PUBLISHING_POLICIES.find((item) => item === value) ?? 'chiefs'

const character_ids = (values: FormDataEntryValue[]): number[] => [
    ...new Set(values.map((value) => parseInt(String(value))).filter((id) => Number.isFinite(id) && id > 0)),
]

/**
 * Discord section: `discord_channel_id` '' means "use the tribe's channel"
 * (null). The id stays a string: snowflakes don't fit a JavaScript number and
 * the API takes digit strings.
 */
export function discord_settings_patch(form: FormValues): TribeGroupPublishingPatch {
    const channel = String(form.get('discord_channel_id') ?? '').trim()
    return {
        discord_channel_id: (/^\d+$/.test(channel) ? channel : null) as unknown as number | null,
    }
}

/**
 * Publishing section: the three policies (`post_policy`, ...), the chosen
 * pilots (`post_publishers`, ... repeated) and the two switches. Chosen pilots
 * are only sent with the "chiefs and chosen pilots" policy, so switching away
 * and back keeps the list.
 */
export function publishing_settings_patch(form: FormValues): TribeGroupPublishingPatch {
    const patch: TribeGroupPublishingPatch = {
        allow_alliance_posts: form.get('allow_alliance_posts') === 'on',
        allow_open_fleets: form.get('allow_open_fleets') === 'on',
    }
    for (const kind of PUBLISHING_KINDS) {
        const chosen = policy(form.get(`${kind}_policy`))
        patch[`${kind}_policy`] = chosen
        if (chosen === 'chosen')
            patch[`${kind}_publisher_character_ids`] = character_ids(form.getAll(`${kind}_publishers`))
    }
    return patch
}

export function policy_of(settings: TribeGroupPublishing, kind: PublishingKind): PublishingPolicy {
    return settings[`${kind}_policy`]
}

export function publishers_of(settings: TribeGroupPublishing, kind: PublishingKind) {
    return settings[`${kind}_publishers`]
}
