import { expect, within } from 'storybook/test'
import StructurePingsPanel from '@components/blocks/StructurePingsPanel.astro'
import { pings_typical, pings_all_posted, pings_busy } from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/StructurePingsPanel',
    component: StructurePingsPanel,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Pings tab of `/intel/timers/manage/`: the last 100 structure pings the bot sent and whether Discord took them. The Failed chip is the "needs attention" view; changing a chip reloads this panel from `structure_timers_manage_component?part=pings`.',
                    'The scenarios show the full list with failures, the Failed view, a list where every ping was posted, an empty list and a long run of pings.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        pings: { control: 'object', description: 'Recent pings from the API, newest first.' },
        view: { control: 'radio', options: ['all', 'failed'], description: 'Which chip is selected.' },
    },
    args: { pings: pings_typical, view: 'all' },
}

type Ctx = { canvasElement: HTMLElement }

export const AllPings = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('The last 100 pings the bot sent about our structures.')).toBeVisible()
        await expect(canvas.getByRole('table', { name: 'Structure pings' })).toBeVisible()
        await expect(canvasElement.querySelectorAll('tbody tr.manage-row')).toHaveLength(6)
        await expect(canvas.getAllByText('Posted')).toHaveLength(4)
        await expect(canvas.getAllByText('Failed', { selector: 'td' })).toHaveLength(2)
        await expect(canvas.getByText('Structure under attack')).toBeVisible()
        await expect(canvas.getByRole('radio', { name: /All/ })).toBeChecked()
    },
}

export const FailedView = {
    args: { view: 'failed' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('tbody tr.manage-row')).toHaveLength(2)
        await expect(canvas.queryByText('Posted')).toBeNull()
        await expect(canvas.getByRole('radio', { name: /Failed/ })).toBeChecked()
    },
}

export const NothingFailed = {
    args: { pings: pings_all_posted, view: 'failed' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('Discord took every recent ping')).toBeVisible()
    },
}

export const NoPings = {
    args: { pings: [], view: 'all' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No pings')).toBeVisible()
        await expect(within(canvasElement).queryByRole('table')).toBeNull()
    },
}

export const BusyHistory = {
    args: { pings: pings_busy, view: 'all' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('tbody tr.manage-row')).toHaveLength(40)
    },
}
