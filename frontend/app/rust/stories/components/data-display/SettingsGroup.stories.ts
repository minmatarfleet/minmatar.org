import { expect, within } from 'storybook/test'
import SettingsGroup from '@components/blocks/SettingsGroup.astro'
import SettingRow from '@components/blocks/SettingRow.astro'
import Switch from '@components/blocks/Switch.astro'
import Button from '@components/blocks/Button.astro'
import Input from '@components/blocks/Input.astro'
import { radio_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const rows = [
    { component: SettingRow, props: { title: 'Name', for: 'campaign-name', wide: true }, slots: { default: { component: Input, props: { id: 'campaign-name', name: 'name', value: 'Hed Constellation' } } } },
    { component: SettingRow, props: { title: 'Undisclosed', for: 'campaign-undisclosed' }, slots: { default: { component: Switch, props: { id: 'campaign-undisclosed', name: 'undisclosed' } } } },
]

export default {
    title: 'Components/Data display/SettingsGroup',
    component: SettingsGroup,
    parameters: {
        docs: {
            description: {
                component: [
                    'A titled panel of `SettingRow`s inside a settings section (`SettingsLayout`). The title is a small uppercase label above a bordered panel; the rows draw the rules between themselves, and the panel border stands in for the first one.',
                    '`tone="danger"` is the red-bordered panel at the bottom of a section, for actions that can\'t be undone (archive, disconnect). Keep it to one per section and last.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'Small uppercase label above the panel. Leave out for the first group under the section heading.' },
        tone: radio_control(['default', 'danger'] as const, '`danger` draws the red border for actions that can\'t be undone.'),
    },
    args: {
        title: 'Visibility',
        tone: 'default',
        slots: { default: rows },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Visibility', level: 3 })).toBeVisible()
        await expect(canvas.getByLabelText('Name')).toHaveValue('Hed Constellation')
        await expect(canvasElement.querySelectorAll('.setting-row')).toHaveLength(2)
        await expect(canvasElement.querySelector('.settings-group--danger')).toBeNull()
    },
}

export const Untitled = {
    name: 'Without a title',
    args: { title: undefined },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('h3')).toBeNull()
        await expect(within(canvasElement).getByLabelText('Undisclosed')).toBeTruthy()
    },
}

export const Danger = {
    name: 'Danger zone',
    args: {
        title: 'Danger zone',
        tone: 'danger',
        slots: { default: { component: SettingRow, props: { title: 'Archive campaign' }, slots: { default: { component: Button, props: { size: 'sm', color: 'transparent' }, slots: { default: 'Archive' } } } } },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('.settings-group')).toHaveClass('settings-group--danger')
        await expect(canvas.getByRole('button', { name: 'Archive' })).toBeVisible()
    },
}
