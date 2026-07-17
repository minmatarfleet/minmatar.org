import { expect, test } from 'vitest';

import {
    areCorporationApplicationFieldsWithinLimits,
    CORPORATION_APPLICATION_DESCRIPTION_FIXED_OVERHEAD,
    CORPORATION_APPLICATION_DESCRIPTION_MAX_LENGTH,
    CORPORATION_APPLICATION_FIELD_LIMITS,
    CORPORATION_APPLICATION_FORM_PREFIX,
    corporationAnswersFromFormData,
    corporationAnswersFromPayload,
    descriptionFromCorporationFormData,
    descriptionFromCorporationPayload,
    estimateCorporationApplicationDescriptionLength,
    formatCorporationApplicationDescription,
    formatCorporationApplicationRequirements,
    formatCorporationApplicationWebDescription,
    isCorporationApplicationComplete,
    isCorporationApplicationDescriptionWithinLimit,
    isCorporationApplicationPayload,
    isL3arnCorporation,
} from '@helpers/corporations/corporation_application';

const completeAnswers = {
    introduction: 'I want to fly with your fleets.',
    activity_region: 'US',
    activity_period: 'evening',
    timezone: 'US',
    user_timezone: 'America/New_York',
    roles: ['fleet_damage', 'fleet_logistics'],
    doctrines: 'CFI, Stabber Fleet Issue, Scythe',
    how_found: 'reddit_post_seen',
    how_found_other: '',
    is_existing_player_alt: false,
    is_other_alliance_member: false,
    main_character_name: '',
    other_alliance_affiliation: '',
    agree_tenets: true,
    confirm_auth_chars: true,
};

test('isL3arnCorporation is false for regular alliance corps', () => {
    expect(isL3arnCorporation({ corporation_name: 'Rattini Tribe' })).toBe(
        false,
    );
});

test('isCorporationApplicationComplete requires shared fields without omega', () => {
    expect(isCorporationApplicationComplete(completeAnswers)).toBe(true);
    expect(
        isCorporationApplicationComplete({
            ...completeAnswers,
            doctrines: '',
        }),
    ).toBe(false);
    expect(
        isCorporationApplicationComplete({
            ...completeAnswers,
            agree_tenets: false,
        }),
    ).toBe(false);
});

test('formatCorporationApplicationWebDescription includes how_found and doctrines', () => {
    const web = formatCorporationApplicationWebDescription(completeAnswers);
    expect(web).toContain('Doctrine ships: CFI, Stabber Fleet Issue, Scythe');
    expect(web).toContain('How I found you:');
    expect(web).not.toContain('Omega status');
});

test('formatCorporationApplicationDescription omits how_found for Discord', () => {
    const discord = formatCorporationApplicationDescription(completeAnswers);
    expect(discord).toContain('Doctrine ships:');
    expect(discord).not.toContain('How I found you:');
    expect(discord).not.toContain('Omega status');
});

test('formatCorporationApplicationRequirements excludes omega', () => {
    expect(
        formatCorporationApplicationRequirements({
            agree_tenets: true,
            confirm_auth_chars: true,
        }),
    ).toEqual([
        '- ✅ All characters added to website (including ones not joining)',
        '- ✅ Agree to alliance values',
    ]);
});

test('fixed overhead estimate covers Discord description length', () => {
    const emptyLimited = {
        introduction: '',
        doctrines: '',
        how_found_other: '',
        main_character_name: '',
        other_alliance_affiliation: '',
    };
    const answers = {
        ...completeAnswers,
        ...emptyLimited,
        roles: ['fleet_damage'],
    };
    const actual = formatCorporationApplicationDescription(answers).length;
    const estimate = estimateCorporationApplicationDescriptionLength({
        ...emptyLimited,
    });

    expect(CORPORATION_APPLICATION_DESCRIPTION_FIXED_OVERHEAD).toBeGreaterThanOrEqual(
        actual,
    );
    expect(estimate).toBeGreaterThanOrEqual(actual);
});

test('isCorporationApplicationDescriptionWithinLimit respects Discord max', () => {
    expect(isCorporationApplicationDescriptionWithinLimit(completeAnswers)).toBe(
        true,
    );
    expect(
        CORPORATION_APPLICATION_DESCRIPTION_MAX_LENGTH,
    ).toBeLessThanOrEqual(1700);
});

test('areCorporationApplicationFieldsWithinLimits enforces per-field caps', () => {
    expect(areCorporationApplicationFieldsWithinLimits(completeAnswers)).toBe(
        true,
    );
    expect(
        areCorporationApplicationFieldsWithinLimits({
            ...completeAnswers,
            doctrines: 'x'.repeat(
                CORPORATION_APPLICATION_FIELD_LIMITS.doctrines + 1,
            ),
        }),
    ).toBe(false);
});

test('isCorporationApplicationPayload requires corp_application marker', () => {
    expect(
        isCorporationApplicationPayload({
            corp_application: true,
            ...completeAnswers,
        }),
    ).toBe(true);
    expect(
        isCorporationApplicationPayload({
            l3arn: true,
            ...completeAnswers,
        }),
    ).toBe(false);
});

test('descriptionFromCorporationPayload formats complete answers', () => {
    const description = descriptionFromCorporationPayload({
        corp_application: true,
        ...completeAnswers,
    });
    expect(description).toContain(completeAnswers.introduction);
    expect(description).toContain('Doctrine ships:');
    expect(description).toContain('How I found you:');
});

test('descriptionFromCorporationFormData reads corp_app_ fields', () => {
    const formData = new FormData();
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}introduction`,
        completeAnswers.introduction,
    );
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}activity_region`,
        completeAnswers.activity_region,
    );
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}activity_period`,
        completeAnswers.activity_period,
    );
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}timezone`,
        completeAnswers.timezone,
    );
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}user_timezone`,
        completeAnswers.user_timezone,
    );
    for (const role of completeAnswers.roles) {
        formData.append(
            `${CORPORATION_APPLICATION_FORM_PREFIX}roles`,
            role,
        );
    }
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}doctrines`,
        completeAnswers.doctrines,
    );
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}how_found`,
        completeAnswers.how_found,
    );
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}agree_tenets`,
        'on',
    );
    formData.set(
        `${CORPORATION_APPLICATION_FORM_PREFIX}confirm_auth_chars`,
        'on',
    );

    const answers = corporationAnswersFromFormData(formData);
    expect(answers.doctrines).toBe(completeAnswers.doctrines);
    expect(descriptionFromCorporationFormData(formData)).toContain(
        'Doctrine ships:',
    );
});

test('corporationAnswersFromPayload resolves timezone from activity', () => {
    const answers = corporationAnswersFromPayload({
        corp_application: true,
        ...completeAnswers,
        timezone: '',
    });
    expect(answers.timezone).toBe('US');
});
