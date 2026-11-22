import { expect, userEvent, waitFor, within } from 'storybook/test'
import ButtonConfirm from '@components/blocks/ButtonConfirm.astro'
import Button from '@components/blocks/Button.astro'
import { BUTTON_COLORS, BUTTON_SIZES, radio_control, select_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Forms/ButtonConfirm',
    component: ButtonConfirm,
    parameters: {
        docs: {
            description: {
                component: [
                    'A two-step button for destructive or irreversible actions. The first click swaps the label button for whatever is in the default slot (usually the real action button, which shakes in); the confirm state expires after 5 seconds.',
                    'Put the real action (a form submit, an `hx-post` button) in the slot and keep the `label` short. Use a plain `Button` plus a dialog when the action needs an explanation, not just a second click.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        label: { control: 'text', description: 'Text of the first-step button.' },
        color: select_control(BUTTON_COLORS, 'Background token of the first-step button.'),
        size: radio_control(BUTTON_SIZES, '`sm` for dense rows, `lg` otherwise.'),
        narrow: { control: 'boolean', description: 'Less inline padding.' },
        centered: { control: 'boolean', description: 'Center the label.' },
        off_disable: { control: 'boolean', description: 'Render the first button enabled from the server (no Alpine gate).' },
    },
    args: {
        label: 'Disband fleet',
        color: 'fleet-red',
        size: 'lg',
        narrow: false,
        centered: true,
        off_disable: false,
        slots: { default: confirm_slot('Yes, disband fleet') },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const first = canvas.getByRole('button', { name: 'Disband fleet' })
        await expect(first).toBeVisible()
        // The confirm slot is hidden until the first click.
        await expect(canvas.queryByRole('button', { name: 'Yes, disband fleet' })).toBeNull()
    },
}

export const ConfirmFlow = {
    name: 'Two-step confirm flow',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByRole('button', { name: 'Disband fleet' }))
        const confirm = await canvas.findByRole('button', { name: 'Yes, disband fleet' })
        await waitFor(() => expect(confirm).toBeVisible())
        await waitFor(() => expect(canvas.queryByRole('button', { name: 'Disband fleet' })).toBeNull())
        await expect(canvasElement.querySelector('.confirm-button')).not.toBeNull()
        await expect(confirm.closest('[x-show="confirm"]')).toHaveClass('animate-shake')
    },
}

export const SmallNarrow = {
    args: { size: 'sm', narrow: true, label: 'Remove', slots: { default: confirm_slot('Confirm remove') } },
    play: async ({ canvasElement }: Ctx) => {
        const first = within(canvasElement).getByRole('button', { name: 'Remove' })
        await expect(first).toHaveAttribute('data-size', 'sm')
        await expect(first).toHaveClass('narrow')
    },
}

export const AllianceBlue = {
    args: { color: 'alliance-blue', label: 'Release SRP claim', slots: { default: confirm_slot('Release it') } },
    play: async ({ canvasElement }: Ctx) => {
        const first = within(canvasElement).getByRole('button', { name: 'Release SRP claim' })
        await expect(first.getAttribute('style')).toContain('var(--alliance-blue)')
    },
}

export const OffDisable = {
    name: 'Enabled without Alpine (off_disable)',
    args: { off_disable: true },
    play: async ({ canvasElement }: Ctx) => {
        const first = within(canvasElement).getByRole('button', { name: 'Disband fleet' })
        await expect(first).toBeEnabled()
        await expect(first).not.toHaveAttribute('x-init')
    },
}

function confirm_slot(label: string) {
    return {
        component: Button,
        props: { color: 'fleet-red' },
        slots: { default: label },
    }
}

export const PassesAttributesThrough = {
    name: 'Extra attributes and classes reach the root',
    args: { class: 'ml-auto', 'data-testid': 'confirm-root' },
    play: async ({ canvasElement }: Ctx) => {
        const root = within(canvasElement).getByTestId('confirm-root')
        await expect(root).toHaveClass('confirm-button')
        await expect(root).toHaveClass('ml-auto')
    },
}
