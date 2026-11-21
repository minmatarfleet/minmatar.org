import { expect, within, userEvent, waitFor } from 'storybook/test'
import SolarSystemSearch from '@components/blocks/sde/SolarSystemSearch.astro'

type Ctx = { canvasElement: HTMLElement }

const PARTIAL = '/partials/sde_system_search_component'

// Minimal stand-in for the partial: the real rows are SolarSystemResults' own stories.
const mock_results = (url: URL) => {
    const query = url.searchParams.get('q') ?? ''
    if (!/^ama/i.test(query))
        return `<p class="empty-state">No systems match “${query}”</p>`
    return `<div role="list">
        <div role="listitem" x-data><button type="button" data-system-id="30002537" data-system-name="Amamake"
            x-on:click="$dispatch('sde-system-select', { system_id: 30002537, system_name: 'Amamake' })">Amamake 0.4</button></div>
    </div>`
}

const input = (canvasElement: HTMLElement) => within(canvasElement).getByRole('searchbox') as HTMLInputElement
const hx_get = (canvasElement: HTMLElement) => new URL(input(canvasElement).getAttribute('hx-get') ?? '', 'http://rust.local')

export default {
    title: 'EVE/SDE/SolarSystemSearch',
    component: SolarSystemSearch,
    parameters: {
        docs: {
            description: {
                component: [
                    'Search solar systems by name: staging and home systems, cyno spots, timer locations. The input asks `/partials/sde_system_search_component` as the pilot types (300 ms after the last keystroke, or on Enter or clearing the field), and htmx swaps the SolarSystemResults it renders into an aria-live region. Exact names rank first, then prefix matches.',
                    'Filters travel in the request URL: `region_ids`, `security` (`high`, `low`, `null`, `wormhole`, by the displayed value, so 0.45 is high-sec and 0.03 is low-sec) and `wormholes` (off leaves J-space out of `any`). With `name`, picking a result fills a hidden input with the system id (local Alpine state); with `href_template`, results link to a page.',
                    'In Rust the partial is mocked (`parameters.htmx`); the typing stories are tagged `browser` because they need htmx. The older FindSystemButton dialog keeps its own prefix-only list partial.',
                ].join('\n\n'),
            },
        },
        htmx: { [PARTIAL]: mock_results },
    },
    argTypes: {
        id: { control: 'text', description: 'Root id; the input, results and indicator ids derive from it.' },
        name: { control: 'text', description: 'Hidden input name for the picked system id; makes results selectable.' },
        label: { control: 'text', description: 'Visible label (defaults to "Find a solar system").' },
        placeholder: { control: 'text', description: 'Input placeholder.' },
        region_ids: { control: 'object', description: 'Only these regions (10000030 Heimatar, 10000042 Metropolis...).' },
        security: { control: 'select', options: ['any', 'high', 'low', 'null', 'wormhole'], description: 'Security band, by displayed value.' },
        wormholes: { control: 'boolean', description: 'Include J-space when `security` is `any`.' },
        limit: { control: 'number', description: 'Most results per search (the server caps it at 50).' },
        href_template: { control: 'text', description: 'Same-site link per result, with `{system_id}` / `{system_name}`.' },
        selected: { control: 'object', description: '`{ system_id, system_name }` already picked (an edit form).' },
    },
    args: {
        id: 'staging-system-search',
        label: 'Find a solar system',
        placeholder: 'System name',
        region_ids: [],
        security: 'any',
        wormholes: true,
        selected: null,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const search = canvas.getByLabelText('Find a solar system')
        await expect(search).toHaveAttribute('type', 'search')
        await expect(search).toHaveAttribute('name', 'q')
        await expect(search).toHaveAttribute('hx-get', PARTIAL)
        await expect(search).toHaveAttribute('hx-trigger', 'input changed delay:300ms, search')
        await expect(search).toHaveAttribute('hx-target', '#staging-system-search-results')
        await expect(search).toHaveAttribute('hx-indicator', '#staging-system-search-indicator')
        await expect(search).toHaveAttribute('hx-sync', 'this:replace')
        await expect(canvas.getByRole('region', { name: 'Search results' })).toHaveAttribute('aria-live', 'polite')
    },
}

export const WarzoneLowSec = {
    name: 'Filtered: Heimatar and Metropolis low-sec',
    args: { region_ids: [10000030, 10000042], security: 'low', label: 'Staging system' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByLabelText('Staging system')).toBeVisible()
        const url = hx_get(canvasElement)
        await expect(url.searchParams.get('region_ids')).toBe('10000030,10000042')
        await expect(url.searchParams.get('security')).toBe('low')
        await expect(url.searchParams.has('wormholes')).toBe(false)
    },
}

export const KSpaceOnly = {
    name: 'K-space only',
    args: { wormholes: false, limit: 10 },
    play: async ({ canvasElement }: Ctx) => {
        const url = hx_get(canvasElement)
        await expect(url.searchParams.get('wormholes')).toBe('0')
        await expect(url.searchParams.get('limit')).toBe('10')
        await expect(url.searchParams.has('security')).toBe(false)
    },
}

export const Preselected = {
    name: 'Already picked (edit form)',
    args: { name: 'staging_system_id', selected: { system_id: 30002537, system_name: 'Amamake' } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(hx_get(canvasElement).searchParams.get('selectable')).toBe('1')
        const hidden = canvasElement.querySelector('input[type="hidden"][name="staging_system_id"]') as HTMLInputElement
        await expect(hidden.value).toBe('30002537')
        await expect(canvas.getByText('Amamake')).toBeVisible()
        await userEvent.click(canvas.getByRole('button', { name: 'Clear' }))
        await waitFor(() => expect(hidden.value).toBe(''))
        await waitFor(() => expect(canvas.queryByText('Selected')).not.toBeVisible())
    },
}

export const LinksToMoonPages = {
    name: 'Results link to pages (href_template)',
    args: { href_template: '/intel/moons/{system_name}' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(hx_get(canvasElement).searchParams.get('href')).toBe('/intel/moons/{system_name}')
    },
}

export const TypeAndPick = {
    name: 'Type, swap results, pick',
    tags: ['browser'],
    args: { name: 'staging_system_id', security: 'low' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(input(canvasElement), 'ama')
        const amamake = await canvas.findByRole('button', { name: /Amamake/ }, { timeout: 3000 })
        const requests: { url: string }[] = (window as unknown as { __rust_htmx_requests?: { url: string }[] }).__rust_htmx_requests ?? []
        const last = new URL(requests[requests.length - 1].url, 'http://rust.local')
        await expect(last.pathname).toBe(PARTIAL)
        await expect(last.searchParams.get('q')).toBe('ama')
        await expect(last.searchParams.get('security')).toBe('low')

        await userEvent.click(amamake)
        const hidden = canvasElement.querySelector('input[type="hidden"][name="staging_system_id"]') as HTMLInputElement
        await waitFor(() => expect(hidden.value).toBe('30002537'))
        await expect(input(canvasElement).value).toBe('Amamake')
    },
}
