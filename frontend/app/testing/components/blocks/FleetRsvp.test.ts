import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { describe, expect, test } from 'vitest'

import FleetRsvpForm from '@components/blocks/fleet_rsvp/FleetRsvpForm.astro'
import FleetRsvpResult from '@components/blocks/fleet_rsvp/FleetRsvpResult.astro'
import FleetRsvpExpired from '@components/blocks/fleet_rsvp/FleetRsvpExpired.astro'
import type { RsvpCharacter, RsvpFleet, RsvpForm } from '@dtypes/api.minmatar.org'

const fleet: RsvpFleet = {
    id: 1,
    title: 'Friday Night Fights',
    type: 'strategic',
    type_label: 'Strategic Fleet',
    invite_only: true,
    start_time: '2026-11-13T19:00:00Z',
    formup: 'Amamake',
    doctrine: 'PHOONS',
    fc_name: 'Vex Drake',
    fc_character_id: 9,
    wanted: [],
}

const character = (overrides: Partial<RsvpCharacter>): RsvpCharacter => ({
    character_id: 11,
    name: 'Bear',
    account: null,
    fits: [
        { key: 'f:1', name: '[FL33T] Typhoon', ship_id: 644, ship_name: 'Typhoon', role: 'dps', fitting_id: 1, fleet_fitting_id: null },
        { key: 'f:2', name: '[FL33T] Guardian', ship_id: 11987, ship_name: 'Guardian', role: 'logi', fitting_id: 2, fleet_fitting_id: null },
    ],
    suggested_key: 'f:2',
    suggested_fleets: 5,
    picked: true,
    picked_key: '',
    ...overrides,
})

const form = (overrides: Partial<RsvpForm> = {}): RsvpForm => ({
    fleet,
    pilot_name: 'Bear',
    pilot_character_id: 11,
    characters: [
        character({}),
        character({ character_id: 22, name: 'Sashii', picked: false, suggested_key: '', suggested_fleets: 0 }),
    ],
    hidden_count: 12,
    any_ship: false,
    answer: 'pending',
    confidence: '',
    submit_token: 'submit-token-abcdefghijklmnop',
    ...overrides,
})

const render = async (component: any, props: Record<string, unknown>) => {
    const container = await AstroContainer.create()
    return container.renderToString(component, { props })
}

const props = { page_token: 'page-token-abcdefghijklmnopq', partial_url: '/partials/fleet_rsvp_component/' }

describe('FleetRsvpForm', () => {
    test('posts to the partial with the submit token and pre-selects the usual fit', async () => {
        const html = await render(FleetRsvpForm, { ...props, form: form() })
        expect(html).toContain('hx-post="/partials/fleet_rsvp_component/"')
        expect(html).toContain('value="submit-token-abcdefghijklmnop"')
        expect(html).toMatch(/<option value="f:2"[^>]*selected/)
        expect(html).toContain('Vex Drake invited you')
        expect(html).toContain('19:00 EVE · Fri 13 Nov')
        expect(html).toContain('Your usual · flown 5 times')
        expect(html).toContain('Can fly 2 fits')
        expect(html).toContain("Your other 12 characters can&#39;t fly a PHOONS fit yet.")
        expect(html).toContain('You might be 10–15 minutes late. Vex Drake will see that.')
    })

    test('the switch sits above the character list', async () => {
        const html = await render(FleetRsvpForm, { ...props, form: form() })
        expect(html.indexOf('How sure are you')).toBeLessThan(html.indexOf('Who&#39;s coming'))
    })

    test('shared accounts come with the warning, ready for Alpine to show', async () => {
        const html = await render(FleetRsvpForm, {
            ...props,
            form: form({ characters: [character({ account: 7 }), character({ character_id: 22, name: 'Sashii', account: 7 })] }),
        })
        expect(html).toContain('Only one character per EVE account can log in at a time.')
        expect(html).toContain('Fix it on the Characters page.')
        expect(html).not.toMatch(/Fix it on the Characters page\.<\/span>\s*<a/)
    })

    test('a fleet with no doctrine asks for no ship', async () => {
        const html = await render(FleetRsvpForm, {
            ...props,
            form: form({ any_ship: true, characters: [character({ fits: [], suggested_key: '', suggested_fleets: 0 })], hidden_count: 0 }),
        })
        expect(html).toContain('No ship yet, ask on comms.')
        expect(html).not.toContain('<select')
        expect(html).toContain('Sign up')
    })

    test('nothing ticked starts with the disabled prompt', async () => {
        const html = await render(FleetRsvpForm, {
            ...props,
            form: form({ characters: [character({ picked: false })] }),
        })
        expect(html).toContain('Pick a character above')
    })
})

describe('FleetRsvpResult', () => {
    test('signed up lists the ships', async () => {
        const html = await render(FleetRsvpResult, {
            form_href: '/fleets/rsvp/page-token/',
            result: {
                fleet,
                answer: 'in',
                confidence: 'high',
                ships: [{ character_id: 11, character_name: 'Bear', ship_name: '[FL33T] Typhoon', ship_id: 644 }],
            },
        })
        expect(html).toContain('You&#39;re signed up')
        expect(html).toContain('Vex Drake can see you&#39;re coming.')
        expect(html).toContain('[FL33T] Typhoon')
        expect(html).toContain('https://images.evetech.net/types/644/icon?size=64')
        expect(html).toContain('https://discord.com/channels/@me')
        expect(html).toContain('href="/fleets/rsvp/page-token/"')
    })

    test('not available says it only skips this fleet', async () => {
        const html = await render(FleetRsvpResult, {
            form_href: '/fleets/rsvp/page-token/',
            result: { fleet, answer: 'out', confidence: '', ships: [] },
        })
        expect(html).toContain('You&#39;re not available for this one')
        expect(html).toContain('This only skips this fleet.')
    })
})

test('the expired screen never names a fleet', async () => {
    const html = await render(FleetRsvpExpired, { sign_in_href: '/redirects/auth_init?redirect_url=x' })
    expect(html).toContain('This link has expired')
    expect(html).toContain('Links from the I&#39;m available button work for 10 minutes.')
    expect(html).toContain('Sign in instead')
    expect(html).not.toContain('Friday Night Fights')
})
