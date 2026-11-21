import { expect, within } from 'storybook/test'
import CampaignCard from '@components/blocks/CampaignCard.astro'
import {
    active_enlisted,
    active_faction_warfare,
    active_strategic,
    bare_campaign,
    completed_campaign,
    launching_campaign,
    long_name_campaign,
    upcoming_campaign,
} from '../../../fixtures/features/campaigns'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignCard',
    component: CampaignCard,
    decorators: [(Story: () => string) => `<div style="max-width: 24rem">${Story()}</div>`],
    parameters: {
        docs: {
            description: {
                component: [
                    'The picture card for one campaign on the campaigns list (`/campaigns/`). It shows the kind (Faction Warfare or Strategic), an Enlisted tag when the pilot has joined, the run dates, the name, tagline and the sides ("Against ... / With ...").',
                    'Scenarios: an active Faction Warfare campaign, one the pilot is enlisted in, a strategic campaign against Snuffed Out, an upcoming card (no link, a countdown instead of dates), a completed one, and edge cases with very long text and no tagline or sides.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        campaign: { control: 'object', description: 'The campaign list item from `/api/campaigns`.' },
        index: { control: 'number', description: 'Position in the list; unused by the markup.' },
    },
    args: { campaign: active_faction_warfare },
}

export const Active = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Amamake Defense' })).toBeVisible()
        await expect(canvas.getByText('Faction Warfare')).toBeVisible()
        await expect(canvas.queryByText('Enlisted')).toBeNull()
        await expect(canvas.getByText('Keep Amamake free and the complexes cycling.')).toBeVisible()
        await expect(canvas.getByText(/Against Amarr Empire/)).toBeVisible()
        const links = canvas.getAllByRole('link')
        for (const link of links) await expect(link).toHaveAttribute('href', '/campaigns/amamake-defense/')
        await expect(canvas.getByRole('link', { name: 'View campaign' })).toBeVisible()
    },
}

export const Enlisted = {
    args: { campaign: active_enlisted },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Auga Offensive' })).toBeVisible()
        await expect(canvas.getByText('Enlisted')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'View campaign' })).toHaveAttribute('href', '/campaigns/auga-offensive/')
    },
}

export const Strategic = {
    args: { campaign: active_strategic },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Strategic')).toBeVisible()
        // At most three enemies and three allies, by ticker.
        await expect(canvas.getByText(/Against SNUFF, CVA, HADO · With FL33T, A-RAT, RFA/)).toBeVisible()
        await expect(canvas.queryByText(/FHBM|FFC/)).toBeNull()
    },
}

export const Upcoming = {
    args: { campaign: upcoming_campaign },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Huola Recapture' })).toBeVisible()
        await expect(canvas.getByText(/Starts in \d+ Days?/)).toBeVisible()
        // An upcoming campaign is not clickable yet.
        await expect(canvas.queryByRole('link')).toBeNull()
        await expect(canvas.queryByText('View campaign')).toBeNull()
    },
}

export const LaunchingSoon = {
    args: { campaign: launching_campaign },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Launching soon')).toBeVisible()
        await expect(canvas.queryByRole('link')).toBeNull()
    },
}

export const Completed = {
    args: { campaign: completed_campaign },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Amamake Defense (October)' })).toBeVisible()
        await expect(canvas.getByText('Enlisted')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'View campaign' })).toHaveAttribute('href', '/campaigns/amamake-defense-october/')
    },
}

export const LongText = {
    args: { campaign: long_name_campaign },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: /Grand Combined Minmatar/ })).toBeVisible()
        // A ticker over six characters is not a ticker: the party name is shown instead.
        await expect(canvas.getByText(/Against The Imperial Amarrian Domain Combined Fleet Command · With MR/)).toBeVisible()
    },
}

export const NoTaglineNoSides = {
    args: { campaign: bare_campaign },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Bare Campaign' })).toBeVisible()
        await expect(canvasElement.querySelector('.campaign-card-tagline')).toBeNull()
        await expect(canvasElement.querySelector('.campaign-card-parties')).toBeNull()
        await expect(canvas.getByRole('link', { name: 'View campaign' })).toBeVisible()
    },
}
