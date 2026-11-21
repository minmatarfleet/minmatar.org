import { expect, within } from 'storybook/test'
import CorporationLeadershipSummary from '@components/blocks/CorporationLeadershipSummary.astro'
import {
    leadership_ceo_only,
    leadership_directors_only,
    leadership_full,
} from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/CorporationLeadershipSummary',
    component: CorporationLeadershipSummary,
    parameters: {
        docs: {
            description: {
                component: [
                    "The leadership strip on a corporation's About tab (`/alliance/corporations/<corp>/`): the CEO card with timezone regions, a directors card, and a link to the full Leadership tab.",
                    'Scenarios show a full team, a CEO with no directors, directors with no CEO, and an empty leadership list (the block renders nothing).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        leadership: { control: 'object' },
        full_list_href: { control: 'text', description: 'Where "Full list" points.' },
    },
    args: { leadership: leadership_full, full_list_href: '#leadership' },
}

export const FullTeam = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Leadership' })).toBeVisible()
        await expect(canvas.getByText("Kel'dar Atram")).toBeVisible()
        await expect(canvas.getByText('Directors · 4')).toBeVisible()
        await expect(canvas.getByText('Hela Brutori')).toBeVisible()
        await expect(canvasElement.querySelectorAll('.zones .zone').length).toBeGreaterThan(0)
        await expect(canvasElement.querySelector('.section-head a')).toHaveAttribute('href', '#leadership')
    },
}

export const CeoOnly = {
    args: { leadership: leadership_ceo_only },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('CEO')).toBeVisible()
        await expect(within(canvasElement).queryByText(/Directors/)).toBeNull()
    },
}

export const DirectorsOnly = {
    args: { leadership: leadership_directors_only },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Directors · 2')).toBeVisible()
        await expect(within(canvasElement).queryByText('CEO')).toBeNull()
    },
}

export const NoLeadership = {
    // The block renders nothing without a CEO or directors.
    parameters: { rust: { allow_empty: true } },
    args: { leadership: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.leaders')).toBeNull()
    },
}
