import { expect, userEvent, waitFor, within } from 'storybook/test'
import SettingsLayout from '@components/blocks/SettingsLayout.astro'

type Ctx = { canvasElement: HTMLElement }

// happy-dom returns the server-rendered value for attributes Alpine rebinds, so state checks read Alpine.
const active_section = (root: HTMLElement): string => (window as any).Alpine.$data(root.querySelector('.settings-layout')).active

const corporation_groups = [
    {
        label: 'Profile',
        items: [
            { id: 'page', label: 'Corporation page', href: '?section=page', url: '/partials/corporation_page_text_component' },
            { id: 'requirements', label: 'Requirements', href: '?section=requirements', url: '/partials/corporation_requirements_settings_component', flag: 'Not set' },
        ],
    },
    {
        label: 'Recruiting',
        items: [
            { id: 'reddit', label: 'Reddit', href: '?section=reddit', url: '/partials/corporation_settings_component' },
            { id: 'forum', label: 'EVE forums', href: '?section=forum', url: '/partials/corporation_forum_post_component', flag: 'Not linked' },
            { id: 'discord', label: 'Discord invite', href: '?section=discord', url: '/partials/corporation_discord_component' },
        ],
    },
]

const section = (title: string) => `<div><h2>${title}</h2><p>The ${title} settings of Rattini Tribe.</p></div>`

const htmx = {
    '/partials/corporation_page_text_component': section('Corporation page'),
    '/partials/corporation_requirements_settings_component': section('Requirements'),
    '/partials/corporation_settings_component': section('Reddit'),
    '/partials/corporation_forum_post_component': section('EVE forums'),
    '/partials/corporation_discord_component': section('Discord invite'),
}

export default {
    title: 'Components/Navigation/SettingsLayout',
    component: SettingsLayout,
    parameters: {
        htmx,
        docs: {
            description: {
                component: [
                    'The settings standard: a grouped list of sections on the left and one section on the right, as GitHub, Discord and Linear do it. A corporation\'s settings, a campaign\'s and the mentor program all use it, so every settings surface looks and saves the same way. Stacks on a phone.',
                    'Each item is a real link (`href`, usually `?section=<id>`), so a section can be linked to and the page works without JavaScript. An item with `url` loads that partial into the content area with htmx and pushes `href` to the address bar; with no default slot, the active item\'s `url` loads on page load.',
                    '`flag` (a short word such as "Not set" or "Draft") and `count` (things waiting) draw the site\'s attention chip. Leave both out when a section is fine: only what needs doing is marked.',
                    'Inside, a section partial starts with its `<h2>`, then `SettingsGroup`s of `SettingRow`s. Switches apply as they flip; a form of text fields ends with a `SaveBar`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        id: { control: 'text', description: 'Base id; the content area is `<id>-content`, the htmx target of the links.' },
        groups: { control: 'object', description: 'Groups of sections: an optional `label` and `items` (`id`, `label`, `href`, optional `url` partial, `flag` word, `count`).' },
        active: { control: 'text', description: 'Id of the section shown; the first item when it names none.' },
        aria_label: { control: 'text', description: 'Accessible name of the section list.' },
    },
    args: {
        id: 'corporation-settings',
        groups: corporation_groups,
        active: 'page',
        aria_label: 'Corporation settings',
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const nav = canvas.getByRole('navigation', { name: 'Corporation settings' })
        await expect(nav).toBeVisible()
        await expect(canvas.getByText('Profile')).toBeVisible()
        await expect(canvas.getByText('Recruiting')).toBeVisible()
        const page = canvas.getByRole('link', { name: 'Corporation page' })
        await expect(page).toHaveAttribute('href', '?section=page')
        await expect(page).toHaveAttribute('aria-current', 'page')
        await expect(page).toHaveClass('is-active')
        await expect(page).toHaveAttribute('hx-target', '#corporation-settings-content')
        await expect(page).toHaveAttribute('hx-push-url', '?section=page')
        await expect(canvasElement.querySelector('#corporation-settings-content')).toBeTruthy()
    },
}

export const Flags = {
    name: 'Flags mark what needs doing',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: /Requirements/ })).toHaveTextContent('Not set')
        await expect(canvas.getByRole('link', { name: /EVE forums/ })).toHaveTextContent('Not linked')
        // A section that is fine carries no mark.
        await expect(canvas.getByRole('link', { name: 'Reddit' }).querySelector('.settings-layout__flag')).toBeNull()
    },
}

export const Counts = {
    name: 'Counts of things waiting',
    args: {
        id: 'mentor-program',
        aria_label: 'Mentor program',
        active: 'mentors',
        groups: [
            { items: [
                { id: 'mentors', label: 'Mentors', href: '?section=mentors', count: 2 },
                { id: 'classes', label: 'Classes', href: '?section=classes' },
                { id: 'reports', label: 'Class reports', href: '?section=reports', count: 0 },
            ] },
        ],
        slots: { default: section('Mentors') },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: /Mentors/ }).querySelector('.settings-layout__count')).toHaveTextContent('2')
        // A zero count is not drawn.
        await expect(canvas.getByRole('link', { name: 'Class reports' }).querySelector('.settings-layout__count')).toBeNull()
        // Without a group label there is no heading above the links.
        await expect(canvasElement.querySelector('.settings-layout__group-label')).toBeNull()
        await expect(canvas.getByRole('heading', { name: 'Mentors' })).toBeVisible()
    },
}

export const UnknownActive = {
    name: 'Unknown active section falls back to the first',
    args: { active: 'billing' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Corporation page' })).toHaveAttribute('aria-current', 'page')
        await expect(active_section(canvasElement)).toBe('page')
    },
}

export const SwitchesSection = {
    name: 'Clicking a section loads it',
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await waitFor(() => expect(canvas.getByRole('heading', { name: 'Corporation page' })).toBeVisible())
        await userEvent.click(canvas.getByRole('link', { name: 'Reddit' }))
        await waitFor(() => expect(canvas.getByRole('heading', { name: 'Reddit' })).toBeVisible())
        await expect(active_section(canvasElement)).toBe('reddit')
        await expect(canvas.getByRole('link', { name: 'Reddit' })).toHaveAttribute('aria-current', 'page')
        await expect(canvas.getByRole('link', { name: 'Corporation page' })).not.toHaveAttribute('aria-current')
    },
}

export const PlainLinks = {
    name: 'Plain links (no partials)',
    args: {
        groups: [{ label: 'Account', items: [
            { id: 'characters', label: 'Characters', href: '/account/characters/' },
            { id: 'display', label: 'Display', href: '/account/display/' },
        ] }],
        active: 'display',
        slots: { default: section('Display') },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const display = canvas.getByRole('link', { name: 'Display' })
        await expect(display).toHaveAttribute('href', '/account/display/')
        await expect(display).not.toHaveAttribute('hx-get')
        await expect(display).toHaveAttribute('aria-current', 'page')
        await expect(canvas.getByRole('heading', { name: 'Display' })).toBeVisible()
    },
}
