export const L3ARN_CORPORATION_NAME = 'Minmatar Fleet Academy';

export const L3ARN_FORM_PREFIX = 'l3arn_';

export interface L3arnApplicationAnswers {
    introduction: string;
    timezone: string;
    roles: string;
    goals: string;
    comfortable_comms: string;
    how_found: string;
    only_l3arn: string;
    agree_tenets: boolean;
    confirm_omega: boolean;
    confirm_not_alt: boolean;
    confirm_not_dual_citizen: boolean;
    confirm_auth_chars: boolean;
}

export const EMPTY_L3ARN_APPLICATION_ANSWERS: L3arnApplicationAnswers = {
    introduction: '',
    timezone: '',
    roles: '',
    goals: '',
    comfortable_comms: '',
    how_found: '',
    only_l3arn: '',
    agree_tenets: false,
    confirm_omega: false,
    confirm_not_alt: false,
    confirm_not_dual_citizen: false,
    confirm_auth_chars: false,
};

export function isL3arnCorporation(corporation: {
    corporation_name?: string;
}): boolean {
    return corporation.corporation_name === L3ARN_CORPORATION_NAME;
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

export function isL3arnApplicationComplete(
    answers: L3arnApplicationAnswers,
): boolean {
    return (
        trim(answers.introduction).length > 0
        && trim(answers.timezone).length > 0
        && trim(answers.roles).length > 0
        && trim(answers.goals).length > 0
        && trim(answers.comfortable_comms).length > 0
        && trim(answers.how_found).length > 0
        && trim(answers.only_l3arn).length > 0
        && answers.agree_tenets
        && answers.confirm_omega
        && answers.confirm_not_alt
        && answers.confirm_not_dual_citizen
        && answers.confirm_auth_chars
    );
}

export function formatL3arnApplicationDescription(
    answers: L3arnApplicationAnswers,
): string {
    const lines = [
        'Why I want to join:',
        trim(answers.introduction),
        '',
        'Questionnaire:',
        `- Timezone: ${trim(answers.timezone)}`,
        `- Roles interested in: ${trim(answers.roles)}`,
        `- Goals in EVE: ${trim(answers.goals)}`,
        `- Comfortable asking questions and on comms: ${trim(answers.comfortable_comms)}`,
        `- How I found you: ${trim(answers.how_found)}`,
        `- Only checked L3ARN / other corps considered: ${trim(answers.only_l3arn)}`,
        '',
        'Requirements confirmed:',
        `- Omega account: ${answers.confirm_omega ? 'Yes' : 'No'}`,
        `- Not an alt of an existing player: ${answers.confirm_not_alt ? 'Yes' : 'No'}`,
        `- Not a dual-citizen (no active alts in other alliances): ${answers.confirm_not_dual_citizen ? 'Yes' : 'No'}`,
        `- All characters added to Auth: ${answers.confirm_auth_chars ? 'Yes' : 'No'}`,
        `- Agree with Alliance Tenets: ${answers.agree_tenets ? 'Yes' : 'No'}`,
    ];

    return lines.join('\n');
}

export function l3arnAnswersFromFormData(formData: FormData): L3arnApplicationAnswers {
    return {
        introduction: String(formData.get(`${L3ARN_FORM_PREFIX}introduction`) ?? ''),
        timezone: String(formData.get(`${L3ARN_FORM_PREFIX}timezone`) ?? ''),
        roles: String(formData.get(`${L3ARN_FORM_PREFIX}roles`) ?? ''),
        goals: String(formData.get(`${L3ARN_FORM_PREFIX}goals`) ?? ''),
        comfortable_comms: String(
            formData.get(`${L3ARN_FORM_PREFIX}comfortable_comms`) ?? '',
        ),
        how_found: String(formData.get(`${L3ARN_FORM_PREFIX}how_found`) ?? ''),
        only_l3arn: String(formData.get(`${L3ARN_FORM_PREFIX}only_l3arn`) ?? ''),
        agree_tenets: formData.get(`${L3ARN_FORM_PREFIX}agree_tenets`) === 'on',
        confirm_omega: formData.get(`${L3ARN_FORM_PREFIX}confirm_omega`) === 'on',
        confirm_not_alt: formData.get(`${L3ARN_FORM_PREFIX}confirm_not_alt`) === 'on',
        confirm_not_dual_citizen:
            formData.get(`${L3ARN_FORM_PREFIX}confirm_not_dual_citizen`) === 'on',
        confirm_auth_chars:
            formData.get(`${L3ARN_FORM_PREFIX}confirm_auth_chars`) === 'on',
    };
}

export function l3arnAnswersFromPayload(value: unknown): L3arnApplicationAnswers {
    if (!isL3arnApplicationPayload(value)) {
        throw new Error('Invalid L3ARN application payload.');
    }

    return {
        introduction: String(value.introduction ?? ''),
        timezone: String(value.timezone ?? ''),
        roles: String(value.roles ?? ''),
        goals: String(value.goals ?? ''),
        comfortable_comms: String(value.comfortable_comms ?? ''),
        how_found: String(value.how_found ?? ''),
        only_l3arn: String(value.only_l3arn ?? ''),
        agree_tenets: Boolean(value.agree_tenets),
        confirm_omega: Boolean(value.confirm_omega),
        confirm_not_alt: Boolean(value.confirm_not_alt),
        confirm_not_dual_citizen: Boolean(value.confirm_not_dual_citizen),
        confirm_auth_chars: Boolean(value.confirm_auth_chars),
    };
}

export function descriptionFromL3arnFormData(formData: FormData): string {
    const answers = l3arnAnswersFromFormData(formData);

    if (!isL3arnApplicationComplete(answers)) {
        throw new Error('Please complete all required L3ARN application fields.');
    }

    return formatL3arnApplicationDescription(answers);
}

export function descriptionFromL3arnPayload(value: unknown): string {
    const answers = l3arnAnswersFromPayload(value);

    if (!isL3arnApplicationComplete(answers)) {
        throw new Error('Please complete all required L3ARN application fields.');
    }

    return formatL3arnApplicationDescription(answers);
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

    return `{
        introduction: '',
        timezone: '',
        roles: '',
        goals: '',
        comfortable_comms: '',
        how_found: '',
        only_l3arn: '',
        agree_tenets: false,
        confirm_omega: false,
        confirm_not_alt: false,
        confirm_not_dual_citizen: false,
        confirm_auth_chars: false,
        error: true,
        answersReady() {
            return Boolean(
                this.introduction?.trim()
                && this.timezone?.trim()
                && this.roles?.trim()
                && this.goals?.trim()
                && this.comfortable_comms?.trim()
                && this.how_found?.trim()
                && this.only_l3arn?.trim()
                && this.agree_tenets
                && this.confirm_omega
                && this.confirm_not_alt
                && this.confirm_not_dual_citizen
                && this.confirm_auth_chars
            );
        },
        buildDescriptionPayload() {
            return {
                l3arn: true,
                introduction: this.introduction,
                timezone: this.timezone,
                roles: this.roles,
                goals: this.goals,
                comfortable_comms: this.comfortable_comms,
                how_found: this.how_found,
                only_l3arn: this.only_l3arn,
                agree_tenets: this.agree_tenets,
                confirm_omega: this.confirm_omega,
                confirm_not_alt: this.confirm_not_alt,
                confirm_not_dual_citizen: this.confirm_not_dual_citizen,
                confirm_auth_chars: this.confirm_auth_chars,
            };
        },
        updateApplicationStatus() {
            this.error = !this.answersReady();
            ${dialogUpdate}
        },
        clearL3arnForm() {
            this.introduction = '';
            this.timezone = '';
            this.roles = '';
            this.goals = '';
            this.comfortable_comms = '';
            this.how_found = '';
            this.only_l3arn = '';
            this.agree_tenets = false;
            this.confirm_omega = false;
            this.confirm_not_alt = false;
            this.confirm_not_dual_citizen = false;
            this.confirm_auth_chars = false;
            this.updateApplicationStatus();
        }
    }`;
}
