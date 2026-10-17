/**
 * Alpine state for the corporation application forms (the shared corp form
 * and the L3ARN academy form). Both forms run the same state machine:
 * activity region/period to timezone, Discord length budget, ready check,
 * payload. The differences are a config.
 */
import {
    L3ARN_APPLICATION_ACTIVITY_PERIODS,
    L3ARN_APPLICATION_ARRAY_FIELDS,
    L3ARN_APPLICATION_BOOLEAN_FIELDS,
    L3ARN_APPLICATION_DESCRIPTION_FIXED_OVERHEAD,
    L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH,
    L3ARN_APPLICATION_DRAFT_STORAGE_KEY,
    L3ARN_APPLICATION_FIELD_LIMITS,
    L3ARN_APPLICATION_HOW_FOUND_OPTIONS,
    L3ARN_APPLICATION_REGIONS,
    L3ARN_APPLICATION_REGION_LABELS,
    L3ARN_APPLICATION_ROLES,
    L3ARN_APPLICATION_STRING_FIELDS,
    L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS,
    L3ARN_APPLICATION_TIMEZONE_LABELS,
    L3ARN_REGION_PERIOD_TO_TIMEZONE,
} from '@helpers/corporations/l3arn_application';
import {
    CORPORATION_APPLICATION_DESCRIPTION_FIXED_OVERHEAD,
    CORPORATION_APPLICATION_DESCRIPTION_MAX_LENGTH,
    CORPORATION_APPLICATION_FIELD_LIMITS,
} from '@helpers/corporations/corporation_application';

type FieldInitial = "''" | '[]' | 'false';

/** Session-storage draft for a form (L3ARN only today). */
export interface ApplicationDraftConfig {
    storage_key: string;
    /** Payload marker the saved draft must carry to be restored. */
    marker: string;
    string_fields: readonly string[];
    array_fields: readonly string[];
    boolean_fields: readonly string[];
    persist_method: string;
}

export interface ApplicationFormConfig {
    /** `true` flag that marks the payload as this form's. */
    payload_marker: string;
    /** State fields in declaration (and payload) order. */
    fields: ReadonlyArray<readonly [name: string, initial: FieldInitial]>;
    field_limits: Readonly<Record<string, number>>;
    description_max_length: number;
    description_fixed_overhead: number;
    /** Count the listed other corporations against the Discord budget. */
    count_other_corporations: boolean;
    /** JS expression that is truthy when the roles answer is complete. */
    roles_ready: string;
    /** Free-text answer that must not be blank (doctrines / goals). */
    answer_field: string;
    /** Confirmation checkboxes besides agree_tenets and confirm_auth_chars. */
    extra_confirmations: readonly string[];
    init_method: string;
    clear_method: string;
    draft?: ApplicationDraftConfig;
}

const quoted_list = (values: readonly string[]) =>
    values.map((value) => `'${value}'`).join(', ');

const CLEAR_VALUES: Record<string, string> = {
    activity_region: 'this.detectActivityRegion()',
    user_timezone: 'this.detectUserTimezone()',
};

function draft_restore_block(draft: ApplicationDraftConfig): string {
    return [
        ...draft.string_fields.map(
            (field) => `this.${field} = saved.${field} ?? '';`,
        ),
        ...draft.array_fields.map(
            (field) => `this.${field} = Array.isArray(saved.${field}) ? saved.${field} : [];`,
        ),
        ...draft.boolean_fields.map(
            (field) => `this.${field} = Boolean(saved.${field});`,
        ),
    ].join('\n                        ');
}

function draft_has_content_expression(draft: ApplicationDraftConfig): string {
    const stringChecks = draft.string_fields.map(
        (field) => `payload.${field}?.trim()`,
    ).join(' || ');
    const arrayChecks = draft.array_fields.map(
        (field) => `payload.${field}?.length`,
    ).join(' || ');
    const booleanChecks = draft.boolean_fields.map(
        (field) => `payload.${field}`,
    ).join(' || ');

    return `Boolean(${stringChecks} || ${arrayChecks} || ${booleanChecks})`;
}

/** Alpine `x-data` object source for an application form. */
export function applicationAlpineState(
    config: ApplicationFormConfig,
    dialogMode: boolean,
): string {
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
    const regionValues = quoted_list(L3ARN_APPLICATION_REGIONS);
    const periodValues = quoted_list(L3ARN_APPLICATION_ACTIVITY_PERIODS);
    const regionPeriodMapping = JSON.stringify(L3ARN_REGION_PERIOD_TO_TIMEZONE);
    const howFoundValues = quoted_list(L3ARN_APPLICATION_HOW_FOUND_OPTIONS);
    const fieldLimits = JSON.stringify(config.field_limits);
    const regionLabels = JSON.stringify(L3ARN_APPLICATION_REGION_LABELS);
    const timezoneLabels = JSON.stringify(L3ARN_APPLICATION_TIMEZONE_LABELS);
    const timezoneEveWindows = JSON.stringify(L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS);
    const draft = config.draft;

    const stateFields = config.fields
        .map(([name, initial]) => `        ${name}: ${initial},\n`)
        .join('');
    const payloadFields = config.fields
        .map(([name]) => `                ${name}: this.${name},\n`)
        .join('');
    const clearFields = config.fields
        .map(([name, initial]) => `            this.${name} = ${CLEAR_VALUES[name] ?? initial};\n`)
        .join('');
    const confirmations = config.extra_confirmations
        .map((name) => `                && this.${name}\n`)
        .join('');

    const corpsLength = config.count_other_corporations
        ? `            const corpsLength = (this.other_corporations || []).join(', ').length || 4;\n`
        : '';
    const corpsTerm = config.count_other_corporations ? ' + corpsLength' : '';

    const draftRestore = draft
        ? `            try {
                const raw = sessionStorage.getItem('${draft.storage_key}');
                if (raw) {
                    const saved = JSON.parse(raw);
                    if (saved && saved.${draft.marker} === true) {
                        ${draft_restore_block(draft)}
                    }
                }
            } catch (error) {}
`
        : '';
    const persistMethod = draft
        ? `        ${draft.persist_method}() {
            const payload = this.buildDescriptionPayload();
            const hasContent = ${draft_has_content_expression(draft)};

            try {
                if (hasContent) {
                    sessionStorage.setItem(
                        '${draft.storage_key}',
                        JSON.stringify(payload),
                    );
                } else {
                    sessionStorage.removeItem('${draft.storage_key}');
                }
            } catch (error) {}
        },
`
        : '';
    const persistCall = draft ? `            this.${draft.persist_method}();\n` : '';
    const draftClear = draft
        ? `            try {
                sessionStorage.removeItem('${draft.storage_key}');
            } catch (error) {}
`
        : '';

    return `{
${stateFields}        error: true,
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
${corpsLength}            return (
                ${config.description_fixed_overhead} + userTextLength${corpsTerm}
                <= ${config.description_max_length}
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
                && ${config.roles_ready}
                && this.${config.answer_field}?.trim()
                && [${howFoundValues}].includes(this.how_found)
                && (this.how_found !== 'other' || this.how_found_other?.trim())
                && this.agree_tenets
${confirmations}                && this.confirm_auth_chars
                && this.fieldsWithinLimits()
                && this.descriptionWithinLimit()
            );
        },
        buildDescriptionPayload() {
            this.syncTimezoneFromActivity();
            return {
                ${config.payload_marker}: true,
${payloadFields}            };
        },
        ${config.init_method}() {
${draftRestore}            this.user_timezone = this.detectUserTimezone();
            this.activity_region = this.detectActivityRegion();
            this.syncTimezoneFromActivity();
            this.updateApplicationStatus();
        },
${persistMethod}        onExistingPlayerAltChange() {
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
${persistCall}            ${dialogUpdate}
        },
        ${config.clear_method}() {
${clearFields}${draftClear}            this.updateApplicationStatus();
        }
    }`;
}

export const CORPORATION_APPLICATION_FORM: ApplicationFormConfig = {
    payload_marker: 'corp_application',
    fields: [
        ['introduction', "''"],
        ['activity_region', "''"],
        ['activity_period', "''"],
        ['timezone', "''"],
        ['user_timezone', "''"],
        ['roles', '[]'],
        ['doctrines', "''"],
        ['how_found', "''"],
        ['how_found_other', "''"],
        ['is_existing_player_alt', 'false'],
        ['is_other_alliance_member', 'false'],
        ['main_character_name', "''"],
        ['other_alliance_affiliation', "''"],
        ['agree_tenets', 'false'],
        ['confirm_auth_chars', 'false'],
    ],
    field_limits: CORPORATION_APPLICATION_FIELD_LIMITS,
    description_max_length: CORPORATION_APPLICATION_DESCRIPTION_MAX_LENGTH,
    description_fixed_overhead: CORPORATION_APPLICATION_DESCRIPTION_FIXED_OVERHEAD,
    count_other_corporations: false,
    roles_ready: `this.roles?.some((role) => [${quoted_list(L3ARN_APPLICATION_ROLES)}].includes(role))`,
    answer_field: 'doctrines',
    extra_confirmations: [],
    init_method: 'initCorpApplicationForm',
    clear_method: 'clearCorpApplicationForm',
};

export const L3ARN_APPLICATION_FORM: ApplicationFormConfig = {
    payload_marker: 'l3arn',
    fields: [
        ['introduction', "''"],
        ['activity_region', "''"],
        ['activity_period', "''"],
        ['timezone', "''"],
        ['user_timezone', "''"],
        ['roles', '[]'],
        ['goals', "''"],
        ['how_found', "''"],
        ['how_found_other', "''"],
        ['other_corporations', '[]'],
        ['is_existing_player_alt', 'false'],
        ['is_other_alliance_member', 'false'],
        ['main_character_name', "''"],
        ['other_alliance_affiliation', "''"],
        ['agree_tenets', 'false'],
        ['confirm_omega', 'false'],
        ['confirm_auth_chars', 'false'],
    ],
    field_limits: L3ARN_APPLICATION_FIELD_LIMITS,
    description_max_length: L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH,
    description_fixed_overhead: L3ARN_APPLICATION_DESCRIPTION_FIXED_OVERHEAD,
    count_other_corporations: true,
    roles_ready: 'this.roles?.length',
    answer_field: 'goals',
    extra_confirmations: ['confirm_omega'],
    init_method: 'initL3arnForm',
    clear_method: 'clearL3arnForm',
    draft: {
        storage_key: L3ARN_APPLICATION_DRAFT_STORAGE_KEY,
        marker: 'l3arn',
        string_fields: L3ARN_APPLICATION_STRING_FIELDS,
        array_fields: L3ARN_APPLICATION_ARRAY_FIELDS,
        boolean_fields: L3ARN_APPLICATION_BOOLEAN_FIELDS,
        persist_method: 'persistL3arnForm',
    },
};

export function corporationApplicationAlpineState(dialogMode: boolean): string {
    return applicationAlpineState(CORPORATION_APPLICATION_FORM, dialogMode);
}

export function l3arnApplicationAlpineState(dialogMode: boolean): string {
    return applicationAlpineState(L3ARN_APPLICATION_FORM, dialogMode);
}
