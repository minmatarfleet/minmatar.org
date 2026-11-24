import { expect, within } from 'storybook/test'
import SettingRow from '@components/blocks/SettingRow.astro'
import Button from '@components/blocks/Button.astro'
import Textarea from '@components/blocks/Textarea.astro'

export default {
    title: 'Components/Data display/SettingRow',
    component: SettingRow,
    parameters: {
        docs: {
            description: {
                component: 'One settings line: title and short description on the left, the control (button, switch or select) in the slot on the right. Stack several inside a ComponentBlock; each row draws a rule above itself. Pass `for` with the control\'s id so clicking the title focuses or toggles it (the title then renders as a `<label>`).',
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'Bold name of the setting.' },
        description: { control: 'text', description: 'Short muted explanation under the title.' },
        for: { control: 'text', description: 'Id of the control; turns the title into a `<label for>`.' },
        wide: { control: 'boolean', description: 'For text fields: the title takes a fixed column and the control fills the rest of the row.' },
    },
    args: {
        title: 'Fleet notifications',
        description: 'Get a Discord DM when a fleet you signed up for forms up.',
        slots: { default: { component: Button, props: { size: 'sm' }, slots: { default: 'Configure' } } },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Fleet notifications')).toBeVisible()
        await expect(canvas.getByText(/Discord DM/)).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Configure' })).toBeVisible()
        // Without `for` the title is a plain div, not a label.
        await expect(canvasElement.querySelector('label')).toBeNull()
    },
}

export const LabelledControl = {
    name: 'Label for a control',
    args: {
        for: 'show-sneak',
        title: 'Show Sneak',
        description: 'The mascot in the desktop overlay.',
        slots: { default: { component: Button, props: { id: 'show-sneak', size: 'sm', color: 'transparent' }, slots: { default: 'Off' } } },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // With `for` the title becomes a <label> pointing at the control, so clicking it activates the control.
        const label = canvasElement.querySelector('label') as HTMLLabelElement
        await expect(label).toHaveAttribute('for', 'show-sneak')
        await expect(label).toHaveTextContent('Show Sneak')
        await expect(canvasElement.querySelector('#show-sneak')).toBeTruthy()
    },
}

export const WithoutDescription = {
    name: 'Without description',
    args: { description: undefined, title: 'Color-blind mode' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('small')).toBeNull()
        await expect(within(canvasElement).getByText('Color-blind mode')).toBeVisible()
    },
}

export const MultipleControls = {
    name: 'Multiple controls',
    args: {
        title: 'Timezone',
        description: 'Used to show fleet times in your local time.',
        slots: {
            default: [
                { component: Button, props: { size: 'sm', color: 'transparent' }, slots: { default: 'Reset' } },
                { component: Button, props: { size: 'sm' }, slots: { default: 'Save' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('button')).toHaveLength(2)
    },
}

export const LongDescription = {
    name: 'Long description wraps',
    args: {
        title: 'SRP payouts',
        description: 'Approved claims are paid out to your main character every Sunday, in one transfer, minus nothing: the alliance covers the contract fee.',
        slots: { default: { component: Button, props: { size: 'sm' }, slots: { default: 'Change' } } },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/Approved claims are paid out/)).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Change' })).toBeVisible()
    },
}

export const Wide = {
    name: 'Wide (text field)',
    args: {
        title: 'Introduction',
        description: undefined,
        for: 'corp-intro',
        wide: true,
        slots: { default: { component: Textarea, props: { id: 'corp-intro', name: 'introduction' }, slots: { default: 'A cult of Minmatar pilots who worship the Rat.' } } },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('.setting-row')).toHaveClass('setting-row--wide')
        await expect(canvas.getByLabelText('Introduction')).toHaveValue('A cult of Minmatar pilots who worship the Rat.')
    },
}
