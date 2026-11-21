import { expect, userEvent, waitFor, within } from 'storybook/test'
import CampaignLeaderboard from '@components/blocks/CampaignLeaderboard.astro'
import { select_control } from '../../_controls'
import {
    ensure_edge_fade,
    leaderboard_busy,
    leaderboard_edge,
    leaderboard_empty,
    leaderboard_podium,
    leaderboard_single,
} from '../../../fixtures/features/campaigns'

ensure_edge_fade()

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignLeaderboard',
    component: CampaignLeaderboard,
    parameters: {
        docs: {
            description: {
                component: [
                    'The pilot leaderboard on a campaign page (`/campaigns/<slug>/`, Pilots tab). Two segmented switches pick the metric (Kills, Complexes, Advantage, FCs) and the period (This week, Rolling 7 days, All time); each re-requests `/partials/campaign_leaderboard_component` with htmx and swaps the block. A local Alpine search filters the rows already on screen.',
                    'Scenarios: a busy 20-pilot board, a lone pilot, a podium of three, an empty board, other metric and period selections, and edge cases (no character, empty or very long names, a zero score).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        slug: { control: 'text', description: 'Campaign slug, used to build the partial URL.' },
        rows: { control: 'object', description: 'Ranked rows for the selected metric and period.' },
        metric: select_control(['kills', 'sites', 'advantage', 'fcs'], 'The selected metric; its button is pressed and it names the value column.'),
        period: select_control(['week', 'rolling7', 'all'], 'The selected window.'),
    },
    args: { slug: 'amamake-defense', rows: leaderboard_busy, metric: 'kills', period: 'week' },
}

const pressed = (canvas: ReturnType<typeof within>) =>
    canvas.getAllByRole('button').filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.textContent?.trim())

export const Busy = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('[data-pilot]')).toHaveLength(20)
        await expect(canvas.getByText("Kel'dar Atram")).toBeVisible()
        await expect(canvas.getByRole('columnheader', { name: 'Pilot' })).toBeVisible()
        await expect(pressed(canvas)).toEqual(['Kills', 'This week'])
        await expect(canvas.getByRole('searchbox', { name: 'Search pilots' })).toBeVisible()
    },
}

export const SearchFiltersRows = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(canvas.getByRole('searchbox', { name: 'Search pilots' }), 'sabrina')
        await waitFor(() => {
            const visible = [...canvasElement.querySelectorAll<HTMLElement>('[data-pilot]')].filter(r => !r.hidden)
            expect(visible).toHaveLength(1)
        })
        await expect(canvas.getByText('Sabrina Thule')).toBeVisible()
    },
}

export const SearchWithNoMatch = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(canvas.getByRole('searchbox', { name: 'Search pilots' }), 'zzzzz')
        await waitFor(() => expect(canvas.getByText('No pilot matches.')).toBeVisible())
    },
}

export const SinglePilot = {
    args: { rows: leaderboard_single },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('[data-pilot]')).toHaveLength(1)
        await expect(within(canvasElement).getByText("Kel'dar Atram")).toBeVisible()
    },
}

export const Podium = {
    args: { rows: leaderboard_podium, metric: 'sites', period: 'rolling7' },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('[data-pilot]')).toHaveLength(3)
        await expect(pressed(canvas)).toEqual(['Complexes', 'Rolling 7 days'])
        await expect(canvas.getByRole('columnheader', { name: 'Value' })).toBeVisible()
    },
}

export const AdvantageAllTime = {
    args: { metric: 'advantage', period: 'all' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(pressed(within(canvasElement))).toEqual(['Advantage', 'All time'])
    },
}

export const Empty = {
    args: { rows: leaderboard_empty },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Nobody on the board yet.')).toBeVisible()
        await expect(canvas.queryByRole('searchbox')).toBeNull()
        await expect(canvasElement.querySelectorAll('[data-pilot]')).toHaveLength(0)
        // The switches stay, so a pilot can look at another window.
        await expect(canvas.getByRole('button', { name: 'All time' })).toBeVisible()
    },
}

export const EdgeCases = {
    args: { rows: leaderboard_edge },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('[data-pilot]')).toHaveLength(4)
        // A row without a name falls back to "Unknown pilot"; one without a character id has no portrait.
        await expect(canvas.getByText('Unknown pilot')).toBeVisible()
        await expect(canvas.getByText(/Maximilian Bartholomew-Featherstonehaugh/)).toBeVisible()
        await expect(canvasElement.querySelectorAll('img')).toHaveLength(3)
        await expect(canvas.getByText('0')).toBeVisible()
    },
}

export const SwitchingMetricRequestsPartial = {
    tags: ['browser'],
    parameters: {
        htmx: {
            '/partials/campaign_leaderboard_component': '<div id="campaign-leaderboard"><small>Complexes board</small></div>',
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByRole('button', { name: 'Complexes' }))
        await waitFor(() => expect(canvas.getByText('Complexes board')).toBeVisible())
        const requests = (window as any).__rust_htmx_requests as { url: string }[]
        await expect(requests.some(r => r.url.includes('slug=amamake-defense') && r.url.includes('metric=sites') && r.url.includes('period=week'))).toBe(true)
    },
}
