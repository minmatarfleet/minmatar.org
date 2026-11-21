import { expect, within } from 'storybook/test'
import CampaignStructuresTable from '@components/blocks/CampaignStructuresTable.astro'
import {
    structures_busy,
    structures_edge,
    structures_single,
    structures_typical,
} from '../../../fixtures/features/campaigns'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignStructuresTable',
    component: CampaignStructuresTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'The structures under recon in a strategic campaign\'s theatre, on `/campaigns/<slug>/` (Structures tab): name and fit, system, type, owner, related alliance, side, status, reinforcement hour and timer or destruction time. Pilots with intel access also get Report structure and Add timer buttons that open the intel pages with the campaign preselected.',
                    'Scenarios: a typical mix of friendly, hostile and destroyed structures, a single reinforced keep, a busy 14-row list, the empty state, a pilot who can add timers, and long names with unknown structure types.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        structures: { control: 'object', description: 'Structures from `/api/campaigns/<slug>`.' },
        slug: { control: 'text', description: 'Campaign slug for the report and timer links.' },
        show_add_timer: { control: 'boolean', description: 'Show the Report structure and Add timer buttons (intel access).' },
        tracking: { control: 'text', description: 'Optional summary line under the hint, e.g. "3 destroyed · 7 remaining".' },
    },
    args: { structures: structures_typical, slug: 'snuffed-out-sovereignty', show_add_timer: false, tracking: '' },
}

export const Typical = {
    args: { tracking: '1 destroyed · 4 remaining' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Structures' })).toBeVisible()
        await expect(canvas.getAllByRole('row')).toHaveLength(structures_typical.length + 1)
        await expect(canvas.getByText('Amamake - Freeport')).toBeVisible()
        await expect(canvas.getByText('1 destroyed · 4 remaining')).toBeVisible()
        await expect(canvas.getByText('Reinforced')).toBeVisible()
        await expect(canvas.getByText('Destroyed')).toBeVisible()
        await expect(canvas.getByText('Unanchored')).toBeVisible()
        await expect(canvas.getAllByText('Friendly').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('Hostile').length).toBeGreaterThan(0)
        await expect(canvas.getByText('Neutral')).toBeVisible()
        await expect(canvas.getByText('18:00')).toBeVisible()
        // Structures with a recorded fit carry a Fit tag.
        await expect(canvas.getAllByText('Fit')).toHaveLength(2)
        await expect(canvas.queryByRole('link', { name: 'Add timer' })).toBeNull()
    },
}

export const WithIntelButtons = {
    args: { show_add_timer: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Report structure' })).toHaveAttribute('href', '/intel/add_structure/?campaign_slug=snuffed-out-sovereignty')
        await expect(canvas.getByRole('link', { name: 'Add timer' })).toHaveAttribute('href', '/intel/timers/add/?campaign_slug=snuffed-out-sovereignty')
    },
}

export const SingleReinforced = {
    args: { structures: structures_single },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(2)
        await expect(canvas.getByText('Auga - Forward Keep')).toBeVisible()
        await expect(canvas.getByText('Reinforced')).toBeVisible()
        // Owner and related alliance both read Clan Vanguard of Amarr.
        await expect(canvas.getAllByText('Clan Vanguard of Amarr')).toHaveLength(2)
    },
}

export const Busy = {
    args: { structures: structures_busy, show_add_timer: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(15)
        await expect(canvas.getByText('Amamake - Citadel 1')).toBeVisible()
        await expect(canvas.getByText('Auga - Citadel 2')).toBeVisible()
    },
}

export const Empty = {
    args: { structures: [], show_add_timer: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No structures under recon yet.')).toBeVisible()
        await expect(canvas.queryByRole('table')).toBeNull()
        // The buttons stay so a pilot can report the first one.
        await expect(canvas.getByRole('link', { name: 'Report structure' })).toBeVisible()
    },
}

export const EdgeCases = {
    args: { structures: structures_edge },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(3)
        await expect(canvas.getByText(/A Structure With An Extraordinarily Long Name/)).toBeVisible()
        // A reinforcement hour of 0 is a real value, not "no hour".
        await expect(canvas.getByText('00:00')).toBeVisible()
        await expect(canvas.getByText('Unknown Deployable')).toBeVisible()
    },
}
