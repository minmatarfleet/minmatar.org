import {
    DISCORD_MESSAGE_MAX_LENGTH,
    L3ARN_APPLICATION_COUNTER_THRESHOLD_OFFSET,
    L3ARN_APPLICATION_DISCORD_METADATA_OVERHEAD,
    formatL3arnApplicationDisclosure,
    formatL3arnApplicationHowFound,
    formatL3arnApplicationRoles,
    formatL3arnApplicationTimezoneLine,
    isL3arnApplicationActivityPeriod,
    isL3arnApplicationHowFoundComplete,
    isL3arnApplicationRegion,
    isL3arnApplicationRole,
    isL3arnApplicationTimezone,
    isL3arnCorporation,
    normalizeL3arnApplicationRoles,
    withResolvedL3arnApplicationTimezone,
    type L3arnApplicationAnswers,
} from '@helpers/corporations/l3arn_application';

export {
    DISCORD_MESSAGE_MAX_LENGTH,
    L3ARN_APPLICATION_COUNTER_THRESHOLD_OFFSET as CORPORATION_APPLICATION_COUNTER_THRESHOLD_OFFSET,
    isL3arnCorporation,
};

/** Max length of the formatted corp application description stored and posted to Discord. */
export const CORPORATION_APPLICATION_DESCRIPTION_MAX_LENGTH =
    DISCORD_MESSAGE_MAX_LENGTH - L3ARN_APPLICATION_DISCORD_METADATA_OVERHEAD;

/** Per-field maxlength for user-editable text inputs on the shared corp form. */
export const CORPORATION_APPLICATION_FIELD_LIMITS = {
    introduction: 300,
    doctrines: 250,
    how_found_other: 80,
    main_character_name: 37,
    other_alliance_affiliation: 40,
} as const;

export type CorporationApplicationLimitedField =
    keyof typeof CORPORATION_APPLICATION_FIELD_LIMITS;

/**
 * Fixed template overhead for the Discord-bound formatted description
 * (labels/sections; excludes how_found and user-editable field bodies).
 */
export const CORPORATION_APPLICATION_DESCRIPTION_FIXED_OVERHEAD = 620;

export const CORPORATION_APPLICATION_FORM_PREFIX = 'corp_app_';

export interface CorporationApplicationAnswers {
    introduction: string;
    activity_region: string;
    activity_period: string;
    /** EVE prime-time bucket derived from region + activity period. */
    timezone: string;
    /** Applicant IANA timezone from the browser, e.g. America/New_York. */
    user_timezone: string;
    roles: string[];
    doctrines: string;
    how_found: string;
    how_found_other: string;
    is_existing_player_alt: boolean;
    is_other_alliance_member: boolean;
    main_character_name: string;
    other_alliance_affiliation: string;
    agree_tenets: boolean;
    confirm_auth_chars: boolean;
}

function trim(value: string): string {
    return value.trim();
}

function withResolvedTimezone(
    answers: CorporationApplicationAnswers,
): CorporationApplicationAnswers {
    const resolved = withResolvedL3arnApplicationTimezone(
        answers as unknown as L3arnApplicationAnswers,
    );

    return {
        ...answers,
        timezone: resolved.timezone || answers.timezone,
    };
}

export function isCorporationApplicationPayload(
    value: unknown,
): value is CorporationApplicationAnswers & { corp_application: true } {
    return (
        typeof value === 'object'
        && value !== null
        && 'corp_application' in value
        && (value as { corp_application?: boolean }).corp_application === true
    );
}

export function formatCorporationApplicationRequirements(
    answers: Pick<CorporationApplicationAnswers, 'confirm_auth_chars' | 'agree_tenets'>,
): string[] {
    const lines: string[] = [];

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

export function isCorporationApplicationFieldWithinLimit(
    field: CorporationApplicationLimitedField,
    value: string,
): boolean {
    return value.length <= CORPORATION_APPLICATION_FIELD_LIMITS[field];
}

export function areCorporationApplicationFieldsWithinLimits(
    answers: Pick<CorporationApplicationAnswers, CorporationApplicationLimitedField>,
): boolean {
    return (
        Object.keys(
            CORPORATION_APPLICATION_FIELD_LIMITS,
        ) as CorporationApplicationLimitedField[]
    ).every((field) =>
        isCorporationApplicationFieldWithinLimit(field, answers[field]),
    );
}

export function isCorporationApplicationDescriptionWithinLimit(
    answers: CorporationApplicationAnswers,
): boolean {
    return (
        formatCorporationApplicationDescription(answers).length
        <= CORPORATION_APPLICATION_DESCRIPTION_MAX_LENGTH
    );
}

export function isCorporationApplicationWithinLimits(
    answers: CorporationApplicationAnswers,
): boolean {
    return (
        areCorporationApplicationFieldsWithinLimits(answers)
        && isCorporationApplicationDescriptionWithinLimit(answers)
    );
}

export function isCorporationApplicationComplete(
    answers: CorporationApplicationAnswers,
): boolean {
    const resolved = withResolvedTimezone(answers);

    return (
        trim(answers.introduction).length > 0
        && isL3arnApplicationRegion(trim(answers.activity_region))
        && isL3arnApplicationActivityPeriod(trim(answers.activity_period))
        && isL3arnApplicationTimezone(resolved.timezone)
        && trim(answers.user_timezone).length > 0
        && answers.roles.some(isL3arnApplicationRole)
        && trim(answers.doctrines).length > 0
        && isL3arnApplicationHowFoundComplete(answers)
        && answers.agree_tenets
        && answers.confirm_auth_chars
        && isCorporationApplicationWithinLimits(resolved)
    );
}

/** Discord-bound description; omits how_found (web-only analytics). */
export function formatCorporationApplicationDescription(
    answers: CorporationApplicationAnswers,
): string {
    const resolved = withResolvedTimezone(answers);
    const lines = [
        trim(answers.introduction),
        '',
        'Questionnaire:',
        `- Timezone: ${formatL3arnApplicationTimezoneLine(resolved)}`,
        `- Roles interested in: ${formatL3arnApplicationRoles(answers.roles)}`,
        `- Doctrine ships: ${trim(answers.doctrines)}`,
        '',
        'Affiliation disclosure:',
        ...formatL3arnApplicationDisclosure(answers),
        '',
        'Requirements confirmed:',
        ...formatCorporationApplicationRequirements(answers),
    ];

    return lines.join('\n');
}

/** Stored description and recruiter web view; includes fields omitted from Discord. */
export function formatCorporationApplicationWebDescription(
    answers: CorporationApplicationAnswers,
): string {
    const resolved = withResolvedTimezone(answers);
    const lines = [
        trim(answers.introduction),
        '',
        'Questionnaire:',
        `- Timezone: ${formatL3arnApplicationTimezoneLine(resolved)}`,
        `- Roles interested in: ${formatL3arnApplicationRoles(answers.roles)}`,
        `- Doctrine ships: ${trim(answers.doctrines)}`,
        `- How I found you: ${formatL3arnApplicationHowFound(answers)}`,
        '',
        'Affiliation disclosure:',
        ...formatL3arnApplicationDisclosure(answers),
        '',
        'Requirements confirmed:',
        ...formatCorporationApplicationRequirements(answers),
    ];

    return lines.join('\n');
}

function normalizeDisclosureFields(value: {
    is_existing_player_alt?: unknown;
    is_other_alliance_member?: unknown;
    main_character_name?: unknown;
    other_alliance_affiliation?: unknown;
}): Pick<
    CorporationApplicationAnswers,
    | 'is_existing_player_alt'
    | 'is_other_alliance_member'
    | 'main_character_name'
    | 'other_alliance_affiliation'
> {
    return {
        is_existing_player_alt: Boolean(value.is_existing_player_alt),
        is_other_alliance_member: Boolean(value.is_other_alliance_member),
        main_character_name: String(value.main_character_name ?? ''),
        other_alliance_affiliation: String(
            value.other_alliance_affiliation ?? '',
        ),
    };
}

export function corporationAnswersFromFormData(
    formData: FormData,
): CorporationApplicationAnswers {
    const answers: CorporationApplicationAnswers = {
        introduction: String(
            formData.get(`${CORPORATION_APPLICATION_FORM_PREFIX}introduction`)
                ?? '',
        ),
        activity_region: String(
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}activity_region`,
            ) ?? '',
        ),
        activity_period: String(
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}activity_period`,
            ) ?? '',
        ),
        timezone: String(
            formData.get(`${CORPORATION_APPLICATION_FORM_PREFIX}timezone`)
                ?? '',
        ),
        user_timezone: String(
            formData.get(`${CORPORATION_APPLICATION_FORM_PREFIX}user_timezone`)
                ?? '',
        ),
        roles: formData
            .getAll(`${CORPORATION_APPLICATION_FORM_PREFIX}roles`)
            .map(String)
            .filter(isL3arnApplicationRole),
        doctrines: String(
            formData.get(`${CORPORATION_APPLICATION_FORM_PREFIX}doctrines`)
                ?? '',
        ),
        how_found: String(
            formData.get(`${CORPORATION_APPLICATION_FORM_PREFIX}how_found`)
                ?? '',
        ),
        how_found_other: String(
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}how_found_other`,
            ) ?? '',
        ),
        is_existing_player_alt:
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}is_existing_player_alt`,
            ) === 'on',
        is_other_alliance_member:
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}is_other_alliance_member`,
            ) === 'on',
        main_character_name: String(
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}main_character_name`,
            ) ?? '',
        ),
        other_alliance_affiliation: String(
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}other_alliance_affiliation`,
            ) ?? '',
        ),
        agree_tenets:
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}agree_tenets`,
            ) === 'on',
        confirm_auth_chars:
            formData.get(
                `${CORPORATION_APPLICATION_FORM_PREFIX}confirm_auth_chars`,
            ) === 'on',
    };

    return withResolvedTimezone(answers);
}

export function corporationAnswersFromPayload(
    value: unknown,
): CorporationApplicationAnswers {
    if (!isCorporationApplicationPayload(value)) {
        throw new Error('Invalid corporation application payload.');
    }

    const answers: CorporationApplicationAnswers = {
        introduction: String(value.introduction ?? ''),
        activity_region: String(value.activity_region ?? ''),
        activity_period: String(value.activity_period ?? ''),
        timezone: String(value.timezone ?? ''),
        user_timezone: String(value.user_timezone ?? ''),
        roles: normalizeL3arnApplicationRoles(value.roles),
        doctrines: String(value.doctrines ?? ''),
        how_found: String(value.how_found ?? ''),
        how_found_other: String(value.how_found_other ?? ''),
        ...normalizeDisclosureFields(value),
        agree_tenets: Boolean(value.agree_tenets),
        confirm_auth_chars: Boolean(value.confirm_auth_chars),
    };

    return withResolvedTimezone(answers);
}

export function descriptionFromCorporationFormData(formData: FormData): string {
    const answers = corporationAnswersFromFormData(formData);

    if (!areCorporationApplicationFieldsWithinLimits(answers)) {
        throw new Error(
            'Corporation application text exceeds the maximum length for one or more fields.',
        );
    }

    if (!isCorporationApplicationDescriptionWithinLimit(answers)) {
        throw new Error(
            'Corporation application text exceeds the maximum length for Discord.',
        );
    }

    if (!isCorporationApplicationComplete(answers)) {
        throw new Error(
            'Please complete all required corporation application fields.',
        );
    }

    return formatCorporationApplicationWebDescription(answers);
}

export function descriptionFromCorporationPayload(value: unknown): string {
    const answers = corporationAnswersFromPayload(value);

    if (!areCorporationApplicationFieldsWithinLimits(answers)) {
        throw new Error(
            'Corporation application text exceeds the maximum length for one or more fields.',
        );
    }

    if (!isCorporationApplicationDescriptionWithinLimit(answers)) {
        throw new Error(
            'Corporation application text exceeds the maximum length for Discord.',
        );
    }

    if (!isCorporationApplicationComplete(answers)) {
        throw new Error(
            'Please complete all required corporation application fields.',
        );
    }

    return formatCorporationApplicationWebDescription(answers);
}
