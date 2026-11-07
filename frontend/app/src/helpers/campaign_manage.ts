/** Shared by the campaign Settings tab, the new-campaign form and the payout codes screen. */
import type { CampaignChoice } from '@helpers/api.minmatar.org/campaigns'

/** The backend label for a stored value; the value itself when the label is unknown. */
export function choice_label(choices: CampaignChoice[] | undefined, value: string | null | undefined): string {
    if (!value) return ''
    return choices?.find((choice) => choice.value === value)?.label ?? value
}

/** The page slug a name gives: "Huola Push!" -> "huola-push". */
export function slug_from_name(name: string): string {
    return name
        .normalize('NFKD')
        .replace(/[̀-ͯ]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '')
        .slice(0, 64)
        .replace(/-+$/g, '')
}

/** Whole weeks when it divides evenly, else days; '' when the end is not after the start. */
export function duration_parts(start_iso: string, end_iso: string): { value: number, unit: 'weeks' | 'days' | 'hours' } | null {
    const start = new Date(start_iso).getTime()
    const end = new Date(end_iso).getTime()
    if (Number.isNaN(start) || Number.isNaN(end) || end <= start) return null
    const hours = Math.round((end - start) / 3_600_000)
    if (hours < 48) return { value: hours, unit: 'hours' }
    const days = Math.round(hours / 24)
    if (days % 7 === 0) return { value: days / 7, unit: 'weeks' }
    return { value: days, unit: 'days' }
}

/** "Tue 17 Nov" in EVE time. */
export function eve_weekday_date(lang: string, iso: string): string {
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return ''
    return date.toLocaleDateString(lang, { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' })
}

/** "3 Nov 19:25" in EVE time. */
export function eve_date_time(lang: string, iso: string): string {
    const date = new Date(iso)
    if (Number.isNaN(date.getTime())) return ''
    const day = date.toLocaleDateString(lang, { day: 'numeric', month: 'short', timeZone: 'UTC' })
    return `${day} ${date.toISOString().slice(11, 16)}`
}

/** "Kamela, take · Huola, pressure": each live system with its goal. */
export function systems_summary(
    systems: { name: string, goal: string, retired?: boolean }[],
    goals: CampaignChoice[] | undefined,
): string {
    return systems
        .filter((system) => !system.retired)
        .map((system) => `${system.name}, ${choice_label(goals, system.goal).toLowerCase()}`)
        .join(' · ')
}

/** "Enemy: Amarr Defense [AMD] · Ally: ...": parties grouped by side. */
export function sides_summary(
    parties: { name: string, ticker?: string | null, side: string }[],
    sides: CampaignChoice[] | undefined,
): string {
    const order = (sides ?? []).map((side) => side.value)
    const groups = new Map<string, string[]>()
    for (const party of parties) {
        const name = party.ticker ? `${party.name} [${party.ticker}]` : party.name
        groups.set(party.side, [...(groups.get(party.side) ?? []), name])
    }
    return [...groups.entries()]
        .sort(([a], [b]) => order.indexOf(a) - order.indexOf(b))
        .map(([side, names]) => `${choice_label(sides, side)}: ${names.join(', ')}`)
        .join(' · ')
}

/** What the new-campaign form posted, to fill it again after a refusal. */
export type CampaignNewValues = {
    name:       string;
    slug:       string;
    kind:       string;
    start_at:   string;
    end_at:     string;
    systems:    { id: string, name: string }[];
}

export type CampaignNewErrors = {
    form?:      string;
    slug?:      string;
    systems?:   string;
}


/** The backend's reason without the client's "Error changing campaign: " prefix. */
export function refusal_text(error: unknown, fallback: string): string {
    const message = error instanceof Error && error.message ? error.message : fallback
    return message.replace(/^Error [^:]{1,60}: /, '')
}
