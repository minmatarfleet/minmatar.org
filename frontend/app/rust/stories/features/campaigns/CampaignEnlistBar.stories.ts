import { expect, within } from 'storybook/test'
import CampaignEnlistBar from '@components/blocks/CampaignEnlistBar.astro'
import { campaign_detail, leaderboard_podium, leaderboard_rows } from '../../../fixtures/features/campaigns'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignEnlistBar',
    component: CampaignEnlistBar,
    parameters: {
        layout: 'fullscreen',
        docs: {
            description: {
                component: [
                    'The bar docked to the bottom of a campaign page (`/campaigns/<slug>/`). It rolls this week\'s top killers in a reel and keeps one action in reach: Enlist (posts to `/partials/campaign_actions_component?action=enlist`) or, once enlisted, a link to the pilot\'s own tab with their rank.',
                    'Scenarios: not enlisted with a busy board, enlisted with a rank, enlisted without kills, a short board shown without the scrolling marquee, and an empty board.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        campaign: { control: 'object', description: 'The campaign detail; `is_enlisted`, `slug` and `totals.enlisted` drive the bar.' },
        leaderboard: { control: 'object', description: 'This week\'s kills leaderboard; rows without a character are ignored.' },
        user_id: { control: 'number', description: 'The signed-in user, used to find their own row.' },
    },
    args: { campaign: campaign_detail(), leaderboard: leaderboard_rows(10), user_id: 999 },
}

export const NotEnlisted = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const bar = canvasElement.querySelector('#campaign-enlist-bar') as HTMLElement
        await expect(bar).toHaveAttribute('data-enlisted', 'false')
        await expect(canvas.getByText('You are not enlisted')).toBeVisible()
        await expect(canvas.getByText('412 pilots are. Enlist and your kills count.')).toBeVisible()
        const enlist = canvas.getByRole('button', { name: 'Enlist' })
        await expect(enlist).toHaveAttribute('hx-post', '/partials/campaign_actions_component?slug=amamake-defense&action=enlist')
        await expect(enlist).toHaveAttribute('hx-target', '#campaign-actions-amamake-defense')
        // Ten pilots roll in the marquee.
        await expect(canvas.getAllByText("Kel'dar Atram").length).toBeGreaterThan(0)
    },
}

export const EnlistedWithRank = {
    args: { campaign: campaign_detail({ is_enlisted: true, characters_included: 3, characters_tracked: 3 }), user_id: 1002 },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('#campaign-enlist-bar')).toHaveAttribute('data-enlisted', 'true')
        await expect(canvas.getByText('Enlisted')).toBeVisible()
        // user 1002 is the third row of the board.
        await expect(canvas.getByText(/^#3 this week · \d+ kills$/)).toBeVisible()
        await expect(canvas.queryByRole('button', { name: 'Enlist' })).toBeNull()
        await expect(canvas.getByRole('link', { name: 'Your campaign' })).toHaveAttribute('href', '#you')
    },
}

export const EnlistedNoKillsYet = {
    args: { campaign: campaign_detail({ is_enlisted: true }), user_id: 4242 },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No kills this week yet')).toBeVisible()
    },
}

export const ShortBoardWithoutMarquee = {
    args: { leaderboard: leaderboard_podium },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByText(/^\d+ kills$/)).toHaveLength(3)
        await expect(canvasElement.querySelector('.marquee, [class*="marquee"]')).toBeNull()
    },
}

export const EmptyBoard = {
    args: { leaderboard: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Nobody is on the board this week yet. Be the first.')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Enlist' })).toBeVisible()
    },
}

export const OnePilotOneKill = {
    args: { leaderboard: [{ rank: 1, user_id: 1000, character_id: 2112954532, character_name: "Kel'dar Atram", value: 1 }], campaign: campaign_detail({ is_enlisted: true }), user_id: 1000 },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // Singular wording for one kill.
        await expect(canvas.getByText('#1 this week · 1 kill')).toBeVisible()
    },
}
