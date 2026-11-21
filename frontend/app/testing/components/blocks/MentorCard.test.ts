import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'

import MentorCard from '@components/blocks/mentors/MentorCard.astro'
import type { MentorCard as MentorCardData } from '@dtypes/api.minmatar.org'

const card = (overrides: Partial<MentorCardData> = {}): MentorCardData => ({
    mentor_id: 7,
    person: {
        user_id: 0,
        name: 'Orion',
        character_id: 93672441,
        portrait: '',
        corp: 'FL33T',
        corporation_id: 98726134,
        discord_handle: '',
        discord_id: null,
    },
    availability: { weekday_brackets: ['USTZ'], weekend_brackets: ['USTZ'], days: [0, 1, 2, 3, 4, 5, 6] },
    fit: 'none',
    answer_hours: null,
    answer_text: 'Within a day',
    queue: 0,
    classes_taught: 3,
    pilots_mentored: 2,
    full: false,
    classes: [{
        id: 1,
        slug: 'multi-boxing',
        title: 'Multi-boxing',
        minutes: 60,
        where: 'voice',
        status: 'published',
        cover_image_url: '',
    }],
    is_you: false,
    ...overrides,
})

const render = async (props: Record<string, unknown>) => {
    const container = await AstroContainer.create()
    return container.renderToString(MentorCard, { props })
}

test('a logged-out visitor gets a log-in link instead of the request button', async () => {
    const html = await render({ card: card(), login_href: '/redirects/auth_init?redirect_url=x' })

    expect(html).toContain('Log in to request')
    expect(html).toContain('href="/redirects/auth_init?redirect_url=x"')
    expect(html).not.toContain('x-on:click')
})

test('a logged-in pilot keeps the request button', async () => {
    const html = await render({ card: card() })

    expect(html).toMatch(/>\s*Request\s*</)
    expect(html).not.toContain('Log in to request')
})

test('a full mentor says so, logged in or not', async () => {
    const html = await render({ card: card({ full: true }), login_href: '/login' })

    expect(html).not.toContain('Log in to request')
})
