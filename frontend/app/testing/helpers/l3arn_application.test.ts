import { expect, test } from 'vitest';

import {
    descriptionFromL3arnFormData,
    descriptionFromL3arnPayload,
    formatL3arnApplicationDescription,
    isL3arnApplicationComplete,
    isL3arnCorporation,
    L3ARN_FORM_PREFIX,
} from '@helpers/corporations/l3arn_application';

const completeAnswers = {
    introduction: 'I want to learn FW PvP.',
    timezone: 'USTZ',
    roles: 'DPS',
    goals: 'Learn small gang and FW.',
    comfortable_comms: 'Yes',
    how_found: 'Reddit',
    only_l3arn: 'Yes, L3ARN is the best fit.',
    agree_tenets: true,
    confirm_omega: true,
    confirm_not_alt: true,
    confirm_not_dual_citizen: true,
    confirm_auth_chars: true,
};

test('isL3arnCorporation matches Minmatar Fleet Academy', () => {
    expect(
        isL3arnCorporation({ corporation_name: 'Minmatar Fleet Academy' }),
    ).toBe(true);
    expect(isL3arnCorporation({ corporation_name: 'Rattini Tribe' })).toBe(
        false,
    );
});

test('isL3arnApplicationComplete requires all fields', () => {
    expect(isL3arnApplicationComplete(completeAnswers)).toBe(true);
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            confirm_omega: false,
        }),
    ).toBe(false);
});

test('formatL3arnApplicationDescription renders questionnaire sections', () => {
    const description = formatL3arnApplicationDescription(completeAnswers);

    expect(description).toContain('Why I want to join:');
    expect(description).toContain('- Timezone: USTZ');
    expect(description).toContain('- Agree with Alliance Tenets: Yes');
});

test('descriptionFromL3arnFormData parses posted form fields', () => {
    const formData = new FormData();

    formData.set(`${L3ARN_FORM_PREFIX}introduction`, completeAnswers.introduction);
    formData.set(`${L3ARN_FORM_PREFIX}timezone`, completeAnswers.timezone);
    formData.set(`${L3ARN_FORM_PREFIX}roles`, completeAnswers.roles);
    formData.set(`${L3ARN_FORM_PREFIX}goals`, completeAnswers.goals);
    formData.set(`${L3ARN_FORM_PREFIX}comfortable_comms`, completeAnswers.comfortable_comms);
    formData.set(`${L3ARN_FORM_PREFIX}how_found`, completeAnswers.how_found);
    formData.set(`${L3ARN_FORM_PREFIX}only_l3arn`, completeAnswers.only_l3arn);
    formData.set(`${L3ARN_FORM_PREFIX}agree_tenets`, 'on');
    formData.set(`${L3ARN_FORM_PREFIX}confirm_omega`, 'on');
    formData.set(`${L3ARN_FORM_PREFIX}confirm_not_alt`, 'on');
    formData.set(`${L3ARN_FORM_PREFIX}confirm_not_dual_citizen`, 'on');
    formData.set(`${L3ARN_FORM_PREFIX}confirm_auth_chars`, 'on');

    const description = descriptionFromL3arnFormData(formData);

    expect(description).toContain('Why I want to join:');
    expect(description).toContain('I want to learn FW PvP.');
});

test('descriptionFromL3arnPayload parses dialog payload', () => {
    const description = descriptionFromL3arnPayload({
        l3arn: true,
        ...completeAnswers,
    });

    expect(description).toContain('- Roles interested in: DPS');
});
