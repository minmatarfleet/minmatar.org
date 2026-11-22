import { expect, userEvent, waitFor, within } from 'storybook/test'
import SectionTabs from '@components/blocks/SectionTabs.astro'
import SectionTabPanel from '@components/blocks/SectionTabPanel.astro'
import { radio_control } from '../../_controls'

// Selecting a tab writes `#<tab>` to the URL; clear it so the next story starts on its default tab.
const reset_hash = () => {
    try { history.replaceState(null, '', location.pathname + location.search) } catch { /* sandboxed frame */ }
}

// The active tab lives in the component's Alpine state. (happy-dom, the vitest DOM, keeps returning stale
// `aria-selected`/`class` values for elements Alpine rebinds, so tab-state assertions read Alpine and the
// panels' visibility; `AriaSelectedFollowsTab` checks the attributes in a real browser.)
const active_tab = (root: HTMLElement): string => (window as any).Alpine.$data(root.querySelector('.section-tabs')).tab
const attr = (el: Element, name: string) => Array.from(el.attributes).find((a) => a.name === name)?.value

const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'fleets', label: 'Fleets', meta: '12' },
    { id: 'srp', label: 'SRP', meta: '3', flag: 'attention' },
]

const panels = (id_prefix: string) => [
    { component: SectionTabPanel, props: { id: 'overview', id_prefix, is_default: true }, slots: { default: '<p>Rattini Tribe at a glance: 48 pilots, 6 fleets this week.</p>' } },
    { component: SectionTabPanel, props: { id: 'fleets', id_prefix }, slots: { default: '<p>Upcoming: Rifter Fleet Friday 19:00 EVE.</p>' } },
    { component: SectionTabPanel, props: { id: 'srp', id_prefix }, slots: { default: '<p>3 SRP requests waiting for review.</p>' } },
]

export default {
    title: 'Components/Navigation/SectionTabs',
    component: SectionTabs,
    parameters: {
        docs: {
            description: {
                component: [
                    'Page-section tabs: a `tablist` of buttons plus `SectionTabPanel` children (one per tab id). Alpine keeps the active tab, with arrow-key, Home and End navigation and roving `tabindex`; the panel is shown with `hidden`, so every panel is in the DOM (use `LazyPartial` inside a panel to defer heavy content).',
                    'The active tab is mirrored to the URL hash (`history.replaceState`) and read back on load and on `hashchange`; `hash_aliases` maps hash prefixes to a tab, so `#campaign-system-42` opens Systems. The hash sync is browser-only behaviour; stories assert the tab state instead.',
                    '**Link mode:** give any tab an `href` and the component renders a `<nav aria-label>` of links to other pages (no panels, no Alpine). The active link gets `aria-current="page"`: the tab named by `active_tab`, else the tab whose `href` is the longest path prefix of the current page (`/fleets` is current on `/fleets/94/`). `variant="compact"` is the small in-card toggle and works in both modes.',
                    '`sync_hash={false}` keeps the active tab out of the URL: for tabs in a dialog or a card, where a `#tab` in the address bar would be wrong (it neither reads nor writes the hash).',
                    'Always pass the same `id_prefix` to the tabs and each panel: the tab/panel `id`s, `aria-controls` and `aria-labelledby` are derived from it. `variant="pills"` is for sub-tabs inside a panel.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        tabs: { control: 'object', description: 'The tabs: `id`, `label`, optional `meta` (count), `flag` (`attention` orange or `live` red dot) and `icon: \'cog\'` for an icon-only tab.' },
        aria_label: { control: 'text', description: 'Accessible name of the tablist.' },
        id_prefix: { control: 'text', description: 'Prefix for the tab/panel ids; must match the panels\' `id_prefix`.' },
        hash_aliases: { control: 'object', description: 'Hash prefixes that open a tab, e.g. `{ \'campaign-system-\': \'systems\' }`.' },
        default_tab: { control: 'text', description: 'The tab shown when the URL names none; the first tab otherwise.' },
        variant: radio_control(['tabs', 'pills', 'compact'] as const, '`pills` for sub-tabs inside a tab panel; `compact` for small toggles inside a card.'),
        sync_hash: { control: 'boolean', description: 'Hash mode: mirror the active tab to the URL hash and read it on load (default on). Turn off for tabs inside a dialog or card.' },
        active_tab: { control: 'text', description: 'Link mode only: the id of the active tab. Otherwise the tab whose `href` is the longest prefix of the page path.' },
    },
    args: {
        tabs,
        aria_label: 'Tribe sections',
        id_prefix: 'tribe',
        hash_aliases: {},
        variant: 'tabs',
        slots: { default: panels('tribe') },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        try {
            const canvas = within(canvasElement)
            await waitFor(() => expect(canvas.getByRole('tablist', { name: 'Tribe sections' })).toBeVisible())
            const overview = canvas.getByRole('tab', { name: 'Overview' })
            const fleets = canvas.getByRole('tab', { name: /Fleets/ })
            await expect(attr(overview, 'aria-selected')).toBe('true')
            await expect(attr(overview, 'class')).toContain('is-active')
            await expect(attr(fleets, 'aria-selected')).toBe('false')
            await expect(attr(fleets, 'tabindex')).toBe('-1')
            await waitFor(() => expect(canvas.getByRole('tabpanel', { name: 'Overview' })).toBeVisible())

            await userEvent.click(fleets)
            await waitFor(() => expect(active_tab(canvasElement)).toBe('fleets'))
            await waitFor(() => expect(canvas.getByText(/Rifter Fleet Friday/)).toBeVisible())
            await waitFor(() => expect(canvas.getByText(/48 pilots/)).not.toBeVisible())
        } finally {
            reset_hash()
        }
    },
}

export const ThreeTabs = {
    name: 'Click through three tabs',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        try {
            const canvas = within(canvasElement)
            for (const [name, id, text] of [
                [/SRP/, 'srp', /3 SRP requests/],
                [/Fleets/, 'fleets', /Rifter Fleet Friday/],
                [/Overview/, 'overview', /48 pilots/],
            ] as const) {
                await userEvent.click(canvas.getByRole('tab', { name }))
                await waitFor(() => expect(active_tab(canvasElement)).toBe(id))
                await waitFor(() => expect(canvas.getByText(text)).toBeVisible())
                // Exactly one panel is shown at a time.
                await expect(canvas.getAllByRole('tabpanel')).toHaveLength(1)
            }
        } finally {
            reset_hash()
        }
    },
}

export const KeyboardNavigation = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        try {
            const canvas = within(canvasElement)
            canvas.getByRole('tab', { name: 'Overview' }).focus()
            await userEvent.keyboard('{ArrowRight}')
            await waitFor(() => expect(active_tab(canvasElement)).toBe('fleets'))
            await waitFor(() => expect(canvas.getByRole('tab', { name: /Fleets/ })).toHaveFocus())
            await userEvent.keyboard('{End}')
            await waitFor(() => expect(active_tab(canvasElement)).toBe('srp'))
            // Wraps around at the end.
            await userEvent.keyboard('{ArrowRight}')
            await waitFor(() => expect(active_tab(canvasElement)).toBe('overview'))
            await userEvent.keyboard('{ArrowLeft}')
            await waitFor(() => expect(active_tab(canvasElement)).toBe('srp'))
            await userEvent.keyboard('{Home}')
            await waitFor(() => expect(active_tab(canvasElement)).toBe('overview'))
        } finally {
            reset_hash()
        }
    },
}

export const AriaSelectedFollowsTab = {
    name: 'aria-selected and roving tabindex follow the tab',
    // happy-dom reports stale attributes for Alpine-rebound elements; check them in a real browser.
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        try {
            const canvas = within(canvasElement)
            const fleets = canvas.getByRole('tab', { name: /Fleets/ })
            await userEvent.click(fleets)
            await waitFor(() => expect(fleets).toHaveAttribute('aria-selected', 'true'))
            await expect(fleets).toHaveAttribute('tabindex', '0')
            await expect(fleets).toHaveClass('is-active')
            await expect(canvas.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'false')
            await expect(canvas.getByRole('tab', { name: 'Overview' })).toHaveAttribute('tabindex', '-1')
            await expect(canvas.getAllByRole('tab', { selected: true })).toHaveLength(1)
        } finally {
            reset_hash()
        }
    },
}

export const MetaAndFlags = {
    name: 'Counts, flags and icon tab',
    args: {
        tabs: [
            ...tabs,
            { id: 'live', label: 'Live', meta: '1', flag: 'live' },
            { id: 'settings', label: 'Settings', icon: 'cog' },
        ],
        slots: {
            default: [
                ...panels('tribe'),
                { component: SectionTabPanel, props: { id: 'live', id_prefix: 'tribe' }, slots: { default: '<p>Strategic fleet forming now.</p>' } },
                { component: SectionTabPanel, props: { id: 'settings', id_prefix: 'tribe' }, slots: { default: '<p>Tribe settings.</p>' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        try {
            const canvas = within(canvasElement)
            await expect(canvasElement.querySelector('.section-tab__meta--attention')).toHaveTextContent('3')
            await expect(canvasElement.querySelector('.section-tab__meta--live')).toHaveTextContent('1')
            // The icon-only tab gets its name from `label` and a tooltip title.
            const cog = canvas.getByRole('tab', { name: 'Settings' })
            await expect(cog).toHaveClass('section-tab--icon')
            await expect(cog).toHaveAttribute('title', 'Settings')
            await userEvent.click(cog)
            await waitFor(() => expect(canvas.getByText('Tribe settings.')).toBeVisible())
        } finally {
            reset_hash()
        }
    },
}

export const DefaultTab = {
    name: 'Non-first default tab',
    args: { default_tab: 'srp', slots: { default: [
        { component: SectionTabPanel, props: { id: 'overview', id_prefix: 'tribe' }, slots: { default: '<p>Rattini Tribe at a glance: 48 pilots, 6 fleets this week.</p>' } },
        { component: SectionTabPanel, props: { id: 'fleets', id_prefix: 'tribe' }, slots: { default: '<p>Upcoming: Rifter Fleet Friday 19:00 EVE.</p>' } },
        { component: SectionTabPanel, props: { id: 'srp', id_prefix: 'tribe', is_default: true }, slots: { default: '<p>3 SRP requests waiting for review.</p>' } },
    ] } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(attr(canvas.getByRole('tab', { name: /SRP/ }), 'aria-selected')).toBe('true')
        await waitFor(() => expect(canvas.getByRole('tabpanel', { name: /SRP/ })).toBeVisible())
    },
}

export const Pills = {
    args: { variant: 'pills', aria_label: 'Fleet history range' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.section-tabs--pills')).not.toBeNull()
        await waitFor(() => expect(within(canvasElement).getByRole('tablist', { name: 'Fleet history range' })).toBeVisible())
    },
}

export const IdsAreWired = {
    name: 'Tab and panel ids are wired',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const tab = canvas.getByRole('tab', { name: /Fleets/ })
        await expect(tab).toHaveAttribute('id', 'tribe-tab-fleets')
        await expect(tab).toHaveAttribute('aria-controls', 'tribe-panel-fleets')
        const panel = canvasElement.querySelector('#tribe-panel-fleets') as HTMLElement
        await expect(panel).toHaveAttribute('role', 'tabpanel')
        await expect(panel).toHaveAttribute('aria-labelledby', 'tribe-tab-fleets')
        await expect(panel).toHaveAttribute('hidden')
    },
}

export const Compact = {
    name: 'Compact (in-card toggle)',
    args: { variant: 'compact', aria_label: 'Chart range' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        try {
            const canvas = within(canvasElement)
            await expect(canvasElement.querySelector('.section-tabs--compact')).not.toBeNull()
            await expect(canvasElement.querySelector('.section-tabs--pills')).toBeNull()
            await waitFor(() => expect(canvas.getByRole('tablist', { name: 'Chart range' })).toBeVisible())
            // Same hash/panel behaviour as the default variant.
            await userEvent.click(canvas.getByRole('tab', { name: /Fleets/ }))
            await waitFor(() => expect(active_tab(canvasElement)).toBe('fleets'))
            await waitFor(() => expect(canvas.getByText(/Rifter Fleet Friday/)).toBeVisible())
        } finally {
            reset_hash()
        }
    },
}

export const NoHashSync = {
    name: 'sync_hash off: the URL stays clean',
    args: { sync_hash: false, variant: 'compact', aria_label: 'Dialog sections' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        reset_hash()
        const canvas = within(canvasElement)
        await waitFor(() => expect(canvas.getByRole('tablist', { name: 'Dialog sections' })).toBeVisible())
        await userEvent.click(canvas.getByRole('tab', { name: /Fleets/ }))
        await waitFor(() => expect(active_tab(canvasElement)).toBe('fleets'))
        await waitFor(() => expect(canvas.getByText(/Rifter Fleet Friday/)).toBeVisible())
        await expect(location.hash).toBe('')
    },
}

const link_tabs = [
    { id: 'home', label: 'Overview', href: '/' },
    { id: 'fleets', label: 'Fleets', href: '/not-this-page/fleets', meta: '12' },
    { id: 'srp', label: 'SRP', href: '/not-this-page/srp' },
]

export const LinkModeByPath = {
    name: 'Link mode: active by path prefix',
    args: { tabs: link_tabs, aria_label: 'Tribe pages', slots: {} },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const nav = canvas.getByRole('navigation', { name: 'Tribe pages' })
        await expect(canvas.queryByRole('tablist')).toBeNull()
        await expect(canvas.queryAllByRole('tabpanel')).toHaveLength(0)
        const links = within(nav).getAllByRole('link')
        await expect(links).toHaveLength(3)
        await expect(canvas.getByRole('link', { name: /Fleets/ })).toHaveAttribute('href', '/not-this-page/fleets')
        // `/` is a prefix of every page path; the other hrefs are not.
        await expect(canvas.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page')
        await expect(canvas.getByRole('link', { name: 'Overview' })).toHaveClass('is-active')
        await expect(canvas.getByRole('link', { name: /Fleets/ })).not.toHaveAttribute('aria-current')
        await expect(canvasElement.querySelectorAll('[aria-current="page"]')).toHaveLength(1)
    },
}

export const LinkModeActiveTab = {
    name: 'Link mode: active_tab wins',
    args: { tabs: link_tabs, aria_label: 'Tribe pages', active_tab: 'srp', slots: {} },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'SRP' })).toHaveAttribute('aria-current', 'page')
        await expect(canvas.getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current')
        await expect(canvasElement.querySelectorAll('[aria-current="page"]')).toHaveLength(1)
        await expect(canvas.getByRole('link', { name: /Fleets/ }).querySelector('.section-tab__meta')).toHaveTextContent('12')
    },
}

export const LinkModeCompact = {
    name: 'Link mode: compact',
    args: { tabs: link_tabs, aria_label: 'Tribe pages', variant: 'compact', active_tab: 'fleets', slots: {} },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const nav = within(canvasElement).getByRole('navigation', { name: 'Tribe pages' })
        await expect(nav).toHaveClass('section-tabs--compact', 'section-tabs--links')
        await expect(within(nav).getByRole('link', { name: /Fleets/ })).toHaveAttribute('aria-current', 'page')
    },
}
