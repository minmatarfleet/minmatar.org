import { expect, within, userEvent, waitFor } from 'storybook/test'
import TypeSearch from '@components/blocks/sde/TypeSearch.astro'

type Ctx = { canvasElement: HTMLElement }

const PARTIAL = '/partials/sde_type_search_component'

// Minimal stand-in for the partial: the real rows are the partial's own output.
const mock_results = (url: URL) => {
    const query = url.searchParams.get('q') ?? ''
    if (!/^rif/i.test(query))
        return `<li role="presentation"><p class="empty-state">No items match “${query}”</p></li>`
    return `<li role="option" data-value="587" data-label="Rifter">Rifter</li>`
}

const input = (canvasElement: HTMLElement) => within(canvasElement).getByRole('combobox') as HTMLInputElement
const hx_get = (canvasElement: HTMLElement) => new URL(input(canvasElement).getAttribute('hx-get') ?? '', 'http://rust.local')
const hidden = (canvasElement: HTMLElement, name: string) => canvasElement.querySelector(`input[type="hidden"][name="${name}"]`) as HTMLInputElement

export default {
    title: 'EVE/SDE/TypeSearch',
    component: TypeSearch,
    parameters: {
        docs: {
            description: {
                component: [
                    'Search inventory types by name: a preset over `Combobox`. The field asks `/partials/sde_type_search_component` as the pilot types (300 ms after the last keystroke, from 2 letters), and htmx swaps in `<li role="option" data-value data-label>` rows, a TypeRow in each. Filters (`category_ids`, `group_ids`, `published`, `limit`, `slots`) travel in the request URL, and the query helpers escape LIKE wildcards.',
                    'Picking a type fills the hidden input `name` with the type id and dispatches `combobox:select` with `{ name, value, label }`; keyboard, Escape and click-outside behave as in Combobox. Results that link to a page are not a combobox: use TypeResults with `href_template` for those.',
                    'In Rust the partial is mocked (`parameters.htmx`) with a one-row stand-in; the typing stories are tagged `browser` because they need htmx.',
                ].join('\n\n'),
            },
        },
        htmx: { [PARTIAL]: mock_results },
    },
    argTypes: {
        name: { control: 'text', description: 'Hidden input name for the picked id.' },
        label: { control: 'text', description: 'Visible label (defaults to "Find an item").' },
        placeholder: { control: 'text', description: 'Input placeholder.' },
        category_ids: { control: 'object', description: 'Only these categories: 6 ships, 7 modules, 8 charges...' },
        group_ids: { control: 'object', description: 'Only these groups: 25 frigates, 59 gyrostabilizers...' },
        published: { control: 'boolean', description: 'Only published types (off includes NPC and test types).' },
        show_slots: { control: 'boolean', description: 'Slot layout under each ship result.' },
        limit: { control: 'number', description: 'Most results per search (the server caps it at 50).' },
        selected: { control: 'object', description: "`{ type_id: 11999, type_name: 'Vagabond' }` already picked (an edit form)." },
        allow_clear: { control: 'boolean', description: 'Show a Clear button while something is picked.' },
    },
    args: {
        name: 'ship_type_id',
        label: 'Find an item',
        placeholder: 'Ship, module or item name',
        category_ids: [], group_ids: [], published: true, show_slots: false,
        selected: null,
        allow_clear: true,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const search = within(canvasElement).getByRole('combobox', { name: 'Find an item' })
        await expect(search).toBe(input(canvasElement))
        await expect(search).toHaveAttribute('autocomplete', 'off')
        await expect(search).toHaveAttribute('hx-get', PARTIAL)
        await expect(search.getAttribute('hx-trigger')).toContain('delay:300ms')
        await expect(search).toHaveAttribute('aria-expanded', 'false')
        await expect(hidden(canvasElement, 'ship_type_id').value).toBe('')
        await expect(canvasElement.querySelector('[role="listbox"]')).not.toBeVisible()
    },
}

export const ShipsOnly = {
    name: 'Filtered: Minmatar frigates',
    args: { category_ids: [6], group_ids: [25, 324], limit: 10, show_slots: true, label: 'Doctrine hull' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('combobox', { name: 'Doctrine hull' })).toBeVisible()
        const url = hx_get(canvasElement)
        await expect(url.pathname).toBe(PARTIAL)
        await expect(url.searchParams.get('category_ids')).toBe('6')
        await expect(url.searchParams.get('group_ids')).toBe('25,324')
        await expect(url.searchParams.get('limit')).toBe('10')
        await expect(url.searchParams.get('slots')).toBe('1')
        await expect(url.searchParams.has('published')).toBe(false)
    },
}

export const IncludesUnpublished = {
    args: { published: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(hx_get(canvasElement).searchParams.get('published')).toBe('0')
    },
}

export const Preselected = {
    name: 'Already picked (edit form)',
    args: { selected: { type_id: 11999, type_name: 'Vagabond' } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(hidden(canvasElement, 'ship_type_id').value).toBe('11999')
        await expect(input(canvasElement).value).toBe('Vagabond')
        await userEvent.click(canvas.getByRole('button', { name: 'Clear' }))
        await waitFor(() => expect(hidden(canvasElement, 'ship_type_id').value).toBe(''))
        await expect(input(canvasElement).value).toBe('')
    },
}

export const TypeAndPick = {
    name: 'Type, swap results, pick',
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(input(canvasElement), 'rif')
        const option = await canvas.findByRole('option', { name: /Rifter/ }, { timeout: 3000 })
        const requests: { url: string }[] = (window as unknown as { __rust_htmx_requests?: { url: string }[] }).__rust_htmx_requests ?? []
        const last = new URL(requests[requests.length - 1].url, 'http://rust.local')
        await expect(last.pathname).toBe(PARTIAL)
        await expect(last.searchParams.get('q')).toBe('rif')

        await userEvent.click(option)
        await waitFor(() => expect(hidden(canvasElement, 'ship_type_id').value).toBe('587'))
        await expect(input(canvasElement).value).toBe('Rifter')
    },
}

export const NoMatches = {
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        await userEvent.type(input(canvasElement), 'zzz')
        await within(canvasElement).findByText(/No items match/, {}, { timeout: 3000 })
        await expect(within(canvasElement).queryAllByRole('option')).toHaveLength(0)
    },
}
