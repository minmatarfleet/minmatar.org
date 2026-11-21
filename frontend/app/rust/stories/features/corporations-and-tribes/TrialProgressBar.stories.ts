import { expect, within } from 'storybook/test'
import TrialProgressBar from '@components/blocks/TrialProgressBar.astro'
import {
    trial_alliance_average,
    trial_behind,
    trial_no_average,
    trial_on_pace,
    trial_overdue,
} from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/TrialProgressBar',
    component: TrialProgressBar,
    parameters: {
        docs: {
            description: {
                component: [
                    "A trial pilot's day-of-trial bar, shown on the account Trial tab (`/account/`) and, in its compact form, on each trial row of the corporation Members tab. Markers show when review opens and the average trial length for the corporation or alliance.",
                    'Scenarios: on pace (green), behind pace, past the end of the scale, the alliance-wide average (no corp ticker), no average yet, and the compact row version.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        trial: { control: 'object', description: 'TrialProgress from the trial report API.' },
        ticker: { control: 'text', description: 'Corporation ticker used in the average label.' },
        compact: { control: 'boolean', description: 'Short marker labels for roster rows.' },
    },
    args: { trial: trial_on_pace, ticker: 'A-RAT', compact: false },
}

export const OnPace = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const bar = canvasElement.querySelector('.trial-bar') as HTMLElement
        await expect(bar).toHaveClass('is-on-pace')
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('img', { name: /Day 18 of trial/ })).toBeInTheDocument()
        await expect(canvas.getByText('A-RAT average · day 34')).toBeVisible()
        await expect(canvas.getByText('Review opens · day 28')).toBeVisible()
        await expect(canvas.getByText('Day 1')).toBeVisible()
    },
}

export const BehindPace = {
    args: { trial: trial_behind },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.trial-bar')).not.toHaveClass('is-on-pace')
        await expect(within(canvasElement).getByRole('img', { name: /Day 31 of trial/ })).toBeInTheDocument()
    },
}

export const PastTheScale = {
    args: { trial: trial_overdue },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const fill = canvasElement.querySelector('.trial-bar__fill') as HTMLElement
        await expect(fill.getAttribute('style')).toContain('width: 100%')
        await expect(within(canvasElement).getByRole('img', { name: /Day 62 of trial/ })).toBeInTheDocument()
    },
}

export const AllianceAverage = {
    args: { trial: trial_alliance_average, ticker: null },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.textContent).toContain('average · day 38')
        await expect(canvasElement.textContent).not.toContain('A-RAT')
    },
}

export const NoAverageYet = {
    args: { trial: trial_no_average },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.textContent).not.toContain('average')
        await expect(within(canvasElement).getByText('Review opens · day 28')).toBeVisible()
    },
}

export const Compact = {
    args: { compact: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('.trial-bar')).toHaveClass('is-compact')
        await expect(canvas.getByText('Avg · 34')).toBeVisible()
        await expect(canvas.getByText('Review · 28')).toBeVisible()
        await expect(canvas.queryByText('Day 1')).toBeNull()
    },
}
