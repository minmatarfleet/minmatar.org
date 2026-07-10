export const L3ARN_CORPORATION_NAME = 'Minmatar Fleet Academy';

/** Discord API hard limit for message content. */
export const DISCORD_MESSAGE_MAX_LENGTH = 2000;

/**
 * Estimated characters in the Discord forum-thread opener before the
 * application description body (mentions, metadata lines, URL).
 */
export const L3ARN_APPLICATION_DISCORD_METADATA_OVERHEAD = 300;

/** Max length of the formatted L3ARN application description stored and posted to Discord. */
export const L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH =
    DISCORD_MESSAGE_MAX_LENGTH - L3ARN_APPLICATION_DISCORD_METADATA_OVERHEAD;

/** Per-field maxlength for user-editable text inputs on the L3ARN form. */
export const L3ARN_APPLICATION_FIELD_LIMITS = {
    introduction: 300,
    goals: 180,
    how_found_other: 80,
    main_character_name: 37,
    other_alliance_affiliation: 40,
} as const;

export type L3arnApplicationLimitedField =
    keyof typeof L3ARN_APPLICATION_FIELD_LIMITS;

/** Fixed template overhead for the formatted description (roles, labels, sections). */
export const L3ARN_APPLICATION_DESCRIPTION_FIXED_OVERHEAD = 771;

/** Show character counter when remaining chars drop below this offset from the limit. */
export const L3ARN_APPLICATION_COUNTER_THRESHOLD_OFFSET = 50;

export const L3ARN_EXCLUDED_ALLIANCE_CORPORATIONS = [
    L3ARN_CORPORATION_NAME,
    'Minmatar Fleet Holdings',
] as const;

/** Main Minmatar Fleet Alliance corps (slider corps), excluding L3ARN and Holdings. */
export const L3ARN_MAIN_ALLIANCE_CORPORATIONS = [
    'Rattini Tribe',
    'Soltech Armada',
    'Straylight Systems',
    'The Dark Tribe',
    'Administrative Atrocities',
] as const;

export const L3ARN_FORM_PREFIX = 'l3arn_';

export const L3ARN_APPLICATION_DRAFT_STORAGE_KEY = 'l3arn_application_draft';

export const L3ARN_APPLICATION_TIMEZONES = [
    'US',
    'US_AP',
    'AP',
    'AP_EU',
    'EU',
    'EU_US',
] as const;

export type L3arnApplicationTimezone = typeof L3ARN_APPLICATION_TIMEZONES[number];

export const L3ARN_APPLICATION_TIMEZONE_LABELS: Record<
    L3arnApplicationTimezone,
    string
> = {
    US: 'USTZ',
    US_AP: 'USTZ - AUTZ',
    AP: 'AUTZ',
    AP_EU: 'AUTZ - EUTZ',
    EU: 'EUTZ',
    EU_US: 'EUTZ - USTZ',
};

/**
 * UTC hour bands from fleets `time_region()` — when alliance fleets peak in each bucket.
 * AP_EU spans the AUTZ–EUTZ crossover used for afternoon EU applicants.
 */
export const L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS: Record<
    L3arnApplicationTimezone,
    string
> = {
    US: 'EVE prime time: roughly 22:00–04:59 UTC',
    US_AP: 'EVE prime time: roughly 05:00–09:59 UTC',
    AP: 'EVE prime time: roughly 10:00–14:59 UTC',
    AP_EU: 'EVE prime time: roughly 10:00–19:59 UTC (AUTZ–EUTZ overlap)',
    EU: 'EVE prime time: roughly 15:00–19:59 UTC',
    EU_US: 'EVE prime time: roughly 20:00–21:59 UTC',
};

/** Geographic regions inferred from the applicant's browser timezone. */
export const L3ARN_APPLICATION_REGIONS = ['US', 'AP', 'EU'] as const;

export type L3arnApplicationRegion = typeof L3ARN_APPLICATION_REGIONS[number];

export const L3ARN_APPLICATION_REGION_LABELS: Record<
    L3arnApplicationRegion,
    string
> = {
    US: 'US',
    AP: 'Asia-Pacific',
    EU: 'Europe',
};

/** When the applicant is usually active in their local time. */
export const L3ARN_APPLICATION_ACTIVITY_PERIODS = [
    'early_morning',
    'morning',
    'afternoon',
    'evening',
] as const;

export type L3arnApplicationActivityPeriod =
    typeof L3ARN_APPLICATION_ACTIVITY_PERIODS[number];

export const L3ARN_APPLICATION_ACTIVITY_PERIOD_LABELS: Record<
    L3arnApplicationActivityPeriod,
    string
> = {
    early_morning: 'early mornings',
    morning: 'mornings',
    afternoon: 'afternoons',
    evening: 'evenings',
};

/**
 * Maps geographic region + local activity period to an EVE prime-time bucket.
 *
 * Evening in a region maps to that region's home bucket (US→US, EU→EU, AP→AP).
 * Morning/afternoon picks crossover buckets where local play overlaps adjacent
 * regions' prime times (aligned with fleets `time_region()` UTC hour bands).
 *
 * Early morning (about midnight–6am local) maps one step earlier on the UTC
 * cycle than morning: EU night owls overlap US prime (22–4 UTC), AP early
 * hours overlap EU prime (15–19 UTC), US pre-dawn overlaps US_AP (5–9 UTC).
 */
export const L3ARN_REGION_PERIOD_TO_TIMEZONE: Record<
    L3arnApplicationRegion,
    Record<L3arnApplicationActivityPeriod, L3arnApplicationTimezone>
> = {
    US: {
        early_morning: 'US_AP',
        morning: 'US_AP',
        afternoon: 'EU_US',
        evening: 'US',
    },
    EU: {
        early_morning: 'US',
        morning: 'US_AP',
        afternoon: 'AP_EU',
        evening: 'EU',
    },
    AP: {
        early_morning: 'EU',
        morning: 'EU_US',
        afternoon: 'US_AP',
        evening: 'AP',
    },
};

export const L3ARN_APPLICATION_ROLES = [
    'fleet_damage',
    'fleet_logistics',
    'fleet_support',
    'solo_combat',
    'small_gang_combat',
    'resource_harvesting',
    'production',
] as const;

export type L3arnApplicationRole = typeof L3ARN_APPLICATION_ROLES[number];

export const L3ARN_APPLICATION_ROLE_LABELS: Record<
    L3arnApplicationRole,
    string
> = {
    fleet_damage: 'Fleet damage (guns, missiles, etc)',
    fleet_logistics: 'Fleet logistics (healing)',
    fleet_support: 'Fleet support (painting, tackling, etc)',
    solo_combat: 'Solo combat',
    small_gang_combat: 'Small gang combat (<10 pilots)',
    resource_harvesting: 'Resource harvesting (mining, planet harvesting, etc)',
    production: 'Production (building things)',
};

export const L3ARN_APPLICATION_HOW_FOUND_OPTIONS = [
    'reddit_post_seen',
    'forum_post_seen',
    'reddit_post_made',
    'forum_post_made',
    'other',
] as const;

export type L3arnApplicationHowFound =
    typeof L3ARN_APPLICATION_HOW_FOUND_OPTIONS[number];

export const L3ARN_APPLICATION_HOW_FOUND_LABELS: Record<
    L3arnApplicationHowFound,
    string
> = {
    reddit_post_seen: 'I saw a Reddit post by Minmatar Fleet',
    forum_post_seen: 'I saw a forum post by Minmatar Fleet',
    reddit_post_made: 'I made a Reddit post and received a response from Minmatar Fleet',
    forum_post_made: 'I made a forum post and received a response from Minmatar Fleet',
    other: 'Other',
};

const L3ARN_APPLICATION_STRING_FIELDS = [
    'introduction',
    'activity_region',
    'activity_period',
    'timezone',
    'user_timezone',
    'goals',
    'how_found',
    'how_found_other',
    'main_character_name',
    'other_alliance_affiliation',
] as const;

const L3ARN_APPLICATION_ARRAY_FIELDS = [
    'roles',
    'other_corporations',
] as const;

const L3ARN_APPLICATION_BOOLEAN_FIELDS = [
    'is_existing_player_alt',
    'is_other_alliance_member',
    'agree_tenets',
    'confirm_omega',
    'confirm_auth_chars',
] as const;

export interface L3arnApplicationAnswers {
    introduction: string;
    activity_region: string;
    activity_period: string;
    /** EVE prime-time bucket derived from region + activity period. */
    timezone: string;
    /** Applicant IANA timezone from the browser, e.g. America/New_York. */
    user_timezone: string;
    roles: string[];
    goals: string;
    how_found: string;
    how_found_other: string;
    other_corporations: string[];
    is_existing_player_alt: boolean;
    is_other_alliance_member: boolean;
    main_character_name: string;
    other_alliance_affiliation: string;
    agree_tenets: boolean;
    confirm_omega: boolean;
    confirm_auth_chars: boolean;
}

export const EMPTY_L3ARN_APPLICATION_ANSWERS: L3arnApplicationAnswers = {
    introduction: '',
    activity_region: '',
    activity_period: '',
    timezone: '',
    user_timezone: '',
    roles: [],
    goals: '',
    how_found: '',
    how_found_other: '',
    other_corporations: [],
    is_existing_player_alt: false,
    is_other_alliance_member: false,
    main_character_name: '',
    other_alliance_affiliation: '',
    agree_tenets: false,
    confirm_omega: false,
    confirm_auth_chars: false,
};

export function isL3arnCorporation(corporation: {
    corporation_name?: string;
}): boolean {
    return corporation.corporation_name === L3ARN_CORPORATION_NAME;
}

export function isL3arnApplicationTimezone(
    value: string,
): value is L3arnApplicationTimezone {
    return (L3ARN_APPLICATION_TIMEZONES as readonly string[]).includes(value);
}

export function l3arnApplicationTimezoneLabel(timezone: string): string {
    if (isL3arnApplicationTimezone(timezone)) {
        return L3ARN_APPLICATION_TIMEZONE_LABELS[timezone];
    }

    return timezone;
}

export function l3arnApplicationTimezoneEveWindow(timezone: string): string {
    if (isL3arnApplicationTimezone(timezone)) {
        return L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS[timezone];
    }

    return '';
}

export function isL3arnApplicationRegion(
    value: string,
): value is L3arnApplicationRegion {
    return (L3ARN_APPLICATION_REGIONS as readonly string[]).includes(value);
}

export function l3arnApplicationRegionLabel(region: string): string {
    if (isL3arnApplicationRegion(region)) {
        return L3ARN_APPLICATION_REGION_LABELS[region];
    }

    return region;
}

export function isL3arnApplicationActivityPeriod(
    value: string,
): value is L3arnApplicationActivityPeriod {
    return (L3ARN_APPLICATION_ACTIVITY_PERIODS as readonly string[]).includes(
        value,
    );
}

export function l3arnApplicationActivityPeriodLabel(period: string): string {
    if (isL3arnApplicationActivityPeriod(period)) {
        return L3ARN_APPLICATION_ACTIVITY_PERIOD_LABELS[period];
    }

    return period;
}

export function mapL3arnRegionAndPeriodToTimezone(
    region: L3arnApplicationRegion,
    period: L3arnApplicationActivityPeriod,
): L3arnApplicationTimezone {
    return L3ARN_REGION_PERIOD_TO_TIMEZONE[region][period];
}

export function resolveL3arnApplicationTimezone(
    answers: Pick<L3arnApplicationAnswers, 'activity_region' | 'activity_period'>,
): L3arnApplicationTimezone | '' {
    const region = trim(answers.activity_region);
    const period = trim(answers.activity_period);

    if (
        !isL3arnApplicationRegion(region)
        || !isL3arnApplicationActivityPeriod(period)
    ) {
        return '';
    }

    return mapL3arnRegionAndPeriodToTimezone(region, period);
}

export function withResolvedL3arnApplicationTimezone(
    answers: L3arnApplicationAnswers,
): L3arnApplicationAnswers {
    const timezone = resolveL3arnApplicationTimezone(answers);

    return {
        ...answers,
        timezone: timezone || answers.timezone,
    };
}

/**
 * Infer US / AP / EU from the browser's IANA timezone, falling back to UTC offset.
 */
export function detectL3arnApplicationRegionFromBrowser(): L3arnApplicationRegion {
    try {
        const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

        if (
            timeZone.startsWith('America/')
            || timeZone === 'Pacific/Honolulu'
            || timeZone === 'Pacific/Pago_Pago'
            || timeZone === 'Pacific/Midway'
        ) {
            return 'US';
        }

        if (
            timeZone.startsWith('Asia/')
            || timeZone.startsWith('Australia/')
            || (
                timeZone.startsWith('Pacific/')
                && timeZone !== 'Pacific/Honolulu'
                && timeZone !== 'Pacific/Pago_Pago'
                && timeZone !== 'Pacific/Midway'
            )
        ) {
            return 'AP';
        }

        return 'EU';
    } catch {
        const utcOffsetHours = -new Date().getTimezoneOffset() / 60;

        if (utcOffsetHours <= -2) {
            return 'US';
        }

        if (utcOffsetHours >= 5) {
            return 'AP';
        }

        return 'EU';
    }
}

export function formatL3arnApplicationActivitySummary(
    answers: Pick<
        L3arnApplicationAnswers,
        'activity_region' | 'activity_period' | 'timezone'
    >,
): string {
    const region = l3arnApplicationRegionLabel(trim(answers.activity_region));
    const period = l3arnApplicationActivityPeriodLabel(
        trim(answers.activity_period),
    );
    const bucket = l3arnApplicationTimezoneLabel(
        trim(answers.timezone) || resolveL3arnApplicationTimezone(answers),
    );

    return `${region} region, ${period} → ${bucket}`;
}

/**
 * Read the browser IANA timezone (e.g. America/New_York).
 */
export function detectL3arnApplicationUserTimezone(): string {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    } catch {
        return '';
    }
}

/**
 * Format an IANA timezone with its current offset abbreviation (EST, EDT, etc.).
 */
export function formatL3arnApplicationUserTimezoneLabel(
    ianaTimezone: string,
    at: Date = new Date(),
): string {
    const timeZone = trim(ianaTimezone);

    if (!timeZone) {
        return '';
    }

    try {
        const offsetLabel = new Intl.DateTimeFormat('en-US', {
            timeZone,
            timeZoneName: 'short',
        })
            .formatToParts(at)
            .find((part) => part.type === 'timeZoneName')?.value;

        return offsetLabel ? `${timeZone} (${offsetLabel})` : timeZone;
    } catch {
        return timeZone;
    }
}

export function formatL3arnApplicationTimezoneLine(
    answers: Pick<
        L3arnApplicationAnswers,
        'user_timezone' | 'activity_region' | 'activity_period' | 'timezone'
    >,
): string {
    const humanTimezone = formatL3arnApplicationUserTimezoneLabel(
        trim(answers.user_timezone),
    );
    const eveActivity = formatL3arnApplicationActivitySummary(answers);

    if (humanTimezone && eveActivity) {
        return `${humanTimezone} — ${eveActivity}`;
    }

    return humanTimezone || eveActivity;
}

export function isL3arnApplicationRole(
    value: string,
): value is L3arnApplicationRole {
    return (L3ARN_APPLICATION_ROLES as readonly string[]).includes(value);
}

export function normalizeL3arnApplicationRoles(value: unknown): string[] {
    if (Array.isArray(value)) {
        return value.map(String).filter(isL3arnApplicationRole);
    }

    return [];
}

export function l3arnApplicationRoleLabel(role: string): string {
    if (isL3arnApplicationRole(role)) {
        return L3ARN_APPLICATION_ROLE_LABELS[role];
    }

    return role;
}

export function formatL3arnApplicationRoles(roles: string[]): string {
    return roles
        .filter(isL3arnApplicationRole)
        .map(l3arnApplicationRoleLabel)
        .join(', ');
}

export function normalizeL3arnApplicationOtherCorporations(
    value: unknown,
): string[] {
    if (!Array.isArray(value)) {
        return [];
    }

    return [...new Set(value.map(String).map(trim).filter(Boolean))];
}

export function formatL3arnApplicationCorpConsideration(
    answers: Pick<L3arnApplicationAnswers, 'other_corporations'>,
): string {
    if (answers.other_corporations.length > 0) {
        return answers.other_corporations.join(', ');
    }

    return 'none';
}

export function filterL3arnApplicationAllianceCorporations(
    corporations: {
        corporation_id?: number;
        corporation_name?: string;
        active?: boolean;
    }[],
): { corporation_id: number; corporation_name: string }[] {
    return corporations
        .filter(
            (corporation) =>
                corporation.active !== false
                && corporation.corporation_id != null
                && corporation.corporation_name
                && L3ARN_MAIN_ALLIANCE_CORPORATIONS.includes(
                    corporation.corporation_name as typeof L3ARN_MAIN_ALLIANCE_CORPORATIONS[number],
                ),
        )
        .map((corporation) => ({
            corporation_id: corporation.corporation_id as number,
            corporation_name: corporation.corporation_name as string,
        }))
        .sort((left, right) =>
            left.corporation_name.localeCompare(right.corporation_name),
        );
}

function normalizeL3arnOtherCorporationsFromDraft(value: {
    only_l3arn?: unknown;
    other_corporations?: unknown;
}): string[] {
    if (value.only_l3arn === true) {
        return [];
    }

    if (
        typeof value.only_l3arn === 'string'
        && trim(value.only_l3arn).length > 0
    ) {
        return [];
    }

    return normalizeL3arnApplicationOtherCorporations(value.other_corporations);
}

function normalizeL3arnApplicationDisclosureFields(value: {
    is_existing_player_alt?: unknown;
    is_other_alliance_member?: unknown;
    main_character_name?: unknown;
    other_alliance_affiliation?: unknown;
}): Pick<
    L3arnApplicationAnswers,
    | 'is_existing_player_alt'
    | 'is_other_alliance_member'
    | 'main_character_name'
    | 'other_alliance_affiliation'
> {
    return {
        is_existing_player_alt: Boolean(value.is_existing_player_alt),
        is_other_alliance_member: Boolean(value.is_other_alliance_member),
        main_character_name: String(value.main_character_name ?? ''),
        other_alliance_affiliation: String(value.other_alliance_affiliation ?? ''),
    };
}

export function isL3arnApplicationHowFound(
    value: string,
): value is L3arnApplicationHowFound {
    return (L3ARN_APPLICATION_HOW_FOUND_OPTIONS as readonly string[]).includes(
        value,
    );
}

export function l3arnApplicationHowFoundLabel(howFound: string): string {
    if (isL3arnApplicationHowFound(howFound)) {
        return L3ARN_APPLICATION_HOW_FOUND_LABELS[howFound];
    }

    return howFound;
}

export function isL3arnApplicationHowFoundComplete(
    answers: Pick<L3arnApplicationAnswers, 'how_found' | 'how_found_other'>,
): boolean {
    const howFound = trim(answers.how_found);

    if (!isL3arnApplicationHowFound(howFound)) {
        return false;
    }

    if (howFound === 'other') {
        return trim(answers.how_found_other).length > 0;
    }

    return true;
}

export function formatL3arnApplicationHowFound(
    answers: Pick<L3arnApplicationAnswers, 'how_found' | 'how_found_other'>,
): string {
    const howFound = trim(answers.how_found);

    if (howFound === 'other') {
        const other = trim(answers.how_found_other);
        return other ? `Other: ${other}` : 'Other';
    }

    return l3arnApplicationHowFoundLabel(howFound);
}

export function isL3arnApplicationPayload(
    value: unknown,
): value is L3arnApplicationAnswers & { l3arn: true } {
    return (
        typeof value === 'object'
        && value !== null
        && 'l3arn' in value
        && (value as { l3arn?: boolean }).l3arn === true
    );
}

function trim(value: string): string {
    return value.trim();
}

export function formatL3arnApplicationDisclosure(
    answers: Pick<
        L3arnApplicationAnswers,
        | 'is_existing_player_alt'
        | 'is_other_alliance_member'
        | 'main_character_name'
        | 'other_alliance_affiliation'
    >,
): string[] {
    const lines: string[] = [];

    if (answers.is_existing_player_alt) {
        const mainCharacter = trim(answers.main_character_name);
        lines.push(
            mainCharacter
                ? `- Alt of existing player: Yes (main character: ${mainCharacter})`
                : '- Alt of existing player: Yes',
        );
    } else {
        lines.push('- Alt of existing player: No');
    }

    if (answers.is_other_alliance_member) {
        const affiliation = trim(answers.other_alliance_affiliation);
        lines.push(
            affiliation
                ? `- Member of another alliance: Yes (${affiliation})`
                : '- Member of another alliance: Yes',
        );
    } else {
        lines.push('- Member of another alliance: No');
    }

    return lines;
}

export function formatL3arnApplicationRequirements(
    answers: Pick<
        L3arnApplicationAnswers,
        'confirm_omega' | 'confirm_auth_chars' | 'agree_tenets'
    >,
): string[] {
    const lines: string[] = [];

    if (answers.confirm_omega) {
        lines.push('- ✅ Currently or intending to obtain Omega status');
    }
    if (answers.confirm_auth_chars) {
        lines.push(
            '- ✅ All characters added to website (including ones not joining)',
        );
    }
    if (answers.agree_tenets) {
        lines.push('- ✅ Agree to alliance values');
    }

    return lines;
}

export function estimateL3arnApplicationDescriptionLength(
    answers: Pick<
        L3arnApplicationAnswers,
        L3arnApplicationLimitedField | 'other_corporations'
    >,
): number {
    const userTextLength = (
        Object.keys(L3ARN_APPLICATION_FIELD_LIMITS) as L3arnApplicationLimitedField[]
    ).reduce((total, field) => total + answers[field].length, 0);
    const corpsLength = formatL3arnApplicationCorpConsideration({
        other_corporations: answers.other_corporations,
    }).length;

    return (
        L3ARN_APPLICATION_DESCRIPTION_FIXED_OVERHEAD
        + userTextLength
        + corpsLength
    );
}

export function isL3arnApplicationFieldWithinLimit(
    field: L3arnApplicationLimitedField,
    value: string,
): boolean {
    return value.length <= L3ARN_APPLICATION_FIELD_LIMITS[field];
}

export function areL3arnApplicationFieldsWithinLimits(
    answers: Pick<L3arnApplicationAnswers, L3arnApplicationLimitedField>,
): boolean {
    return (
        Object.keys(L3ARN_APPLICATION_FIELD_LIMITS) as L3arnApplicationLimitedField[]
    ).every((field) => isL3arnApplicationFieldWithinLimit(field, answers[field]));
}

export function isL3arnApplicationDescriptionWithinLimit(
    answers: L3arnApplicationAnswers,
): boolean {
    return (
        formatL3arnApplicationDescription(answers).length
        <= L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH
    );
}

export function isL3arnApplicationWithinLimits(
    answers: L3arnApplicationAnswers,
): boolean {
    return (
        areL3arnApplicationFieldsWithinLimits(answers)
        && isL3arnApplicationDescriptionWithinLimit(answers)
    );
}

export function isL3arnApplicationComplete(
    answers: L3arnApplicationAnswers,
): boolean {
    const resolved = withResolvedL3arnApplicationTimezone(answers);

    return (
        trim(answers.introduction).length > 0
        && isL3arnApplicationRegion(trim(answers.activity_region))
        && isL3arnApplicationActivityPeriod(trim(answers.activity_period))
        && isL3arnApplicationTimezone(resolved.timezone)
        && trim(answers.user_timezone).length > 0
        && answers.roles.some(isL3arnApplicationRole)
        && trim(answers.goals).length > 0
        && isL3arnApplicationHowFoundComplete(answers)
        && answers.agree_tenets
        && answers.confirm_omega
        && answers.confirm_auth_chars
        && isL3arnApplicationWithinLimits(resolved)
    );
}

export function formatL3arnApplicationDescription(
    answers: L3arnApplicationAnswers,
): string {
    const resolved = withResolvedL3arnApplicationTimezone(answers);
    const lines = [
        trim(answers.introduction),
        '',
        'Questionnaire:',
        `- Timezone: ${formatL3arnApplicationTimezoneLine(resolved)}`,
        `- Roles interested in: ${formatL3arnApplicationRoles(answers.roles)}`,
        `- Goals in EVE: ${trim(answers.goals)}`,
        `- Other corps considered: ${formatL3arnApplicationCorpConsideration(answers)}`,
        '',
        'Affiliation disclosure:',
        ...formatL3arnApplicationDisclosure(answers),
        '',
        'Requirements confirmed:',
        ...formatL3arnApplicationRequirements(answers),
    ];

    return lines.join('\n');
}

/** Stored description and recruiter web view; includes fields omitted from Discord. */
export function formatL3arnApplicationWebDescription(
    answers: L3arnApplicationAnswers,
): string {
    const resolved = withResolvedL3arnApplicationTimezone(answers);
    const lines = [
        trim(answers.introduction),
        '',
        'Questionnaire:',
        `- Timezone: ${formatL3arnApplicationTimezoneLine(resolved)}`,
        `- Roles interested in: ${formatL3arnApplicationRoles(answers.roles)}`,
        `- Goals in EVE: ${trim(answers.goals)}`,
        `- How I found you: ${formatL3arnApplicationHowFound(answers)}`,
        `- Other corps considered: ${formatL3arnApplicationCorpConsideration(answers)}`,
        '',
        'Affiliation disclosure:',
        ...formatL3arnApplicationDisclosure(answers),
        '',
        'Requirements confirmed:',
        ...formatL3arnApplicationRequirements(answers),
    ];

    return lines.join('\n');
}

export function l3arnAnswersFromFormData(formData: FormData): L3arnApplicationAnswers {
    const answers: L3arnApplicationAnswers = {
        introduction: String(formData.get(`${L3ARN_FORM_PREFIX}introduction`) ?? ''),
        activity_region: String(
            formData.get(`${L3ARN_FORM_PREFIX}activity_region`) ?? '',
        ),
        activity_period: String(
            formData.get(`${L3ARN_FORM_PREFIX}activity_period`) ?? '',
        ),
        timezone: String(formData.get(`${L3ARN_FORM_PREFIX}timezone`) ?? ''),
        user_timezone: String(
            formData.get(`${L3ARN_FORM_PREFIX}user_timezone`) ?? '',
        ),
        roles: formData
            .getAll(`${L3ARN_FORM_PREFIX}roles`)
            .map(String)
            .filter(isL3arnApplicationRole),
        goals: String(formData.get(`${L3ARN_FORM_PREFIX}goals`) ?? ''),
        how_found: String(formData.get(`${L3ARN_FORM_PREFIX}how_found`) ?? ''),
        how_found_other: String(
            formData.get(`${L3ARN_FORM_PREFIX}how_found_other`) ?? '',
        ),
        other_corporations: formData
            .getAll(`${L3ARN_FORM_PREFIX}other_corporations`)
            .map(String)
            .map(trim)
            .filter(Boolean),
        is_existing_player_alt:
            formData.get(`${L3ARN_FORM_PREFIX}is_existing_player_alt`) === 'on',
        is_other_alliance_member:
            formData.get(`${L3ARN_FORM_PREFIX}is_other_alliance_member`) === 'on',
        main_character_name: String(
            formData.get(`${L3ARN_FORM_PREFIX}main_character_name`) ?? '',
        ),
        other_alliance_affiliation: String(
            formData.get(`${L3ARN_FORM_PREFIX}other_alliance_affiliation`) ?? '',
        ),
        agree_tenets: formData.get(`${L3ARN_FORM_PREFIX}agree_tenets`) === 'on',
        confirm_omega: formData.get(`${L3ARN_FORM_PREFIX}confirm_omega`) === 'on',
        confirm_auth_chars:
            formData.get(`${L3ARN_FORM_PREFIX}confirm_auth_chars`) === 'on',
    };

    return withResolvedL3arnApplicationTimezone(answers);
}

export function l3arnAnswersFromPayload(value: unknown): L3arnApplicationAnswers {
    if (!isL3arnApplicationPayload(value)) {
        throw new Error('Invalid L3ARN application payload.');
    }

    const answers: L3arnApplicationAnswers = {
        introduction: String(value.introduction ?? ''),
        activity_region: String(value.activity_region ?? ''),
        activity_period: String(value.activity_period ?? ''),
        timezone: String(value.timezone ?? ''),
        user_timezone: String(value.user_timezone ?? ''),
        roles: normalizeL3arnApplicationRoles(value.roles),
        goals: String(value.goals ?? ''),
        how_found: String(value.how_found ?? ''),
        how_found_other: String(value.how_found_other ?? ''),
        other_corporations: normalizeL3arnOtherCorporationsFromDraft(value),
        ...normalizeL3arnApplicationDisclosureFields(value),
        agree_tenets: Boolean(value.agree_tenets),
        confirm_omega: Boolean(value.confirm_omega),
        confirm_auth_chars: Boolean(value.confirm_auth_chars),
    };

    return withResolvedL3arnApplicationTimezone(answers);
}

export function descriptionFromL3arnFormData(formData: FormData): string {
    const answers = l3arnAnswersFromFormData(formData);

    if (!areL3arnApplicationFieldsWithinLimits(answers)) {
        throw new Error('L3ARN application text exceeds the maximum length for one or more fields.');
    }

    if (!isL3arnApplicationDescriptionWithinLimit(answers)) {
        throw new Error('L3ARN application text exceeds the maximum length for Discord.');
    }

    if (!isL3arnApplicationComplete(answers)) {
        throw new Error('Please complete all required L3ARN application fields.');
    }

    return formatL3arnApplicationWebDescription(answers);
}

export function descriptionFromL3arnPayload(value: unknown): string {
    const answers = l3arnAnswersFromPayload(value);

    if (!areL3arnApplicationFieldsWithinLimits(answers)) {
        throw new Error('L3ARN application text exceeds the maximum length for one or more fields.');
    }

    if (!isL3arnApplicationDescriptionWithinLimit(answers)) {
        throw new Error('L3ARN application text exceeds the maximum length for Discord.');
    }

    if (!isL3arnApplicationComplete(answers)) {
        throw new Error('Please complete all required L3ARN application fields.');
    }

    return formatL3arnApplicationWebDescription(answers);
}

export function l3arnApplicationToDraftPayload(
    answers: L3arnApplicationAnswers,
): L3arnApplicationAnswers & { l3arn: true } {
    return {
        l3arn: true,
        ...answers,
    };
}

export function parseL3arnApplicationDraft(
    raw: string | null,
): L3arnApplicationAnswers | null {
    if (!raw) {
        return null;
    }

    try {
        const parsed = JSON.parse(raw);

        if (!isL3arnApplicationPayload(parsed)) {
            return null;
        }

        return l3arnAnswersFromPayload(parsed);
    } catch {
        return null;
    }
}

export function serializeL3arnApplicationDraft(
    answers: L3arnApplicationAnswers,
): string {
    return JSON.stringify(l3arnApplicationToDraftPayload(answers));
}

export function hasL3arnApplicationDraftContent(
    answers: L3arnApplicationAnswers,
): boolean {
    return (
        L3ARN_APPLICATION_STRING_FIELDS.some(
            (field) => trim(answers[field]).length > 0,
        )
        || L3ARN_APPLICATION_ARRAY_FIELDS.some(
            (field) => answers[field].length > 0,
        )
        || L3ARN_APPLICATION_BOOLEAN_FIELDS.some((field) => answers[field])
    );
}

function l3arnDraftRestoreAlpineBlock(): string {
    return [
        ...L3ARN_APPLICATION_STRING_FIELDS.map(
            (field) => `this.${field} = saved.${field} ?? '';`,
        ),
        ...L3ARN_APPLICATION_ARRAY_FIELDS.map(
            (field) => `this.${field} = Array.isArray(saved.${field}) ? saved.${field} : [];`,
        ),
        ...L3ARN_APPLICATION_BOOLEAN_FIELDS.map(
            (field) => `this.${field} = Boolean(saved.${field});`,
        ),
    ].join('\n                        ');
}

function l3arnDraftHasContentAlpineExpression(): string {
    const stringChecks = L3ARN_APPLICATION_STRING_FIELDS.map(
        (field) => `payload.${field}?.trim()`,
    ).join(' || ');
    const arrayChecks = L3ARN_APPLICATION_ARRAY_FIELDS.map(
        (field) => `payload.${field}?.length`,
    ).join(' || ');
    const booleanChecks = L3ARN_APPLICATION_BOOLEAN_FIELDS.map(
        (field) => `payload.${field}`,
    ).join(' || ');

    return `Boolean(${stringChecks} || ${arrayChecks} || ${booleanChecks})`;
}

export function l3arnApplicationAlpineState(dialogMode: boolean): string {
    const dialogUpdate = dialogMode
        ? `
            if (typeof confirm_dialog_hx !== 'undefined') {
                confirm_dialog_hx.vals = JSON.stringify(this.buildDescriptionPayload());
            }
            if (typeof confirm_dialog_set_accept_disable === 'function') {
                confirm_dialog_set_accept_disable(this.error);
            }
        `
        : '';
    const regionValues = L3ARN_APPLICATION_REGIONS.map(
        (region) => `'${region}'`,
    ).join(', ');
    const periodValues = L3ARN_APPLICATION_ACTIVITY_PERIODS.map(
        (period) => `'${period}'`,
    ).join(', ');
    const regionPeriodMapping = JSON.stringify(L3ARN_REGION_PERIOD_TO_TIMEZONE);
    const howFoundValues = L3ARN_APPLICATION_HOW_FOUND_OPTIONS.map(
        (option) => `'${option}'`,
    ).join(', ');
    const fieldLimits = JSON.stringify(L3ARN_APPLICATION_FIELD_LIMITS);
    const descriptionMaxLength = L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH;
    const descriptionFixedOverhead = L3ARN_APPLICATION_DESCRIPTION_FIXED_OVERHEAD;
    const regionLabels = JSON.stringify(L3ARN_APPLICATION_REGION_LABELS);
    const timezoneLabels = JSON.stringify(L3ARN_APPLICATION_TIMEZONE_LABELS);
    const timezoneEveWindows = JSON.stringify(L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS);

    return `{
        introduction: '',
        activity_region: '',
        activity_period: '',
        timezone: '',
        user_timezone: '',
        roles: [],
        goals: '',
        how_found: '',
        how_found_other: '',
        other_corporations: [],
        is_existing_player_alt: false,
        is_other_alliance_member: false,
        main_character_name: '',
        other_alliance_affiliation: '',
        agree_tenets: false,
        confirm_omega: false,
        confirm_auth_chars: false,
        error: true,
        detectActivityRegion() {
            try {
                const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
                if (
                    timeZone.startsWith('America/')
                    || timeZone === 'Pacific/Honolulu'
                    || timeZone === 'Pacific/Pago_Pago'
                    || timeZone === 'Pacific/Midway'
                ) {
                    return 'US';
                }
                if (
                    timeZone.startsWith('Asia/')
                    || timeZone.startsWith('Australia/')
                    || (
                        timeZone.startsWith('Pacific/')
                        && timeZone !== 'Pacific/Honolulu'
                        && timeZone !== 'Pacific/Pago_Pago'
                        && timeZone !== 'Pacific/Midway'
                    )
                ) {
                    return 'AP';
                }
                return 'EU';
            } catch (error) {
                const utcOffsetHours = -new Date().getTimezoneOffset() / 60;
                if (utcOffsetHours <= -2) {
                    return 'US';
                }
                if (utcOffsetHours >= 5) {
                    return 'AP';
                }
                return 'EU';
            }
        },
        detectUserTimezone() {
            try {
                return Intl.DateTimeFormat().resolvedOptions().timeZone || '';
            } catch (error) {
                return '';
            }
        },
        userTimezoneLabel() {
            if (!this.user_timezone) {
                return '';
            }
            try {
                const offsetLabel = new Intl.DateTimeFormat('en-US', {
                    timeZone: this.user_timezone,
                    timeZoneName: 'short',
                })
                    .formatToParts(new Date())
                    .find((part) => part.type === 'timeZoneName')?.value;
                return offsetLabel
                    ? \`\${this.user_timezone} (\${offsetLabel})\`
                    : this.user_timezone;
            } catch (error) {
                return this.user_timezone;
            }
        },
        syncTimezoneFromActivity() {
            const mapping = ${regionPeriodMapping};
            if (
                [${regionValues}].includes(this.activity_region)
                && [${periodValues}].includes(this.activity_period)
            ) {
                this.timezone = mapping[this.activity_region][this.activity_period];
            } else {
                this.timezone = '';
            }
        },
        activityRegionLabel() {
            const labels = ${regionLabels};
            return labels[this.activity_region] || '';
        },
        timezoneBucketLabel() {
            const labels = ${timezoneLabels};
            return this.timezone ? (labels[this.timezone] || '') : '';
        },
        timezoneEveWindow() {
            const windows = ${timezoneEveWindows};
            return this.timezone ? (windows[this.timezone] || '') : '';
        },
        fieldWithinLimit(field) {
            const limits = ${fieldLimits};
            return (this[field]?.length ?? 0) <= limits[field];
        },
        fieldsWithinLimits() {
            const limits = ${fieldLimits};
            return Object.keys(limits).every(
                (field) => (this[field]?.length ?? 0) <= limits[field],
            );
        },
        descriptionWithinLimit() {
            const limits = ${fieldLimits};
            const userTextLength = Object.keys(limits).reduce(
                (total, field) => total + (this[field]?.length ?? 0),
                0,
            );
            const corpsLength = (this.other_corporations || []).join(', ').length || 4;
            return (
                ${descriptionFixedOverhead} + userTextLength + corpsLength
                <= ${descriptionMaxLength}
            );
        },
        answersReady() {
            this.syncTimezoneFromActivity();
            return Boolean(
                this.introduction?.trim()
                && this.user_timezone
                && [${regionValues}].includes(this.activity_region)
                && [${periodValues}].includes(this.activity_period)
                && this.timezone
                && this.roles?.length
                && this.goals?.trim()
                && [${howFoundValues}].includes(this.how_found)
                && (this.how_found !== 'other' || this.how_found_other?.trim())
                && this.agree_tenets
                && this.confirm_omega
                && this.confirm_auth_chars
                && this.fieldsWithinLimits()
                && this.descriptionWithinLimit()
            );
        },
        buildDescriptionPayload() {
            this.syncTimezoneFromActivity();
            return {
                l3arn: true,
                introduction: this.introduction,
                activity_region: this.activity_region,
                activity_period: this.activity_period,
                timezone: this.timezone,
                user_timezone: this.user_timezone,
                roles: this.roles,
                goals: this.goals,
                how_found: this.how_found,
                how_found_other: this.how_found_other,
                other_corporations: this.other_corporations,
                is_existing_player_alt: this.is_existing_player_alt,
                is_other_alliance_member: this.is_other_alliance_member,
                main_character_name: this.main_character_name,
                other_alliance_affiliation: this.other_alliance_affiliation,
                agree_tenets: this.agree_tenets,
                confirm_omega: this.confirm_omega,
                confirm_auth_chars: this.confirm_auth_chars,
            };
        },
        initL3arnForm() {
            try {
                const raw = sessionStorage.getItem('${L3ARN_APPLICATION_DRAFT_STORAGE_KEY}');
                if (raw) {
                    const saved = JSON.parse(raw);
                    if (saved && saved.l3arn === true) {
                        ${l3arnDraftRestoreAlpineBlock()}
                    }
                }
            } catch (error) {}
            this.user_timezone = this.detectUserTimezone();
            this.activity_region = this.detectActivityRegion();
            this.syncTimezoneFromActivity();
            this.updateApplicationStatus();
        },
        persistL3arnForm() {
            const payload = this.buildDescriptionPayload();
            const hasContent = ${l3arnDraftHasContentAlpineExpression()};

            try {
                if (hasContent) {
                    sessionStorage.setItem(
                        '${L3ARN_APPLICATION_DRAFT_STORAGE_KEY}',
                        JSON.stringify(payload),
                    );
                } else {
                    sessionStorage.removeItem('${L3ARN_APPLICATION_DRAFT_STORAGE_KEY}');
                }
            } catch (error) {}
        },
        onExistingPlayerAltChange() {
            if (!this.is_existing_player_alt) {
                this.main_character_name = '';
            }
            this.updateApplicationStatus();
        },
        onOtherAllianceMemberChange() {
            if (!this.is_other_alliance_member) {
                this.other_alliance_affiliation = '';
            }
            this.updateApplicationStatus();
        },
        updateApplicationStatus() {
            this.syncTimezoneFromActivity();
            this.error = !this.answersReady();
            this.persistL3arnForm();
            ${dialogUpdate}
        },
        clearL3arnForm() {
            this.introduction = '';
            this.activity_region = this.detectActivityRegion();
            this.activity_period = '';
            this.timezone = '';
            this.user_timezone = this.detectUserTimezone();
            this.roles = [];
            this.goals = '';
            this.how_found = '';
            this.how_found_other = '';
            this.other_corporations = [];
            this.is_existing_player_alt = false;
            this.is_other_alliance_member = false;
            this.main_character_name = '';
            this.other_alliance_affiliation = '';
            this.agree_tenets = false;
            this.confirm_omega = false;
            this.confirm_auth_chars = false;
            try {
                sessionStorage.removeItem('${L3ARN_APPLICATION_DRAFT_STORAGE_KEY}');
            } catch (error) {}
            this.updateApplicationStatus();
        }
    }`;
}
