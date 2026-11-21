import { expect, userEvent, waitFor, within } from 'storybook/test'
import CampaignCorporationBoard from '@components/blocks/CampaignCorporationBoard.astro'
import { select_control } from '../../_controls'
import { corporation_rows, ensure_edge_fade } from '../../../fixtures/features/campaigns'

ensure_edge_fade()

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignCorporationBoard',
    component: CampaignCorporationBoard,
    parameters: {
        docs: {
            description: {
                component: [
                    'The pilot leaderboard summed by each pilot\'s main\'s corporation, on a campaign page (`/campaigns/<slug>/`, Pilots tab). It has the same metric and period switches as the pilot board and re-renders through `/partials/campaign_corporations_component`; only corporations that scored are listed.',
                    'Scenarios: a typical board of six corporations plus a pilot with no corporation, a single corporation, an empty board, and a different metric and period.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        slug: { control: 'text', description: 'Campaign slug, used to build the partial URL.' },
        rows: { control: 'object', description: 'Ranked corporations with the pilots who scored and their summed value.' },
        metric: select_control(['kills', 'sites', 'advantage', 'fcs'], 'The selected metric; it names the last column.'),
        period: select_control(['week', 'rolling7', 'all'], 'The selected window.'),
    },
    args: { slug: 'amamake-defense', rows: corporation_rows, metric: 'kills', period: 'week' },
}

export const Typical = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rattini Tribe')).toBeVisible()
        await expect(canvas.getByText('Republic Fleet Auxiliary')).toBeVisible()
        await expect(canvas.getByRole('columnheader', { name: 'Corporation' })).toBeVisible()
        await expect(canvas.getByRole('columnheader', { name: 'Pilots' })).toBeVisible()
        await expect(canvas.getByText('482')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Kills', pressed: true })).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'This week', pressed: true })).toBeVisible()
        // The last row has no corporation: no logo and the "No primary character" label.
        await expect(canvas.getByText('No primary character')).toBeVisible()
        await expect(canvasElement.querySelectorAll('img')).toHaveLength(6)
    },
}

export const SingleCorporation = {
    args: { rows: corporation_rows.slice(0, 1) },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rattini Tribe')).toBeVisible()
        await expect(canvas.queryByText('Republic Fleet Auxiliary')).toBeNull()
    },
}

export const FcsRolling7 = {
    args: { metric: 'fcs', period: 'rolling7' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'FCs', pressed: true })).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Rolling 7 days', pressed: true })).toBeVisible()
        await expect(canvas.getByRole('columnheader', { name: 'FCs' })).toBeVisible()
    },
}

export const Empty = {
    args: { rows: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No corporation on the board yet.')).toBeVisible()
        await expect(canvas.queryByRole('columnheader')).toBeNull()
        await expect(canvas.getByRole('button', { name: 'Advantage' })).toBeVisible()
    },
}

export const SwitchingPeriodRequestsPartial = {
    tags: ['browser'],
    parameters: {
        htmx: {
            '/partials/campaign_corporations_component': '<div id="campaign-corporation-board"><small>All-time corporations</small></div>',
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByRole('button', { name: 'All time' }))
        await waitFor(() => expect(canvas.getByText('All-time corporations')).toBeVisible())
        const requests = (window as any).__rust_htmx_requests as { url: string }[]
        await expect(requests.some(r => r.url.includes('metric=kills') && r.url.includes('period=all'))).toBe(true)
    },
}
