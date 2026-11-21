import { expect, userEvent, within, waitFor } from 'storybook/test'
import SectionTabPanel from '@components/blocks/SectionTabPanel.astro'
import Button from '@components/blocks/Button.astro'

// A panel reads the parent SectionTabs' `tab` state. The Storybook renderer renders one component per story,
// so these stories give the panel its own tiny scope through `x-data` (passed through to the section) instead
// of nesting it in SectionTabs; `SectionTabs` stories cover the two together.
const scope = (tab: string) => `{ tab: '${tab}' }`

export default {
    title: 'Components/Navigation/SectionTabPanel',
    component: SectionTabPanel,
    parameters: {
        docs: {
            description: {
                component: [
                    'The content region of one `SectionTabs` tab. It renders a `role="tabpanel"` section named by its tab (`aria-labelledby`), hidden by Alpine unless the parent\'s active `tab` is its `id`.',
                    '`id` must be a tab id and `id_prefix` must equal the tabs\' `id_prefix`. Mark the tab that opens first with `is_default` so the server-rendered HTML shows it before Alpine starts (the others render `hidden`).',
                    'On pages it is always a child of `SectionTabs`. These stories stand in for the parent with a local `x-data="{ tab }"` on the panel, so the visibility rule can be exercised alone.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        id: { control: 'text', description: 'The tab this panel belongs to.' },
        id_prefix: { control: 'text', description: 'Must match the `id_prefix` of the SectionTabs.' },
        is_default: { control: 'boolean', description: 'Server-render this panel visible (the initially active tab).' },
        'x-data': { control: 'text', description: 'Story only: stands in for the parent SectionTabs\' `tab` state.' },
    },
    args: {
        id: 'members',
        id_prefix: 'corp',
        is_default: true,
        'x-data': scope('members'),
        slots: { default: '<p>Kel&#8217;dar Atram, CEO. 48 pilots, 31 active this month.</p>' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const panel = within(canvasElement).getByRole('tabpanel')
        await waitFor(() => expect(panel).toBeVisible())
        await expect(panel).toHaveAttribute('id', 'corp-panel-members')
        await expect(panel).toHaveAttribute('aria-labelledby', 'corp-tab-members')
        await expect(panel).toHaveClass('section-tabs-panel')
        await waitFor(() => expect(within(panel).getByText(/48 pilots/)).toBeVisible())
    },
}

export const HiddenWhenAnotherTabIsActive = {
    name: 'Hidden when another tab is active',
    args: { id: 'activity', is_default: false, 'x-data': scope('members'), slots: { default: '<p>Rifter Fleet Friday: 24 pilots, 61 kills.</p>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const panel = canvasElement.querySelector('#corp-panel-activity') as HTMLElement
        await expect(panel).toHaveAttribute('role', 'tabpanel')
        await expect(panel).toHaveAttribute('hidden')
        await waitFor(() => expect(within(canvasElement).getByText(/61 kills/)).not.toBeVisible())
    },
}

export const ShownWhenItsTabBecomesActive = {
    name: 'Shown when its tab becomes active',
    args: {
        id: 'activity',
        is_default: false,
        'x-data': scope('members'),
        slots: {
            default: [
                '<p>Rifter Fleet Friday: 24 pilots, 61 kills.</p>',
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const panel = canvasElement.querySelector('#corp-panel-activity') as HTMLElement
        await waitFor(() => expect(within(canvasElement).getByText(/61 kills/)).not.toBeVisible())
        // Flip the parent's state the way SectionTabs does when its tab is clicked.
        const alpine = (window as any).Alpine
        alpine.$data(panel).tab = 'activity'
        await alpine.nextTick()
        await waitFor(() => expect(within(canvasElement).getByText(/61 kills/)).toBeVisible())
        await expect(panel).not.toHaveAttribute('hidden')
    },
}

export const RichContent = {
    args: {
        class: 'corp-members-panel',
        'data-corp': 'a-rat',
        slots: {
            default: `<table><caption>Roster</caption><thead><tr><th>Pilot</th><th>Role</th></tr></thead>
                <tbody><tr><td>Kel&#8217;dar Atram</td><td>CEO</td></tr><tr><td>Sneak</td><td>Scout</td></tr></tbody></table>`,
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const panel = canvasElement.querySelector('#corp-panel-members') as HTMLElement
        // Extra attributes and classes pass through to the section.
        await expect(panel).toHaveClass('corp-members-panel')
        await expect(panel).toHaveAttribute('data-corp', 'a-rat')
        await waitFor(() => expect(within(panel).getByRole('table', { name: 'Roster' })).toBeVisible())
        await waitFor(() => expect(within(panel).getByRole('row', { name: /CEO/ })).toBeVisible())
    },
}

export const WithInteractiveContent = {
    args: {
        slots: {
            default: [
                '<p>Doctrine: Fleet Rifter (Armor)</p>',
                { component: Button, props: { size: 'sm', href: '/doctrines/' }, slots: { default: 'Open doctrines' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: 'Open doctrines' })
        await expect(link).toHaveAttribute('href', '/doctrines/')
        await userEvent.hover(link)
        await waitFor(() => expect(link).toBeVisible())
    },
}
