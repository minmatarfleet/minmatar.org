import { expect, userEvent, waitFor, within } from 'storybook/test'
import Combobox from '@components/blocks/Combobox.astro'

type Ctx = { canvasElement: HTMLElement }

const SEARCH = '/partials/pilot_search_component'

const OPTIONS = `
    <li role="option" data-value="2112625428" data-label="Kel'dar Atram">Kel'dar Atram</li>
    <li role="option" data-value="2113024536" data-label="Mira Tessen">Mira Tessen</li>
    <li role="option" data-value="2114350907" data-label="Orik Vael">Orik Vael</li>`

// Stand-in for a search partial: options for "k", "m" or "o", an empty-state row otherwise.
const mock_search = (url: URL) => {
    const query = url.searchParams.get('q') ?? ''
    if (!/^[kmo]/i.test(query))
        return `<li role="presentation"><p class="empty-state">No pilots match “${query}”</p></li>`
    return OPTIONS
}

const combobox = (canvasElement: HTMLElement) => within(canvasElement).getByRole('combobox') as HTMLInputElement
const listbox = (canvasElement: HTMLElement) => canvasElement.querySelector('[role="listbox"]') as HTMLElement
const hidden = (canvasElement: HTMLElement) => canvasElement.querySelector('input[type="hidden"]') as HTMLInputElement

/** What htmx would do after a swap: fill the listbox and announce it. */
const swap_in = (canvasElement: HTMLElement, html: string) => {
    const list = listbox(canvasElement)
    list.innerHTML = html
    list.dispatchEvent(new CustomEvent('htmx:after-swap', { bubbles: true }))
}

export default {
    title: 'Components/Forms/Combobox',
    component: Combobox,
    parameters: {
        docs: {
            description: {
                component: [
                    'A search-as-you-type picker for a value the browser cannot list up front (pilots, items, systems). The visible field asks the server (`search_url`, `GET ?q=`) 300 ms after the last keystroke, once it holds `min_chars` letters; htmx swaps the `<li role="option" data-value data-label>` items the partial returns into the listbox. The pick lives in a hidden `<input name>`, so the surrounding form submits it.',
                    'Alpine handles only what is local: ArrowUp and ArrowDown move the active option (`aria-activedescendant`), Enter picks it, Escape closes the listbox and stops the key so a surrounding dialog stays open (the dialogs ignore that Escape while `[data-combobox-escape]` is set), and a click outside closes the listbox. Picking dispatches a bubbling `combobox:select` with `{ name, value, label, data }` (`data` holds the option\'s `data-*` attributes, so a partial can carry an icon or detail along); callers listen with `x-on:combobox:select`.',
                    'A partial renders no-result rows as `<li role="presentation">` with an `EmptyState`; only `role="option"` rows can be picked. The SDE searches (`TypeSearch`, `SolarSystemSearch`) are presets over this component. In Rust the partial is mocked (`parameters.htmx`); the typing stories are tagged `browser` because they need htmx.',
                ].join('\n\n'),
            },
        },
        htmx: { [SEARCH]: mock_search },
    },
    argTypes: {
        name: { control: 'text', description: 'Name of the hidden input that holds the picked value.' },
        label: { control: 'text', description: 'Visible label above the field (also the listbox name).' },
        hidden_label: { control: 'boolean', description: 'Keep the label for assistive tech only.' },
        search_url: { control: 'text', description: 'htmx partial: GET `?q=` returns the option `<li>` items.' },
        value: { control: 'text', description: 'Value already picked (an edit form).' },
        value_label: { control: 'text', description: 'Text shown for `value`.' },
        placeholder: { control: 'text', description: 'Field placeholder.' },
        min_chars: { control: 'number', description: 'Letters needed before the server is asked.' },
        debounce_ms: { control: 'number', description: 'Wait after the last keystroke before asking, in ms.' },
        allow_clear: { control: 'boolean', description: 'Show a Clear button while something is picked.' },
        size: { control: 'radio', options: ['lg', 'sm'], description: 'Size of the visible field.' },
        required: { control: 'boolean', description: 'The visible field must hold text before a form submits.' },
        pick_first: { control: 'boolean', description: 'Enter picks the first option when the list is open and nothing is highlighted, and never submits the form.' },
    },
    args: {
        name: 'pilot_id',
        label: 'Pilot',
        hidden_label: false,
        search_url: SEARCH,
        placeholder: 'Pilot name',
        min_chars: 2,
        debounce_ms: 300,
        allow_clear: false,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const field = combobox(canvasElement)
        await expect(within(canvasElement).getByRole('combobox', { name: 'Pilot' })).toBe(field)
        await expect(field).toHaveAttribute('aria-expanded', 'false')
        await expect(field).toHaveAttribute('aria-controls', listbox(canvasElement).id)
        await expect(field).toHaveAttribute('hx-get', SEARCH)
        await expect(field).toHaveAttribute('hx-target', `#${listbox(canvasElement).id}`)
        await expect(field.getAttribute('hx-trigger')).toContain('delay:300ms')
        await expect(field.getAttribute('hx-vals')).toContain('q:')
        await expect(listbox(canvasElement)).toHaveAttribute('role', 'listbox')
        await expect(listbox(canvasElement)).not.toBeVisible()
        await expect(hidden(canvasElement)).toHaveAttribute('name', 'pilot_id')
    },
}

export const KeyboardNavigation = {
    play: async ({ canvasElement }: Ctx) => {
        const field = combobox(canvasElement)
        const canvas = within(canvasElement)
        field.focus()
        swap_in(canvasElement, OPTIONS)
        await waitFor(() => expect(listbox(canvasElement)).toBeVisible())
        await waitFor(() => expect(field).toHaveAttribute('aria-expanded', 'true'))
        const options = canvas.getAllByRole('option')
        await expect(options).toHaveLength(3)

        await userEvent.keyboard('{ArrowDown}')
        await expect(options[0]).toHaveAttribute('aria-selected', 'true')
        await expect(field).toHaveAttribute('aria-activedescendant', options[0].id)
        await userEvent.keyboard('{ArrowDown}{ArrowDown}')
        await expect(options[2]).toHaveAttribute('aria-selected', 'true')
        await userEvent.keyboard('{ArrowDown}')
        await expect(options[0]).toHaveAttribute('aria-selected', 'true')
        await userEvent.keyboard('{ArrowUp}')
        await expect(options[2]).toHaveAttribute('aria-selected', 'true')
        await expect(options[0]).toHaveAttribute('aria-selected', 'false')

        await userEvent.keyboard('{Enter}')
        await expect(hidden(canvasElement).value).toBe('2114350907')
        await expect(field.value).toBe('Orik Vael')
        await expect(field).toHaveAttribute('aria-expanded', 'false')
        await waitFor(() => expect(listbox(canvasElement)).not.toBeVisible())
    },
}

export const SelectDispatchesEvent = {
    name: 'Select dispatches combobox:select',
    play: async ({ canvasElement }: Ctx) => {
        const seen: CustomEvent[] = []
        canvasElement.addEventListener('combobox:select', (event) => seen.push(event as CustomEvent))
        combobox(canvasElement).focus()
        swap_in(canvasElement, OPTIONS)
        await waitFor(() => expect(listbox(canvasElement)).toBeVisible())
        await userEvent.click(within(canvasElement).getByRole('option', { name: 'Mira Tessen' }))
        await expect(seen).toHaveLength(1)
        await expect(seen[0].detail).toEqual({ name: 'pilot_id', value: '2113024536', label: 'Mira Tessen', data: { value: '2113024536', label: 'Mira Tessen' } })
        await expect(seen[0].bubbles).toBe(true)
        await expect(hidden(canvasElement).value).toBe('2113024536')
        await expect(combobox(canvasElement).value).toBe('Mira Tessen')
    },
}

export const PickFirstOnEnter = {
    name: 'pick_first: Enter picks the first option',
    args: { pick_first: true, size: 'sm' },
    play: async ({ canvasElement }: Ctx) => {
        const field = combobox(canvasElement)
        await expect(field).toHaveAttribute('data-size', 'sm')
        field.focus()
        swap_in(canvasElement, OPTIONS)
        await waitFor(() => expect(listbox(canvasElement)).toBeVisible())
        // Nothing highlighted: Enter still picks the first match.
        await userEvent.keyboard('{Enter}')
        await expect(hidden(canvasElement).value).toBe('2112625428')
        await expect(field.value).toBe("Kel'dar Atram")
        // With nothing to pick, Enter still must not submit the surrounding form.
        const keydown = new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true })
        field.dispatchEvent(keydown)
        await expect(keydown.defaultPrevented).toBe(true)
    },
}

export const EnterDoesNothingByDefault = {
    name: 'Enter without a highlighted option picks nothing',
    play: async ({ canvasElement }: Ctx) => {
        const field = combobox(canvasElement)
        field.focus()
        swap_in(canvasElement, OPTIONS)
        await waitFor(() => expect(listbox(canvasElement)).toBeVisible())
        await userEvent.keyboard('{Enter}')
        await expect(hidden(canvasElement).value).toBe('')
    },
}

export const EscapeKeepsDialogOpen = {
    name: 'Escape inside a dialog keeps the dialog open',
    decorators: [(Story: () => string) => `
        <div x-data="{ dialog_open: true }"
            x-on:keyup.escape.window="!$event.target?.closest?.('[data-combobox-escape]') && (dialog_open = false)">
            <div data-testid="dialog" x-show="dialog_open">${Story()}</div>
        </div>`],
    play: async ({ canvasElement }: Ctx) => {
        const dialog = within(canvasElement).getByTestId('dialog')
        const field = combobox(canvasElement)
        field.focus()
        swap_in(canvasElement, OPTIONS)
        await waitFor(() => expect(field).toHaveAttribute('aria-expanded', 'true'))

        await userEvent.keyboard('{Escape}')
        await expect(field).toHaveAttribute('aria-expanded', 'false')
        await waitFor(() => expect(listbox(canvasElement)).not.toBeVisible())
        await expect(dialog).toBeVisible()

        // A second Escape, with the listbox already closed, reaches the dialog.
        await userEvent.keyboard('{Escape}')
        await waitFor(() => expect(dialog).not.toBeVisible())
    },
}

export const ClickOutsideClosesList = {
    // Alpine's .outside ignores elements without layout, so this needs a real browser.
    tags: ['browser'],
    decorators: [(Story: () => string) => `<div><button type="button">Elsewhere</button>${Story()}</div>`],
    play: async ({ canvasElement }: Ctx) => {
        const field = combobox(canvasElement)
        field.focus()
        swap_in(canvasElement, OPTIONS)
        await waitFor(() => expect(listbox(canvasElement)).toBeVisible())
        await userEvent.click(within(canvasElement).getByRole('button', { name: 'Elsewhere' }))
        await waitFor(() => expect(listbox(canvasElement)).not.toBeVisible())
        await expect(hidden(canvasElement).value).toBe('')
    },
}

export const EmptyResults = {
    play: async ({ canvasElement }: Ctx) => {
        const field = combobox(canvasElement)
        field.focus()
        swap_in(canvasElement, '<li role="presentation"><p class="empty-state">No pilots match “zzz”</p></li>')
        await waitFor(() => expect(listbox(canvasElement)).toBeVisible())
        await expect(within(canvasElement).getByText('No pilots match “zzz”')).toBeVisible()
        await expect(within(canvasElement).queryAllByRole('option')).toHaveLength(0)
        // ArrowDown has nothing to land on.
        await userEvent.keyboard('{ArrowDown}')
        await expect(field).not.toHaveAttribute('aria-activedescendant')
    },
}

export const Preselected = {
    name: 'Already picked, with Clear',
    args: { value: '2112625428', value_label: "Kel'dar Atram", allow_clear: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(hidden(canvasElement).value).toBe('2112625428')
        await expect(combobox(canvasElement).value).toBe("Kel'dar Atram")
        await userEvent.click(canvas.getByRole('button', { name: 'Clear' }))
        await waitFor(() => expect(hidden(canvasElement).value).toBe(''))
        await expect(combobox(canvasElement).value).toBe('')
        await waitFor(() => expect(canvasElement.querySelector('.combobox__clear')).not.toBeVisible())
    },
}

export const HiddenLabel = {
    args: { hidden_label: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('combobox', { name: 'Pilot' })).toBe(combobox(canvasElement))
        await expect(canvasElement.querySelector('label')).toHaveClass('visually-hidden')
    },
}

export const TypeSearchAndPick = {
    name: 'Type, swap results, pick',
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(combobox(canvasElement), 'ke')
        const option = await canvas.findByRole('option', { name: /Kel'dar/ }, { timeout: 3000 })
        const requests: { url: string }[] = (window as unknown as { __rust_htmx_requests?: { url: string }[] }).__rust_htmx_requests ?? []
        const last = new URL(requests[requests.length - 1].url, 'http://rust.local')
        await expect(last.pathname).toBe(SEARCH)
        await expect(last.searchParams.get('q')).toBe('ke')
        await expect(combobox(canvasElement)).toHaveAttribute('aria-expanded', 'true')

        await userEvent.click(option)
        await waitFor(() => expect(hidden(canvasElement).value).toBe('2112625428'))
        await expect(combobox(canvasElement).value).toBe("Kel'dar Atram")
    },
}

export const TooShortAsksNothing = {
    name: 'Under min_chars asks nothing',
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const before = ((window as unknown as { __rust_htmx_requests?: unknown[] }).__rust_htmx_requests ?? []).length
        await userEvent.type(combobox(canvasElement), 'k')
        await new Promise((resolve) => setTimeout(resolve, 500))
        const after = ((window as unknown as { __rust_htmx_requests?: unknown[] }).__rust_htmx_requests ?? []).length
        await expect(after).toBe(before)
        await waitFor(() => expect(listbox(canvasElement)).not.toBeVisible())
    },
}
