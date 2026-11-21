import { expect, within } from 'storybook/test'
import CampaignSitesTable from '@components/blocks/CampaignSitesTable.astro'
import { ensure_edge_fade, sites_busy, sites_edge, sites_typical } from '../../../fixtures/features/campaigns'

ensure_edge_fade()

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignSitesTable',
    component: CampaignSitesTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'The log of sites pilots ran for a campaign, in the Sites tab of `/campaigns/<slug>/`: when, system, who, and what. A complex shows its size ("Medium complex") with the LP payout in a tooltip; a complex of unknown size reads "Complex - 1,240 LP"; other site kinds (advantage sites, rendezvous points, propaganda beacons...) are named.',
                    'Scenarios: a typical log with every site kind, a 25-row busy log, an empty log, and edge cases (an unmapped site kind, a pilot without a character id, a very long name).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        sites: { control: 'object', description: 'Sites, newest first, from `/api/campaigns/<slug>/sites`.' },
    },
    args: { sites: sites_typical },
}

export const Typical = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(sites_typical.length + 1)
        await expect(canvas.getByText('Medium complex')).toBeVisible()
        await expect(canvas.getByText('Small complex')).toBeVisible()
        await expect(canvas.getByText('Advantage site')).toBeVisible()
        await expect(canvas.getByText('Propaganda beacon')).toBeVisible()
        await expect(canvas.getByText('Rendezvous point')).toBeVisible()
        await expect(canvas.getByText('Supply cache')).toBeVisible()
        await expect(canvas.getByText('Listening outpost')).toBeVisible()
        await expect(canvas.getByText('Battlefield')).toBeVisible()
        await expect(canvas.getByText('Complex - 1,240 LP')).toBeVisible()
        await expect(canvas.getByText('Medium complex')).toHaveAttribute('title', '36,000 LP · Defensive · high confidence')
    },
}

export const Busy = {
    args: { sites: sites_busy },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(26)
        await expect(canvas.getAllByText('Advantage site').length).toBeGreaterThan(5)
        await expect(canvas.getAllByText('Large complex').length).toBeGreaterThan(0)
    },
}

export const Empty = {
    args: { sites: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No sites logged yet.')).toBeVisible()
        await expect(canvas.queryByRole('row')).toBeNull()
    },
}

export const EdgeCases = {
    args: { sites: sites_edge },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(3)
        // An unknown kind is shown readable rather than raw.
        await expect(canvas.getByText('unmapped site kind')).toBeVisible()
        await expect(canvas.getByText('Unknown pilot')).toBeVisible()
        await expect(canvas.getByText(/Maximilian Bartholomew-Featherstonehaugh/)).toBeVisible()
        // Only the second site has a pilot portrait.
        await expect(canvasElement.querySelectorAll('img')).toHaveLength(1)
    },
}
