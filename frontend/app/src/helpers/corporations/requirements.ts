import type {
    ManagedRequirementRule,
    RequirementCheck,
    RequirementCreateRequest,
    RequirementRule,
} from '@dtypes/api.minmatar.org'

export const REQUIREMENT_KINDS = ['ships', 'kills', 'skill_points', 'character_age', 'prime_time'] as const
export type RequirementKind = typeof REQUIREMENT_KINDS[number]

export const REQUIREMENT_WHO = ['main', 'any', 'other_account'] as const
export type RequirementWho = typeof REQUIREMENT_WHO[number]

export const SHIP_LEVELS = ['can_fly', 'doctrine_ready', 'flown'] as const

// Kinds that read the person, not a character, and kinds where "an alt on
// another account" doesn't apply (the backend enforces the same).
export const PERSON_KINDS: readonly RequirementKind[] = ['prime_time']
export const NO_OTHER_ACCOUNT_KINDS: readonly RequirementKind[] = ['kills', 'prime_time']

export type RequirementStatus = 'met' | 'training' | 'unmet' | 'unknown'

/** What the Apply card's heading says. */
export type ApplyState = 'signed_out' | 'open' | 'ready' | 'blocked'

export interface CheckGroups<T> {
    required: T[];
    preferred: T[];
}

export function group_by_importance<T extends { importance: string }>(items: T[]): CheckGroups<T> {
    return {
        required: items.filter((item) => item.importance === 'required'),
        preferred: items.filter((item) => item.importance !== 'required'),
    }
}

export function check_status(check: Pick<RequirementCheck, 'status'>): RequirementStatus {
    const status = check.status
    return status === 'met' || status === 'training' || status === 'unmet' ? status : 'unknown'
}

/** How a check looks: training toward a Nice to have rule isn't a gap, so it reads neutral. */
export function check_tone(check: Pick<RequirementCheck, 'status' | 'importance'>): RequirementStatus {
    const status = check_status(check)
    return status === 'training' && check.importance !== 'required' ? 'unmet' : status
}

/** Required rules still to meet; rules we can't check never count. */
export function blocking_checks(checks: RequirementCheck[]) {
    return checks.filter((check) => check.importance === 'required'
        && (check.status === 'training' || check.status === 'unmet'))
}

export function apply_state(signed_in: boolean, can_apply: boolean): ApplyState {
    if (!signed_in) return 'signed_out'
    return can_apply ? 'ready' : 'blocked'
}

/** As many checks as rules: what a signed-out visitor sees, status unknown. */
export function rules_as_checks(rules: RequirementRule[]): RequirementCheck[] {
    return rules.map((rule) => ({
        id: rule.id,
        kind: rule.kind,
        importance: rule.importance,
        text: rule.text,
        status: 'unknown',
        detail: '',
        ship_type_ids: [],
        training_days: null,
    }))
}

export interface PrimeTime {
    label: string;
    /** EVE time range, e.g. "16:00–20:00"; null when the line has none. */
    eve_range: string | null;
    start_minutes: number | null;
    end_minutes: number | null;
}

/** The corp's timezone field holds lines or comma-separated entries; split both. */
export function prime_time_lines(entries: string[]): string[] {
    return entries
        .flatMap((entry) => entry.split(/\r?\n/))
        .map((line) => line.trim())
        .filter(Boolean)
}

const PRIME_TIME_PATTERN = /^\s*([^()]+?)\s*\((\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})\)\s*$/

/** "EUTZ (16:00 - 20:00)" → label + EVE range; free text keeps its label only. */
export function parse_prime_time(line: string): PrimeTime {
    const match = PRIME_TIME_PATTERN.exec(line)
    if (!match)
        return { label: line.trim(), eve_range: null, start_minutes: null, end_minutes: null }
    const [, label, sh, sm, eh, em] = match
    const pad = (value: string) => value.padStart(2, '0')
    return {
        label,
        eve_range: `${pad(sh)}:${sm}–${pad(eh)}:${em}`,
        start_minutes: Number(sh) * 60 + Number(sm),
        end_minutes: Number(eh) * 60 + Number(em),
    }
}

function form_text(form: FormData, key: string) {
    return String(form.get(key) ?? '').trim()
}

function form_int(form: FormData, key: string) {
    const value = Number.parseInt(form_text(form, key), 10)
    return Number.isNaN(value) ? null : value
}

/** The params half of the add/edit form, per kind. */
export function requirement_params(kind: string, form: FormData): Record<string, unknown> {
    if (kind === 'ships') {
        const target = form_text(form, 'target')
        const level = form_text(form, 'level') || 'can_fly'
        return target === 'capability'
            ? { target, capability: form_text(form, 'capability'), level }
            : { target: 'doctrine', doctrine_id: form_int(form, 'doctrine_id'), level }
    }
    if (kind === 'kills')
        return { months: form_int(form, 'months'), active_months: form_int(form, 'active_months') }
    if (kind === 'skill_points') {
        const millions = form_int(form, 'minimum_millions')
        return { minimum: millions === null ? null : millions * 1_000_000 }
    }
    if (kind === 'character_age')
        return { months: form_int(form, 'age_months') }
    if (kind === 'prime_time')
        return { brackets: form.getAll('brackets').map(String) }
    return {}
}

export function requirement_from_form(form: FormData): RequirementCreateRequest {
    const kind = form_text(form, 'kind')
    return {
        kind,
        params: requirement_params(kind, form),
        who: form_text(form, 'who') || 'any',
        importance: form_text(form, 'importance') === 'required' ? 'required' : 'preferred',
    }
}

/** Values to prefill the edit form with, from a stored rule. */
export function form_values(rule?: Pick<RequirementRule, 'kind' | 'params' | 'who' | 'importance'> | null) {
    const params = (rule?.params ?? {}) as Record<string, any>
    return {
        kind: (rule?.kind ?? 'ships') as RequirementKind,
        who: (rule?.who ?? 'any') as RequirementWho,
        importance: rule?.importance ?? 'preferred',
        target: params.target ?? 'doctrine',
        doctrine_id: params.doctrine_id ?? null,
        capability: params.capability ?? 'Logistics',
        level: params.level ?? 'can_fly',
        months: params.months ?? 6,
        active_months: params.active_months ?? 4,
        minimum_millions: params.minimum ? Math.round(params.minimum / 1_000_000) : 20,
        age_months: params.months ?? 12,
        brackets: (params.brackets ?? []) as string[],
    }
}

/** Below this share of members, a Required rule gets a "make it Preferred?" nudge. */
export const OVER_ASK_PERCENT = 50

export function over_asks(rule: Pick<ManagedRequirementRule, 'importance' | 'members_pass'>) {
    return rule.importance === 'required'
        && rule.members_pass !== null
        && rule.members_pass < OVER_ASK_PERCENT
}
