import { expect, within, userEvent, waitFor } from 'storybook/test'
import TypeSearch from '@components/blocks/sde/TypeSearch.astro'

type Ctx = { canvasElement: HTMLElement }

const PARTIAL = '/partials/sde_type_search_component'

// Minimal stand-in for the partial: the real rows are TypeResults' own stories.
const mock_results = (url: URL) => {
    const query = url.searchParams.get('q') ?? ''
    if (!/^rif/i.test(query))
        return `<p class="empty-state">No items match “${query}”</p>`
    return `<div role="list">
        <div role="listitem" x-data><button type="button" data-type-id="587" data-type-name="Rifter"
            x-on:click="$dispatch('sde-type-select', { type_id: 587, type_name: 'Rifter' })">Rifter</button></div>
    </div>`
}

const input = (canvasElement: HTMLElement) => within(canvasElement).getByRole('searchbox') as HTMLInputElement
const hx_get = (canvasElement: HTMLElement) => new URL(input(canvasElement).getAttribute('hx-get') ?? '', 'http://rust.local')

export default {
    title: 'EVE/SDE/TypeSearch',
    component: TypeSearch,
    parameters: {
        docs: {
            description: {
                component: [
                    'Search inventory types by name. The input asks `/partials/sde_type_search_component` as the pilot types (300 ms after the last keystroke, or on Enter or clearing the field), and htmx swaps the TypeResults it renders into an aria-live region; `hx-sync` drops a stale request when a new one starts. Filters (`category_ids`, `group_ids`, `published`, `limit`) travel in the request URL, and the query helpers escape LIKE wildcards.',
                    'With `name`, results are buttons: picking one fills a hidden input `name` with the type id for the surrounding form, shows the pick and clears the list (local Alpine state only). With `href_template`, results link to a page. Without either, results are read-only.',
                    'In Rust the partial is mocked (`parameters.htmx`) with a one-row stand-in; the typing stories are tagged `browser` because they need htmx.',
                ].join('\n\n'),
            },
        },
        htmx: { [PARTIAL]: mock_results },
    },
    argTypes: {
        id: { control: 'text', description: 'Root id; the input, results and indicator ids derive from it.' },
        name: { control: 'text', description: 'Hidden input name for the picked type id; makes results selectable.' },
        label: { control: 'text', description: 'Visible label (defaults to "Find an item").' },
        placeholder: { control: 'text', description: 'Input placeholder.' },
        category_ids: { control: 'object', description: 'Only these categories: 6 ships, 7 modules, 8 charges...' },
        group_ids: { control: 'object', description: 'Only these groups: 25 frigates, 59 gyrostabilizers...' },
        published: { control: 'boolean', description: 'Only published types (off includes NPC and test types).' },
        limit: { control: 'number', description: 'Most results per search (the server caps it at 50).' },
        href_template: { control: 'text', description: 'Same-site link per result, with `{type_id}` / `{type_name}`.' },
        show_slots: { control: 'boolean', description: 'Slot layout under each ship result.' },
        selected: { control: 'object', description: '`{ type_id, type_name }` already picked (an edit form).' },
    },
    args: {
        id: 'doctrine-hull-search',
        label: 'Find an item',
        placeholder: 'Ship, module or item name',
        category_ids: [],
        group_ids: [],
        published: true,
        show_slots: false,
        selected: null,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const search = canvas.getByLabelText('Find an item')
        await expect(search).toHaveAttribute('type', 'search')
        await expect(search).toHaveAttribute('name', 'q')
        await expect(search).toHaveAttribute('autocomplete', 'off')
        await expect(search).toHaveAttribute('hx-get', PARTIAL)
        await expect(search).toHaveAttribute('hx-trigger', 'input changed delay:300ms, search')
        await expect(search).toHaveAttribute('hx-target', '#doctrine-hull-search-results')
        await expect(search).toHaveAttribute('hx-indicator', '#doctrine-hull-search-indicator')
        await expect(search).toHaveAttribute('hx-sync', 'this:replace')
        await expect(search).toHaveAttribute('aria-controls', 'doctrine-hull-search-results')
        await expect(search).toHaveAccessibleDescription('Type at least 2 letters.')
        const results = canvas.getByRole('region', { name: 'Search results' })
        await expect(results).toHaveAttribute('aria-live', 'polite')
        await expect(canvasElement.querySelector('#doctrine-hull-search-indicator')).toHaveClass('htmx-indicator')
        await expect(canvasElement.querySelector('input[type="hidden"]')).toBeNull()
    },
}

export const ShipsOnly = {
    name: 'Filtered: Minmatar frigates',
    args: { category_ids: [6], group_ids: [25, 324], limit: 10, show_slots: true, label: 'Doctrine hull' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByLabelText('Doctrine hull')).toBeVisible()
        const url = hx_get(canvasElement)
        await expect(url.pathname).toBe(PARTIAL)
        await expect(url.searchParams.get('category_ids')).toBe('6')
        await expect(url.searchParams.get('group_ids')).toBe('25,324')
        await expect(url.searchParams.get('limit')).toBe('10')
        await expect(url.searchParams.get('slots')).toBe('1')
        await expect(url.searchParams.has('published')).toBe(false)
    },
}

export const PickIntoForm = {
    name: 'Picks into a form field (name)',
    args: { name: 'ship_type_id', category_ids: [6] },
    play: async ({ canvasElement }: Ctx) => {
        await expect(hx_get(canvasElement).searchParams.get('selectable')).toBe('1')
        const hidden = canvasElement.querySelector('input[type="hidden"][name="ship_type_id"]') as HTMLInputElement
        await expect(hidden.value).toBe('')
        await expect(within(canvasElement).queryByText('Selected')).not.toBeVisible()
    },
}

export const Preselected = {
    name: 'Already picked (edit form)',
    args: { name: 'ship_type_id', selected: { type_id: 11999, type_name: 'Vagabond' } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const hidden = canvasElement.querySelector('input[type="hidden"][name="ship_type_id"]') as HTMLInputElement
        await expect(hidden.value).toBe('11999')
        await expect(canvas.getByText('Vagabond')).toBeVisible()
        await userEvent.click(canvas.getByRole('button', { name: 'Clear' }))
        await waitFor(() => expect(hidden.value).toBe(''))
        await waitFor(() => expect(canvas.queryByText('Selected')).not.toBeVisible())
    },
}

export const LinksToPages = {
    name: 'Results link to pages (href_template)',
    args: { href_template: '/market/types/{type_id}/', published: false },
    play: async ({ canvasElement }: Ctx) => {
        const url = hx_get(canvasElement)
        await expect(url.searchParams.get('href')).toBe('/market/types/{type_id}/')
        await expect(url.searchParams.get('published')).toBe('0')
        await expect(url.searchParams.has('selectable')).toBe(false)
    },
}

export const TypeAndPick = {
    name: 'Type, swap results, pick',
    tags: ['browser'],
    args: { name: 'ship_type_id', category_ids: [6] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(input(canvasElement), 'rif')
        const rifter = await canvas.findByRole('button', { name: 'Rifter' }, { timeout: 3000 })
        const requests: { url: string }[] = (window as unknown as { __rust_htmx_requests?: { url: string }[] }).__rust_htmx_requests ?? []
        const last = new URL(requests[requests.length - 1].url, 'http://rust.local')
        await expect(last.pathname).toBe(PARTIAL)
        await expect(last.searchParams.get('q')).toBe('rif')
        await expect(last.searchParams.get('category_ids')).toBe('6')
        // Debounced: three keystrokes, one request.
        await expect(requests.filter((request) => request.url.startsWith(PARTIAL))).toHaveLength(1)

        await userEvent.click(rifter)
        const hidden = canvasElement.querySelector('input[type="hidden"][name="ship_type_id"]') as HTMLInputElement
        await waitFor(() => expect(hidden.value).toBe('587'))
        await expect(input(canvasElement).value).toBe('Rifter')
        await expect(canvas.queryByRole('button', { name: 'Rifter' })).toBeNull()
    },
}

export const NoMatch = {
    name: 'Type, no match',
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(input(canvasElement), 'Nidhoggur')
        await expect(await canvas.findByText('No items match “Nidhoggur”', {}, { timeout: 3000 })).toBeVisible()
    },
}
