import { expect, within } from 'storybook/test'
import CampaignCorporationStats from '@components/blocks/CampaignCorporationStats.astro'
import { corporation_roster, ensure_edge_fade } from '../../../fixtures/features/campaigns'

ensure_edge_fade()

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignCorporationStats',
    component: CampaignCorporationStats,
    parameters: {
        docs: {
            description: {
                component: [
                    'The campaign roster rolled up by corporation, on `/campaigns/<slug>/corporations/` and in the roster panels of the campaign page. Each row shows pilots, pilots active in the last week, characters counted, kills, losses, ISK destroyed, complexes, fleets attended and the last active day. On a phone the grid stacks and each cell carries its column label.',
                    'Scenarios: a typical roster of three corporations plus pilots without a primary character, a single corporation, and no roster yet.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        corporations: { control: 'object', description: 'Corporation rollups from `/api/campaigns/<slug>/roster`.' },
    },
    args: { corporations: corporation_roster },
}

export const Typical = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(corporation_roster.length + 1)
        await expect(canvas.getByText('Rattini Tribe')).toBeVisible()
        await expect(canvas.getByText('Republic Fleet Auxiliary')).toBeVisible()
        await expect(canvas.getByRole('columnheader', { name: 'ISK destroyed' })).toBeVisible()
        await expect(canvas.getByText(/41\.3/)).toBeVisible()
        // Tribal Liberation Front Veterans have gone quiet: 6 of 28 pilots active.
        const row = canvas.getByText('Tribal Liberation Front Veterans').closest('[role=row]') as HTMLElement
        await expect(within(row).getByText('28')).toBeVisible()
        await expect(within(row).getByText('6')).toBeVisible()
    },
}

export const PilotsWithoutAPrimary = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const row = canvas.getByText('No primary character').closest('[role=row]') as HTMLElement
        await expect(row.querySelector('img')).toBeNull()
        // Never active: the last active column shows a dash.
        await expect(within(row).getByText('—')).toBeVisible()
    },
}

export const SingleCorporation = {
    args: { corporations: corporation_roster.slice(0, 1) },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(2)
        await expect(canvasElement.querySelectorAll('img')).toHaveLength(1)
    },
}

export const Empty = {
    args: { corporations: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Nobody enlisted yet.')).toBeVisible()
        await expect(canvas.queryByRole('row')).toBeNull()
    },
}
