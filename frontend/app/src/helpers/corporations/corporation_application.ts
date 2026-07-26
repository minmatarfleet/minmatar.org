import {
    DISCORD_MESSAGE_MAX_LENGTH,
    L3ARN_APPLICATION_ACTIVITY_PERIODS,
    L3ARN_APPLICATION_COUNTER_THRESHOLD_OFFSET,
    L3ARN_APPLICATION_DISCORD_METADATA_OVERHEAD,
    L3ARN_APPLICATION_HOW_FOUND_OPTIONS,
    L3ARN_APPLICATION_REGIONS,
    L3ARN_APPLICATION_ROLES,
    L3ARN_REGION_PERIOD_TO_TIMEZONE,
    L3ARN_APPLICATION_REGION_LABELS,
    L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS,
    L3ARN_APPLICATION_TIMEZONE_LABELS,
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

export const EMPTY_CORPORATION_APPLICATION_ANSWERS: CorporationApplicationAnswers =
    {
        introduction: '',
        activity_region: '',
        activity_period: '',
        timezone: '',
        user_timezone: '',
        roles: [],
        doctrines: '',
        how_found: '',
        how_found_other: '',
        is_existing_player_alt: false,
        is_other_alliance_member: false,
        main_character_name: '',
        other_alliance_affiliation: '',
        agree_tenets: false,
        confirm_auth_chars: false,
    };

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

export function estimateCorporationApplicationDescriptionLength(
    answers: Pick<
        CorporationApplicationAnswers,
        CorporationApplicationLimitedField
    >,
): number {
    const userTextLength = (
        Object.keys(
            CORPORATION_APPLICATION_FIELD_LIMITS,
        ) as CorporationApplicationLimitedField[]
    ).reduce((total, field) => total + answers[field].length, 0);

    return CORPORATION_APPLICATION_DESCRIPTION_FIXED_OVERHEAD + userTextLength;
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

export function corporationApplicationAlpineState(dialogMode: boolean): string {
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
    const fieldLimits = JSON.stringify(CORPORATION_APPLICATION_FIELD_LIMITS);
    const descriptionMaxLength = CORPORATION_APPLICATION_DESCRIPTION_MAX_LENGTH;
    const descriptionFixedOverhead =
        CORPORATION_APPLICATION_DESCRIPTION_FIXED_OVERHEAD;
    const regionLabels = JSON.stringify(L3ARN_APPLICATION_REGION_LABELS);
    const timezoneLabels = JSON.stringify(L3ARN_APPLICATION_TIMEZONE_LABELS);
    const timezoneEveWindows = JSON.stringify(
        L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS,
    );
    const roleValues = L3ARN_APPLICATION_ROLES.map((role) => `'${role}'`).join(
        ', ',
    );

    return `{
        introduction: '',
        activity_region: '',
        activity_period: '',
        timezone: '',
        user_timezone: '',
        roles: [],
        doctrines: '',
        how_found: '',
        how_found_other: '',
        is_existing_player_alt: false,
        is_other_alliance_member: false,
        main_character_name: '',
        other_alliance_affiliation: '',
        agree_tenets: false,
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
            return (
                ${descriptionFixedOverhead} + userTextLength
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
                && this.roles?.some((role) => [${roleValues}].includes(role))
                && this.doctrines?.trim()
                && [${howFoundValues}].includes(this.how_found)
                && (this.how_found !== 'other' || this.how_found_other?.trim())
                && this.agree_tenets
                && this.confirm_auth_chars
                && this.fieldsWithinLimits()
                && this.descriptionWithinLimit()
            );
        },
        buildDescriptionPayload() {
            this.syncTimezoneFromActivity();
            return {
                corp_application: true,
                introduction: this.introduction,
                activity_region: this.activity_region,
                activity_period: this.activity_period,
                timezone: this.timezone,
                user_timezone: this.user_timezone,
                roles: this.roles,
                doctrines: this.doctrines,
                how_found: this.how_found,
                how_found_other: this.how_found_other,
                is_existing_player_alt: this.is_existing_player_alt,
                is_other_alliance_member: this.is_other_alliance_member,
                main_character_name: this.main_character_name,
                other_alliance_affiliation: this.other_alliance_affiliation,
                agree_tenets: this.agree_tenets,
                confirm_auth_chars: this.confirm_auth_chars,
            };
        },
        initCorpApplicationForm() {
            this.user_timezone = this.detectUserTimezone();
            this.activity_region = this.detectActivityRegion();
            this.syncTimezoneFromActivity();
            this.updateApplicationStatus();
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
            ${dialogUpdate}
        },
        clearCorpApplicationForm() {
            this.introduction = '';
            this.activity_region = this.detectActivityRegion();
            this.activity_period = '';
            this.timezone = '';
            this.user_timezone = this.detectUserTimezone();
            this.roles = [];
            this.doctrines = '';
            this.how_found = '';
            this.how_found_other = '';
            this.is_existing_player_alt = false;
            this.is_other_alliance_member = false;
            this.main_character_name = '';
            this.other_alliance_affiliation = '';
            this.agree_tenets = false;
            this.confirm_auth_chars = false;
            this.updateApplicationStatus();
        }
    }`;
}
