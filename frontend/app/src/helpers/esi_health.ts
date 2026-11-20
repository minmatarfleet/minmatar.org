import type { EsiHealthPilot } from '@dtypes/api.minmatar.org'

type Translate = (key: string) => string

export interface EsiMessagePreviewText {
    who:        string;
    title:      string;
    body:       string;
}

/** A superuser's message reaches pilots with Discord linked who aren't On Leave and weren't messaged in the last week. */
export function message_ready(pilot: EsiHealthPilot, now: Date = new Date()): boolean {
    if (pilot.on_leave || !pilot.discord_linked) return false
    if (!pilot.next_message_at) return true
    return new Date(pilot.next_message_at) <= now
}

/** What one pilot sees, worded as notifications/types/esi.py sends it. */
export function message_preview(t: Translate, sender: string, pilot: EsiHealthPilot): EsiMessagePreviewText {
    const [first, ...rest] = pilot.characters
    const others = rest.length
    const who = others === 0
        ? first
        : t(others === 1 ? 'esi_health.preview_and_one' : 'esi_health.preview_and_more')
            .replace('~NAME', first)
            .replace('~COUNT', String(others))
    return {
        who: t('esi_health.preview_who').replace('~NAME', pilot.main_character_name),
        title: t('esi_health.preview_title').replace('~NAME', sender),
        body: t('esi_health.preview_body').replace('~WHO', who),
    }
}

/** "Re-add main + 2 alts", "Re-add 3 alts", "Re-add main". */
export function readd_label(t: Translate, main_broken: boolean, count: number): string {
    const alts = main_broken ? count - 1 : count
    if (main_broken && alts === 0) return t('esi_health.readd_main')
    if (main_broken)
        return t(alts === 1 ? 'esi_health.readd_main_alt' : 'esi_health.readd_main_alts').replace('~COUNT', String(alts))
    return t(alts === 1 ? 'esi_health.readd_alt' : 'esi_health.readd_alts').replace('~COUNT', String(alts))
}
