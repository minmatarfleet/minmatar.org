import { expect, userEvent, waitFor, within } from 'storybook/test'
import SaveBar from '@components/blocks/SaveBar.astro'

type Ctx = { canvasElement: HTMLElement }

// The bar works on the form around it, so each story renders it inside one, as a settings section does.
const in_form = (Story: () => unknown) => `
<form id="story-form" onsubmit="event.preventDefault()">
    <label for="story-tagline">Tagline</label>
    <input id="story-tagline" name="tagline" value="Take the constellation" />
    <span data-save-bar-ignore><label for="story-switch">Undisclosed</label><input id="story-switch" type="checkbox" /></span>
    ${Story()}
</form>`

const dirty = (root: HTMLElement): boolean => (window as any).Alpine.$data(root.querySelector('.save-bar')).dirty

export default {
    title: 'Components/Forms/SaveBar',
    component: SaveBar,
    decorators: [in_form],
    parameters: {
        docs: {
            description: {
                component: [
                    'The unsaved-changes bar of a settings form, as Discord and Shopify do it. Put it last inside the `<form>`: it stays hidden until a field changes, then sticks to the bottom of the screen with Discard (resets the form) and Save (submits it). A successful htmx submit or a reset hides it again.',
                    'One save rule per screen: text fields wait for Save; a `Switch` that posts on `change` applies at once and is left out of the bar by marking it (or a wrapper) `data-save-bar-ignore`.',
                    '`shown` starts it visible, for a form the server re-renders with an error while the edits are still unsaved.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        shown: { control: 'boolean', description: 'Start visible (edits still unsaved after a failed save).' },
        label: { control: 'text', description: 'Text on the left; "Unsaved changes" by default.' },
        save_label: { control: 'text', description: 'Submit button text; "Save" by default.' },
        discard_label: { control: 'text', description: 'Reset button text; "Discard" by default.' },
        save_attributes: { control: 'object', description: 'Attributes for the Save button, e.g. `{ name: \'op\', value: \'save\' }`.' },
        discard_attributes: { control: 'object', description: 'Attributes for the Discard button, e.g. `{ type: \'button\', \'hx-get\': url }` to reload instead of reset.' },
    },
    args: {
        shown: false,
    },
}

export const Default = {
    name: 'Hidden until a field changes',
    play: async ({ canvasElement }: Ctx) => {
        const bar = canvasElement.querySelector('.save-bar') as HTMLElement
        await expect(bar).toHaveAttribute('role', 'region')
        await expect(bar).toHaveAttribute('aria-label', 'Unsaved changes')
        await expect(dirty(canvasElement)).toBe(false)
    },
}

export const Edited = {
    name: 'Typing shows the bar',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(canvas.getByLabelText('Tagline'), ' tonight')
        await waitFor(() => expect(dirty(canvasElement)).toBe(true))
        await expect(canvas.getByRole('button', { name: 'Save' })).toHaveAttribute('type', 'submit')
        await expect(canvas.getByRole('button', { name: 'Discard' })).toHaveAttribute('type', 'reset')
    },
}

export const Discard = {
    name: 'Discard resets the form',
    args: { shown: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const field = canvas.getByLabelText('Tagline') as HTMLInputElement
        await userEvent.clear(field)
        await userEvent.type(field, 'Changed')
        await userEvent.click(canvas.getByRole('button', { name: 'Discard' }))
        await waitFor(() => expect(field.value).toBe('Take the constellation'))
        await waitFor(() => expect(dirty(canvasElement)).toBe(false))
    },
}

export const IgnoredSwitch = {
    name: 'Instant switches leave it hidden',
    play: async ({ canvasElement }: Ctx) => {
        await userEvent.click(within(canvasElement).getByLabelText('Undisclosed'))
        await expect(dirty(canvasElement)).toBe(false)
    },
}

export const Labels = {
    name: 'Custom labels',
    args: { shown: true, label: 'Saving sends the post for approval', save_label: 'Send for approval', discard_label: 'Undo' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Saving sends the post for approval')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Send for approval' })).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Undo' })).toBeVisible()
    },
}

export const ButtonAttributes = {
    name: 'Save posts an op, Discard reloads',
    args: {
        shown: true,
        save_attributes: { name: 'op', value: 'save' },
        discard_attributes: { type: 'button', 'hx-get': '/partials/campaign_settings_component/?part=systems' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const save = canvas.getByRole('button', { name: 'Save' })
        await expect(save).toHaveAttribute('name', 'op')
        await expect(save).toHaveAttribute('value', 'save')
        const discard = canvas.getByRole('button', { name: 'Discard' })
        await expect(discard).toHaveAttribute('type', 'button')
        await expect(discard).toHaveAttribute('hx-get', '/partials/campaign_settings_component/?part=systems')
    },
}
