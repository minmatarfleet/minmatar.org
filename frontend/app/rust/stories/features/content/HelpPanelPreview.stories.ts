import { expect, within } from 'storybook/test'
import HelpPanelPreview from '@components/blocks/HelpPanelPreview.astro'
import { help_full, help_empty, help_no_channel, help_unknown_channel } from '../../../fixtures/features/content'

export default {
    title: 'Features/Content/HelpPanelPreview',
    component: HelpPanelPreview,
    parameters: {
        docs: {
            description: {
                component: [
                    'What the #help panel looks like in Discord: the channel name above one button per active option, in panel order. After an option is saved the server re-renders it out of band (`oob`).',
                    'It sits beside the option editor on the Help tab of `/admin/content/`. The scenarios show a full panel (inactive options are left out), a panel with no active option, no channel chosen, and a channel the site has not synced.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        settings: { control: 'object', description: 'The help settings (categories and panel).' },
        oob: { control: 'boolean', description: 'Re-render out of band (hx-swap-oob).' },
    },
    args: { settings: help_full, oob: false },
}

export const FullPanel = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('How it looks in Discord')).toBeVisible()
        await expect(canvas.getByText('#help')).toBeVisible()
        const buttons = canvas.getAllByRole('listitem')
        await expect(buttons.map(b => b.textContent)).toEqual(['Recruitment', 'SRP', 'Industry orders', 'Report a bug', 'Capitals'])
        await expect(canvas.queryByText('Retired option')).toBeNull()
    },
}

export const NoActiveOptions = {
    args: { settings: help_empty },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No options are shown, so the panel has no buttons.')).toBeVisible()
        await expect(canvas.queryByRole('list')).toBeNull()
    },
}

export const NoChannel = {
    args: { settings: help_no_channel },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('No channel yet')).toBeVisible()
    },
}

export const UnsyncedChannel = {
    args: { settings: help_unknown_channel },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('A channel the site has not synced')).toBeVisible()
    },
}

export const OutOfBand = {
    args: { oob: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('#help-panel-preview')).toHaveAttribute('hx-swap-oob', 'true')
    },
}
