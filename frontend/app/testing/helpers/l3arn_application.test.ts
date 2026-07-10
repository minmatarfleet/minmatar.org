import { expect, test } from 'vitest';

import {
    descriptionFromL3arnFormData,
    descriptionFromL3arnPayload,
    estimateL3arnApplicationDescriptionLength,
    filterL3arnApplicationAllianceCorporations,
    formatL3arnApplicationActivitySummary,
    formatL3arnApplicationCorpConsideration,
    formatL3arnApplicationDescription,
    formatL3arnApplicationDisclosure,
    formatL3arnApplicationHowFound,
    formatL3arnApplicationRequirements,
    formatL3arnApplicationRoles,
    detectL3arnApplicationUserTimezone,
    formatL3arnApplicationTimezoneLine,
    formatL3arnApplicationUserTimezoneLabel,
    formatL3arnApplicationWebDescription,
    hasL3arnApplicationDraftContent,
    isL3arnApplicationActivityPeriod,
    isL3arnApplicationComplete,
    isL3arnApplicationDescriptionWithinLimit,
    isL3arnApplicationFieldWithinLimit,
    isL3arnApplicationHowFound,
    isL3arnApplicationHowFoundComplete,
    isL3arnApplicationRegion,
    isL3arnApplicationRole,
    isL3arnApplicationTimezone,
    isL3arnApplicationWithinLimits,
    isL3arnCorporation,
    L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH,
    L3ARN_APPLICATION_FIELD_LIMITS,
    l3arnApplicationActivityPeriodLabel,
    l3arnApplicationHowFoundLabel,
    l3arnApplicationRegionLabel,
    l3arnApplicationRoleLabel,
    l3arnApplicationTimezoneLabel,
    l3arnApplicationTimezoneEveWindow,
    L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS,
    L3ARN_FORM_PREFIX,
    L3ARN_REGION_PERIOD_TO_TIMEZONE,
    mapL3arnRegionAndPeriodToTimezone,
    parseL3arnApplicationDraft,
    resolveL3arnApplicationTimezone,
    serializeL3arnApplicationDraft,
} from '@helpers/corporations/l3arn_application';

const completeAnswers = {
    introduction: 'I want to learn FW PvP.',
    activity_region: 'US',
    activity_period: 'evening',
    timezone: 'US',
    user_timezone: 'America/New_York',
    roles: ['fleet_damage', 'small_gang_combat'],
    goals: 'Learn small gang and FW.',
    how_found: 'reddit_post_seen',
    how_found_other: '',
    other_corporations: ['Rattini Tribe', 'Ironfleet Protocol'],
    is_existing_player_alt: false,
    is_other_alliance_member: false,
    main_character_name: '',
    other_alliance_affiliation: '',
    agree_tenets: true,
    confirm_omega: true,
    confirm_auth_chars: true,
};

test('filterL3arnApplicationAllianceCorporations includes only main alliance corps', () => {
    expect(
        filterL3arnApplicationAllianceCorporations([
            {
                corporation_id: 1,
                corporation_name: 'Minmatar Fleet Academy',
                active: true,
            },
            {
                corporation_id: 2,
                corporation_name: 'Minmatar Fleet Holdings',
                active: true,
            },
            {
                corporation_id: 3,
                corporation_name: 'Rattini Tribe',
                active: true,
            },
            {
                corporation_id: 4,
                corporation_name: 'Ironfleet Protocol',
                active: true,
            },
            {
                corporation_id: 5,
                corporation_name: 'Soltech Armada',
                active: true,
            },
            {
                corporation_id: 6,
                corporation_name: 'Straylight Systems',
                active: false,
            },
            {
                corporation_name: 'No ID Corp',
                active: true,
            },
        ]),
    ).toEqual([
        { corporation_id: 3, corporation_name: 'Rattini Tribe' },
        { corporation_id: 5, corporation_name: 'Soltech Armada' },
    ]);
});

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

test('isL3arnApplicationComplete requires at least one role', () => {
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            roles: [],
        }),
    ).toBe(false);
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            roles: ['not-a-role'],
        }),
    ).toBe(false);
});

test('formatL3arnApplicationCorpConsideration renders recruiter-friendly text', () => {
    expect(
        formatL3arnApplicationCorpConsideration({
            other_corporations: [],
        }),
    ).toBe('none');
    expect(
        formatL3arnApplicationCorpConsideration({
            other_corporations: ['Rattini Tribe', 'Ironfleet Protocol'],
        }),
    ).toBe('Rattini Tribe, Ironfleet Protocol');
});

test('isL3arnApplicationComplete does not require corp consideration', () => {
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            other_corporations: [],
        }),
    ).toBe(true);
});

test('isL3arnApplicationRole accepts known role codes', () => {
    expect(isL3arnApplicationRole('fleet_damage')).toBe(true);
    expect(isL3arnApplicationRole('production')).toBe(true);
    expect(isL3arnApplicationRole('DPS')).toBe(false);
});

test('l3arnApplicationRoleLabel maps codes to recruiter-friendly labels', () => {
    expect(l3arnApplicationRoleLabel('fleet_damage')).toBe(
        'Fleet damage (guns, missiles, etc)',
    );
    expect(l3arnApplicationRoleLabel('custom text')).toBe('custom text');
});

test('formatL3arnApplicationRoles renders comma-separated labels', () => {
    expect(
        formatL3arnApplicationRoles(['fleet_damage', 'small_gang_combat']),
    ).toBe(
        'Fleet damage (guns, missiles, etc), Small gang combat (<10 pilots)',
    );
    expect(formatL3arnApplicationRoles(['not-a-role'])).toBe('');
});

test('isL3arnApplicationHowFound accepts known option codes', () => {
    expect(isL3arnApplicationHowFound('reddit_post_seen')).toBe(true);
    expect(isL3arnApplicationHowFound('forum_post_made')).toBe(true);
    expect(isL3arnApplicationHowFound('other')).toBe(true);
    expect(isL3arnApplicationHowFound('Reddit')).toBe(false);
});

test('l3arnApplicationHowFoundLabel maps codes to recruiter-friendly labels', () => {
    expect(l3arnApplicationHowFoundLabel('reddit_post_seen')).toBe(
        'I saw a Reddit post by Minmatar Fleet',
    );
    expect(l3arnApplicationHowFoundLabel('forum_post_made')).toBe(
        'I made a forum post and received a response from Minmatar Fleet',
    );
    expect(l3arnApplicationHowFoundLabel('custom text')).toBe('custom text');
});

test('formatL3arnApplicationHowFound renders labels and other write-in', () => {
    expect(
        formatL3arnApplicationHowFound({
            how_found: 'reddit_post_seen',
            how_found_other: '',
        }),
    ).toBe('I saw a Reddit post by Minmatar Fleet');
    expect(
        formatL3arnApplicationHowFound({
            how_found: 'other',
            how_found_other: 'A friend told me',
        }),
    ).toBe('Other: A friend told me');
});

test('isL3arnApplicationHowFoundComplete requires option and other write-in', () => {
    expect(isL3arnApplicationHowFoundComplete(completeAnswers)).toBe(true);
    expect(
        isL3arnApplicationHowFoundComplete({
            ...completeAnswers,
            how_found: '',
            how_found_other: '',
        }),
    ).toBe(false);
    expect(
        isL3arnApplicationHowFoundComplete({
            ...completeAnswers,
            how_found: 'other',
            how_found_other: '',
        }),
    ).toBe(false);
    expect(
        isL3arnApplicationHowFoundComplete({
            ...completeAnswers,
            how_found: 'other',
            how_found_other: 'Discord invite',
        }),
    ).toBe(true);
});

test('isL3arnApplicationComplete requires valid how_found selection', () => {
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            how_found: 'not-an-option',
            how_found_other: '',
        }),
    ).toBe(false);
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            how_found: 'other',
            how_found_other: '',
        }),
    ).toBe(false);
});

test('isL3arnApplicationTimezone accepts alliance prime time values', () => {
    expect(isL3arnApplicationTimezone('US')).toBe(true);
    expect(isL3arnApplicationTimezone('EU_US')).toBe(true);
    expect(isL3arnApplicationTimezone('USTZ')).toBe(false);
});

test('l3arnApplicationTimezoneEveWindow maps buckets to UTC prime-time bands', () => {
    expect(l3arnApplicationTimezoneEveWindow('US')).toBe(
        'EVE prime time: roughly 22:00–04:59 UTC',
    );
    expect(l3arnApplicationTimezoneEveWindow('EU_US')).toBe(
        'EVE prime time: roughly 20:00–21:59 UTC',
    );
    expect(l3arnApplicationTimezoneEveWindow('AP_EU')).toBe(
        'EVE prime time: roughly 10:00–19:59 UTC (AUTZ–EUTZ overlap)',
    );
    expect(l3arnApplicationTimezoneEveWindow('invalid')).toBe('');
});

test('L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS covers every timezone bucket', () => {
    expect(Object.keys(L3ARN_APPLICATION_TIMEZONE_EVE_WINDOWS).sort()).toEqual(
        ['AP', 'AP_EU', 'EU', 'EU_US', 'US', 'US_AP'],
    );
});

test('l3arnApplicationTimezoneLabel maps codes to recruiter-friendly labels', () => {
    expect(l3arnApplicationTimezoneLabel('US')).toBe('USTZ');
    expect(l3arnApplicationTimezoneLabel('EU_US')).toBe('EUTZ - USTZ');
    expect(l3arnApplicationTimezoneLabel('custom text')).toBe('custom text');
});

test('isL3arnApplicationRegion and period accept known values', () => {
    expect(isL3arnApplicationRegion('US')).toBe(true);
    expect(isL3arnApplicationRegion('AP')).toBe(true);
    expect(isL3arnApplicationRegion('EU')).toBe(true);
    expect(isL3arnApplicationRegion('USTZ')).toBe(false);
    expect(isL3arnApplicationActivityPeriod('early_morning')).toBe(true);
    expect(isL3arnApplicationActivityPeriod('evening')).toBe(true);
    expect(isL3arnApplicationActivityPeriod('night')).toBe(false);
});

test('region and period labels are recruiter-friendly', () => {
    expect(l3arnApplicationRegionLabel('EU')).toBe('Europe');
    expect(l3arnApplicationActivityPeriodLabel('early_morning')).toBe(
        'early mornings',
    );
    expect(l3arnApplicationActivityPeriodLabel('morning')).toBe('mornings');
});

test('mapL3arnRegionAndPeriodToTimezone maps all region/period combinations', () => {
    expect(mapL3arnRegionAndPeriodToTimezone('US', 'early_morning')).toBe(
        'US_AP',
    );
    expect(mapL3arnRegionAndPeriodToTimezone('EU', 'early_morning')).toBe('US');
    expect(mapL3arnRegionAndPeriodToTimezone('AP', 'early_morning')).toBe('EU');
    expect(mapL3arnRegionAndPeriodToTimezone('US', 'evening')).toBe('US');
    expect(mapL3arnRegionAndPeriodToTimezone('EU', 'afternoon')).toBe('AP_EU');
    expect(mapL3arnRegionAndPeriodToTimezone('AP', 'morning')).toBe('EU_US');
    expect(L3ARN_REGION_PERIOD_TO_TIMEZONE.AP.evening).toBe('AP');
});

test('L3ARN_REGION_PERIOD_TO_TIMEZONE covers every region and period', () => {
    const regions = ['US', 'AP', 'EU'] as const;
    const periods = [
        'early_morning',
        'morning',
        'afternoon',
        'evening',
    ] as const;

    for (const region of regions) {
        for (const period of periods) {
            expect(L3ARN_REGION_PERIOD_TO_TIMEZONE[region][period]).toBeTruthy();
        }
    }
});

test('resolveL3arnApplicationTimezone derives bucket from region and period', () => {
    expect(
        resolveL3arnApplicationTimezone({
            activity_region: 'US',
            activity_period: 'morning',
        }),
    ).toBe('US_AP');
    expect(
        resolveL3arnApplicationTimezone({
            activity_region: 'invalid',
            activity_period: 'evening',
        }),
    ).toBe('');
});

test('formatL3arnApplicationUserTimezoneLabel formats IANA with offset abbreviation', () => {
    expect(
        formatL3arnApplicationUserTimezoneLabel(
            'America/New_York',
            new Date('2026-01-15T12:00:00Z'),
        ),
    ).toBe('America/New_York (EST)');
    expect(
        formatL3arnApplicationUserTimezoneLabel(
            'America/New_York',
            new Date('2026-07-15T12:00:00Z'),
        ),
    ).toBe('America/New_York (EDT)');
    expect(formatL3arnApplicationUserTimezoneLabel('')).toBe('');
});

test('formatL3arnApplicationTimezoneLine includes human timezone and EVE bucket', () => {
    expect(formatL3arnApplicationTimezoneLine({
        ...completeAnswers,
    })).toContain('America/New_York');
    expect(formatL3arnApplicationTimezoneLine({
        ...completeAnswers,
    })).toContain('US region, evenings → USTZ');
});

test('formatL3arnApplicationActivitySummary renders recruiter-friendly text', () => {
    expect(formatL3arnApplicationActivitySummary(completeAnswers)).toBe(
        'US region, evenings → USTZ',
    );
});

test('formatL3arnApplicationDescription renders questionnaire sections for Discord', () => {
    const description = formatL3arnApplicationDescription(completeAnswers);

    expect(description).toContain('I want to learn FW PvP.');
    expect(description).toContain('- Timezone: America/New_York');
    expect(description).toContain('US region, evenings → USTZ');
    expect(description).toContain(
        '- Roles interested in: Fleet damage (guns, missiles, etc), Small gang combat (<10 pilots)',
    );
    expect(description).toContain(
        '- Other corps considered: Rattini Tribe, Ironfleet Protocol',
    );
    expect(description).not.toContain('How I found you');
    expect(description).toContain('- ✅ Agree to alliance values');
    expect(description).toContain('Requirements confirmed:');
    expect(description).toContain('- ✅ Currently or intending to obtain Omega status');
    expect(description).not.toContain('Comfortable asking questions and on comms');
    expect(description).toContain('Affiliation disclosure:');
    expect(description).toContain('- Alt of existing player: No');
    expect(description).toContain('- Member of another alliance: No');
});

test('formatL3arnApplicationWebDescription includes how found for recruiter web view', () => {
    const description = formatL3arnApplicationWebDescription(completeAnswers);

    expect(description).toContain('- Timezone: America/New_York');
    expect(description).toContain('US region, evenings → USTZ');
    expect(description).toContain(
        '- How I found you: I saw a Reddit post by Minmatar Fleet',
    );
    expect(description).toContain('- Goals in EVE: Learn small gang and FW.');
    expect(description).toContain('- ✅ Agree to alliance values');
});

test('formatL3arnApplicationRequirements renders checkmarks for confirmed items', () => {
    expect(formatL3arnApplicationRequirements(completeAnswers)).toEqual([
        '- ✅ Currently or intending to obtain Omega status',
        '- ✅ All characters added to website (including ones not joining)',
        '- ✅ Agree to alliance values',
    ]);
    expect(
        formatL3arnApplicationRequirements({
            confirm_omega: true,
            confirm_auth_chars: false,
            agree_tenets: true,
        }),
    ).toEqual([
        '- ✅ Currently or intending to obtain Omega status',
        '- ✅ Agree to alliance values',
    ]);
    expect(
        formatL3arnApplicationRequirements({
            confirm_omega: false,
            confirm_auth_chars: false,
            agree_tenets: false,
        }),
    ).toEqual([]);
});

test('formatL3arnApplicationDisclosure renders optional disclosure details', () => {
    expect(formatL3arnApplicationDisclosure(completeAnswers)).toEqual([
        '- Alt of existing player: No',
        '- Member of another alliance: No',
    ]);
    expect(
        formatL3arnApplicationDisclosure({
            is_existing_player_alt: true,
            is_other_alliance_member: false,
            main_character_name: 'Main Pilot',
            other_alliance_affiliation: '',
        }),
    ).toEqual([
        '- Alt of existing player: Yes (main character: Main Pilot)',
        '- Member of another alliance: No',
    ]);
    expect(
        formatL3arnApplicationDisclosure({
            is_existing_player_alt: false,
            is_other_alliance_member: true,
            main_character_name: '',
            other_alliance_affiliation: 'Pandemic Horde',
        }),
    ).toEqual([
        '- Alt of existing player: No',
        '- Member of another alliance: Yes (Pandemic Horde)',
    ]);
});

test('isL3arnApplicationComplete does not require disclosure fields', () => {
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            is_existing_player_alt: true,
            is_other_alliance_member: true,
            main_character_name: '',
            other_alliance_affiliation: '',
        }),
    ).toBe(true);
});

test('isL3arnApplicationComplete requires user_timezone', () => {
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            user_timezone: '',
        }),
    ).toBe(false);
});

test('isL3arnApplicationComplete requires valid region and period', () => {
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            activity_region: 'not-a-region',
        }),
    ).toBe(false);
    expect(
        isL3arnApplicationComplete({
            ...completeAnswers,
            activity_period: 'not-a-period',
        }),
    ).toBe(false);
});

test('descriptionFromL3arnFormData parses posted form fields and derives timezone', () => {
    const formData = new FormData();

    formData.set(`${L3ARN_FORM_PREFIX}introduction`, completeAnswers.introduction);
    formData.set(
        `${L3ARN_FORM_PREFIX}activity_region`,
        completeAnswers.activity_region,
    );
    formData.set(
        `${L3ARN_FORM_PREFIX}activity_period`,
        completeAnswers.activity_period,
    );
    formData.set(
        `${L3ARN_FORM_PREFIX}user_timezone`,
        completeAnswers.user_timezone,
    );
    completeAnswers.roles.forEach((role) => {
        formData.append(`${L3ARN_FORM_PREFIX}roles`, role);
    });
    formData.set(`${L3ARN_FORM_PREFIX}goals`, completeAnswers.goals);
    formData.set(`${L3ARN_FORM_PREFIX}how_found`, completeAnswers.how_found);
    completeAnswers.other_corporations.forEach((corporation) => {
        formData.append(`${L3ARN_FORM_PREFIX}other_corporations`, corporation);
    });
    formData.set(`${L3ARN_FORM_PREFIX}agree_tenets`, 'on');
    formData.set(`${L3ARN_FORM_PREFIX}confirm_omega`, 'on');
    formData.set(`${L3ARN_FORM_PREFIX}confirm_auth_chars`, 'on');

    const description = descriptionFromL3arnFormData(formData);

    expect(description.startsWith('I want to learn FW PvP.')).toBe(true);
    expect(description).toContain('I want to learn FW PvP.');
    expect(description).toContain('America/New_York');
    expect(description).toContain('US region, evenings → USTZ');
    expect(description).toContain(
        'Fleet damage (guns, missiles, etc), Small gang combat (<10 pilots)',
    );
    expect(description).toContain('Rattini Tribe, Ironfleet Protocol');
    expect(description).toContain(
        '- How I found you: I saw a Reddit post by Minmatar Fleet',
    );
});

test('descriptionFromL3arnFormData omits other corps when none selected', () => {
    const formData = new FormData();

    formData.set(`${L3ARN_FORM_PREFIX}introduction`, completeAnswers.introduction);
    formData.set(
        `${L3ARN_FORM_PREFIX}activity_region`,
        completeAnswers.activity_region,
    );
    formData.set(
        `${L3ARN_FORM_PREFIX}activity_period`,
        completeAnswers.activity_period,
    );
    formData.set(
        `${L3ARN_FORM_PREFIX}user_timezone`,
        completeAnswers.user_timezone,
    );
    completeAnswers.roles.forEach((role) => {
        formData.append(`${L3ARN_FORM_PREFIX}roles`, role);
    });
    formData.set(`${L3ARN_FORM_PREFIX}goals`, completeAnswers.goals);
    formData.set(`${L3ARN_FORM_PREFIX}how_found`, completeAnswers.how_found);
    formData.set(`${L3ARN_FORM_PREFIX}agree_tenets`, 'on');
    formData.set(`${L3ARN_FORM_PREFIX}confirm_omega`, 'on');
    formData.set(`${L3ARN_FORM_PREFIX}confirm_auth_chars`, 'on');

    const description = descriptionFromL3arnFormData(formData);

    expect(description).toContain('- Other corps considered: none');
});

test('descriptionFromL3arnPayload parses dialog payload', () => {
    const description = descriptionFromL3arnPayload({
        l3arn: true,
        ...completeAnswers,
    });

    expect(description).toContain(
        '- Roles interested in: Fleet damage (guns, missiles, etc), Small gang combat (<10 pilots)',
    );
    expect(description).toContain('America/New_York');
    expect(description).toContain('US region, evenings → USTZ');
    expect(description).toContain('Rattini Tribe, Ironfleet Protocol');
    expect(description).toContain(
        '- How I found you: I saw a Reddit post by Minmatar Fleet',
    );
});

test('serialize and parse L3ARN application draft round-trip', () => {
    const serialized = serializeL3arnApplicationDraft(completeAnswers);
    const restored = parseL3arnApplicationDraft(serialized);

    expect(restored).toEqual(completeAnswers);
});

test('parseL3arnApplicationDraft rejects invalid payloads', () => {
    expect(parseL3arnApplicationDraft(null)).toBeNull();
    expect(parseL3arnApplicationDraft('not json')).toBeNull();
    expect(parseL3arnApplicationDraft(JSON.stringify({ l3arn: false }))).toBeNull();
});

test('parseL3arnApplicationDraft normalizes legacy string roles to empty array', () => {
    const restored = parseL3arnApplicationDraft(JSON.stringify({
        l3arn: true,
        ...completeAnswers,
        roles: 'DPS',
    }));

    expect(restored?.roles).toEqual([]);
});

test('parseL3arnApplicationDraft ignores legacy confirm_not_alt and confirm_not_dual_citizen keys', () => {
    const restored = parseL3arnApplicationDraft(JSON.stringify({
        l3arn: true,
        ...completeAnswers,
        confirm_not_alt: true,
        confirm_not_dual_citizen: true,
    }));

    expect(restored).toEqual(completeAnswers);
});

test('parseL3arnApplicationDraft ignores legacy comfortable_comms key', () => {
    const restored = parseL3arnApplicationDraft(JSON.stringify({
        l3arn: true,
        ...completeAnswers,
        comfortable_comms: true,
    }));

    expect(restored).toEqual(completeAnswers);
});

test('parseL3arnApplicationDraft normalizes legacy only_l3arn drafts', () => {
    const restored = parseL3arnApplicationDraft(JSON.stringify({
        l3arn: true,
        ...completeAnswers,
        only_l3arn: 'Yes, L3ARN is the best fit.',
        other_corporations: ['Rattini Tribe'],
    }));

    expect(restored?.other_corporations).toEqual([]);

    const restoredBoolean = parseL3arnApplicationDraft(JSON.stringify({
        l3arn: true,
        ...completeAnswers,
        only_l3arn: true,
        other_corporations: ['Rattini Tribe'],
    }));

    expect(restoredBoolean?.other_corporations).toEqual([]);
});

test('isL3arnApplicationFieldWithinLimit enforces per-field maxlength', () => {
    expect(
        isL3arnApplicationFieldWithinLimit(
            'introduction',
            'x'.repeat(L3ARN_APPLICATION_FIELD_LIMITS.introduction),
        ),
    ).toBe(true);
    expect(
        isL3arnApplicationFieldWithinLimit(
            'introduction',
            'x'.repeat(L3ARN_APPLICATION_FIELD_LIMITS.introduction + 1),
        ),
    ).toBe(false);
    expect(
        isL3arnApplicationFieldWithinLimit(
            'main_character_name',
            'x'.repeat(L3ARN_APPLICATION_FIELD_LIMITS.main_character_name),
        ),
    ).toBe(true);
});

test('isL3arnApplicationWithinLimits rejects over-limit formatted descriptions', () => {
    const overLimitAnswers = {
        ...completeAnswers,
        roles: [
            'fleet_damage',
            'fleet_logistics',
            'fleet_support',
            'solo_combat',
            'small_gang_combat',
            'resource_harvesting',
            'production',
        ],
        introduction: 'x'.repeat(500),
        goals: 'x'.repeat(400),
        how_found: 'other' as const,
        how_found_other: 'x'.repeat(120),
        other_corporations: Array.from(
            { length: 20 },
            (_, index) => `Corp Name Here ${String(index + 1).padStart(2, '0')}`,
        ),
        is_existing_player_alt: true,
        is_other_alliance_member: true,
        main_character_name: 'x'.repeat(37),
        other_alliance_affiliation: 'x'.repeat(40),
    };

    expect(
        formatL3arnApplicationDescription(overLimitAnswers).length,
    ).toBeGreaterThan(L3ARN_APPLICATION_DESCRIPTION_MAX_LENGTH);
    expect(isL3arnApplicationDescriptionWithinLimit(overLimitAnswers)).toBe(
        false,
    );
    expect(isL3arnApplicationWithinLimits(overLimitAnswers)).toBe(false);
    expect(isL3arnApplicationComplete(overLimitAnswers)).toBe(false);
});

test('descriptionFromL3arnPayload rejects over-limit field values', () => {
    expect(() =>
        descriptionFromL3arnPayload({
            l3arn: true,
            ...completeAnswers,
            introduction: 'x'.repeat(
                L3ARN_APPLICATION_FIELD_LIMITS.introduction + 1,
            ),
        }),
    ).toThrow('maximum length for one or more fields');
});

test('estimateL3arnApplicationDescriptionLength tracks user text and corp selections', () => {
    expect(
        estimateL3arnApplicationDescriptionLength({
            introduction: 'Hello',
            goals: 'Goals',
            how_found_other: '',
            main_character_name: '',
            other_alliance_affiliation: '',
            other_corporations: ['Rattini Tribe'],
        }),
    ).toBeGreaterThan(
        estimateL3arnApplicationDescriptionLength({
            introduction: 'Hello',
            goals: 'Goals',
            how_found_other: '',
            main_character_name: '',
            other_alliance_affiliation: '',
            other_corporations: [],
        }),
    );
});

test('hasL3arnApplicationDraftContent detects partial drafts', () => {
    expect(hasL3arnApplicationDraftContent(completeAnswers)).toBe(true);
    expect(
        hasL3arnApplicationDraftContent({
            ...completeAnswers,
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
            agree_tenets: false,
            confirm_omega: false,
            confirm_auth_chars: false,
        }),
    ).toBe(false);
    expect(
        hasL3arnApplicationDraftContent({
            ...completeAnswers,
            introduction: 'Still drafting',
            activity_region: '',
            activity_period: '',
            timezone: '',
            user_timezone: '',
            roles: [],
            goals: '',
            how_found: '',
            how_found_other: '',
            other_corporations: [],
            agree_tenets: false,
            confirm_omega: false,
            confirm_auth_chars: false,
        }),
    ).toBe(true);
    expect(
        hasL3arnApplicationDraftContent({
            ...completeAnswers,
            introduction: '',
            activity_region: '',
            activity_period: '',
            timezone: '',
            roles: ['fleet_logistics'],
            goals: '',
            how_found: '',
            how_found_other: '',
            other_corporations: [],
            agree_tenets: false,
            confirm_omega: false,
            confirm_auth_chars: false,
        }),
    ).toBe(true);
    expect(
        hasL3arnApplicationDraftContent({
            ...completeAnswers,
            introduction: '',
            activity_region: '',
            activity_period: '',
            timezone: '',
            user_timezone: '',
            roles: [],
            goals: '',
            how_found: '',
            how_found_other: '',
            other_corporations: ['Rattini Tribe'],
            agree_tenets: false,
            confirm_omega: false,
            confirm_auth_chars: false,
        }),
    ).toBe(true);
});
