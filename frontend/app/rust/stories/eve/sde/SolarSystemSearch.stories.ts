import { expect, within, userEvent, waitFor } from 'storybook/test'
import SolarSystemSearch from '@components/blocks/sde/SolarSystemSearch.astro'

type Ctx = { canvasElement: HTMLElement }

const PARTIAL = '/partials/sde_system_search_component'

// Minimal stand-in for the partial: the real rows are the partial's own output.
const mock_results = (url: URL) => {
    const query = url.searchParams.get('q') ?? ''
    if (!/^ama/i.test(query))
        return `<li role="presentation"><p class="empty-state">No systems match “${query}”</p></li>`
    return `<li role="option" data-value="30002537" data-label="Amamake">Amamake</li>`
}

const input = (canvasElement: HTMLElement) => within(canvasElement).getByRole('combobox') as HTMLInputElement
const hx_get = (canvasElement: HTMLElement) => new URL(input(canvasElement).getAttribute('hx-get') ?? '', 'http://rust.local')
const hidden = (canvasElement: HTMLElement, name: string) => canvasElement.querySelector(`input[type="hidden"][name="${name}"]`) as HTMLInputElement

export default {
    title: 'EVE/SDE/SolarSystemSearch',
    component: SolarSystemSearch,
    parameters: {
        docs: {
            description: {
                component: [
                    'Search solar systems by name: staging and home systems, cyno spots, timer locations. A preset over `Combobox`: the field asks `/partials/sde_system_search_component` as the pilot types (300 ms after the last keystroke, from 2 letters), and htmx swaps in `<li role="option" data-value data-label>` rows, a SolarSystemTag in each. Exact names rank first, then prefix matches.',
                    'Filters travel in the request URL: `region_ids`, `security` (`high`, `low`, `null`, `wormhole`, by the displayed value, so 0.45 is high-sec and 0.03 is low-sec) and `wormholes` (off leaves J-space out of `any`). Picking a system fills the hidden input `name` with the system id and dispatches `combobox:select` with `{ name, value, label }`. The older FindSystemButton dialog keeps its own prefix-only list partial.',
                    'In Rust the partial is mocked (`parameters.htmx`) with a one-row stand-in; the typing stories are tagged `browser` because they need htmx.',
                ].join('\n\n'),
            },
        },
        htmx: { [PARTIAL]: mock_results },
    },
    argTypes: {
        name: { control: 'text', description: 'Hidden input name for the picked id.' },
        label: { control: 'text', description: 'Visible label (defaults to "Find a solar system").' },
        placeholder: { control: 'text', description: 'Input placeholder.' },
        region_ids: { control: 'object', description: 'Only these regions (10000030 Heimatar, 10000042 Metropolis...).' },
        security: { control: 'select', options: ['any', 'high', 'low', 'null', 'wormhole'], description: 'Security band, by displayed value.' },
        wormholes: { control: 'boolean', description: 'Include J-space when `security` is `any`.' },
        limit: { control: 'number', description: 'Most results per search (the server caps it at 50).' },
        selected: { control: 'object', description: "`{ system_id: 30002537, system_name: 'Amamake' }` already picked (an edit form)." },
        allow_clear: { control: 'boolean', description: 'Show a Clear button while something is picked.' },
    },
    args: {
        name: 'staging_system_id',
        label: 'Find a solar system',
        placeholder: 'System name',
        region_ids: [], security: 'any', wormholes: true,
        selected: null,
        allow_clear: true,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const search = within(canvasElement).getByRole('combobox', { name: 'Find a solar system' })
        await expect(search).toBe(input(canvasElement))
        await expect(search).toHaveAttribute('autocomplete', 'off')
        await expect(search).toHaveAttribute('hx-get', PARTIAL)
        await expect(search.getAttribute('hx-trigger')).toContain('delay:300ms')
        await expect(search).toHaveAttribute('aria-expanded', 'false')
        await expect(hidden(canvasElement, 'staging_system_id').value).toBe('')
        await expect(canvasElement.querySelector('[role="listbox"]')).not.toBeVisible()
    },
}

export const WarzoneLowSec = {
    name: 'Filtered: Heimatar and Metropolis low-sec',
    args: { region_ids: [10000030, 10000042], security: 'low', label: 'Staging system' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('combobox', { name: 'Staging system' })).toBeVisible()
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
    args: { selected: { system_id: 30002537, system_name: 'Amamake' } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(hidden(canvasElement, 'staging_system_id').value).toBe('30002537')
        await expect(input(canvasElement).value).toBe('Amamake')
        await userEvent.click(canvas.getByRole('button', { name: 'Clear' }))
        await waitFor(() => expect(hidden(canvasElement, 'staging_system_id').value).toBe(''))
        await expect(input(canvasElement).value).toBe('')
    },
}

export const TypeAndPick = {
    name: 'Type, swap results, pick',
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(input(canvasElement), 'ama')
        const option = await canvas.findByRole('option', { name: /Amamake/ }, { timeout: 3000 })
        const requests: { url: string }[] = (window as unknown as { __rust_htmx_requests?: { url: string }[] }).__rust_htmx_requests ?? []
        const last = new URL(requests[requests.length - 1].url, 'http://rust.local')
        await expect(last.pathname).toBe(PARTIAL)
        await expect(last.searchParams.get('q')).toBe('ama')

        await userEvent.click(option)
        await waitFor(() => expect(hidden(canvasElement, 'staging_system_id').value).toBe('30002537'))
        await expect(input(canvasElement).value).toBe('Amamake')
    },
}

export const NoMatches = {
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        await userEvent.type(input(canvasElement), 'zzz')
        await within(canvasElement).findByText(/No systems match/, {}, { timeout: 3000 })
        await expect(within(canvasElement).queryAllByRole('option')).toHaveLength(0)
    },
}
