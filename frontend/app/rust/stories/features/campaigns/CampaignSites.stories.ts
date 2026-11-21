import { expect, within } from 'storybook/test'
import CampaignSites from '@components/blocks/CampaignSites.astro'
import { ensure_edge_fade, sites_busy, sites_typical } from '../../../fixtures/features/campaigns'

ensure_edge_fade()

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignSites',
    component: CampaignSites,
    parameters: {
        docs: {
            description: {
                component: [
                    'The sites table with its pager, in the Sites tab of `/campaigns/<slug>/`. The Newer and Older buttons request `/partials/campaign_sites_component?slug=...&page=N` and swap the whole block.',
                    'Scenarios: the first page with more behind it, a middle page, the last page, a lone page (no pager), and no sites at all.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        slug: { control: 'text', description: 'Campaign slug, used to build the pager URLs.' },
        sites: { control: 'object', description: 'The sites on this page.' },
        page: { control: 'number', description: 'Current page, starting at 1.' },
        has_more: { control: 'boolean', description: 'Whether an older page exists; the total is not known.' },
    },
    args: { slug: 'amamake-defense', sites: sites_busy, page: 1, has_more: true },
}

export const FirstPage = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('#campaign-sites')).not.toBeNull()
        await expect(canvas.getAllByRole('row')).toHaveLength(26)
        await expect(canvas.getByText('Page 1')).toBeVisible()
        const older = canvas.getByRole('button', { name: /Older/ })
        await expect(older).toHaveAttribute('hx-get', '/partials/campaign_sites_component?slug=amamake-defense&page=2')
        await expect(canvas.queryByRole('button', { name: /Newer/ })).toBeNull()
    },
}

export const MiddlePage = {
    args: { page: 3, has_more: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Page 3')).toBeVisible()
        await expect(canvas.getByRole('button', { name: /Newer/ })).toHaveAttribute('hx-get', '/partials/campaign_sites_component?slug=amamake-defense&page=2')
        await expect(canvas.getByRole('button', { name: /Older/ })).toHaveAttribute('hx-get', '/partials/campaign_sites_component?slug=amamake-defense&page=4')
    },
}

export const LastPage = {
    args: { sites: sites_typical, page: 4, has_more: false },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(sites_typical.length + 1)
        await expect(canvas.getByRole('button', { name: /Newer/ })).toBeVisible()
        await expect(canvas.queryByRole('button', { name: /Older/ })).toBeNull()
    },
}

export const SinglePage = {
    args: { sites: sites_typical, page: 1, has_more: false },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Medium complex')).toBeVisible()
        // A lone first page shows no pager.
        await expect(canvas.queryByRole('button')).toBeNull()
    },
}

export const Empty = {
    args: { sites: [], page: 1, has_more: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No sites logged yet.')).toBeVisible()
    },
}
