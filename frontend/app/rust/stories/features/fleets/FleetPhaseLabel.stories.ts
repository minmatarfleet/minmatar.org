import { expect, within } from 'storybook/test'
import FleetPhaseLabel from '@components/blocks/FleetPhaseLabel.astro'
import { completed_tracking_texts } from '../../../fixtures/features/fleets'

const phases = ['upcoming', 'active', 'completed', 'cancelled'] as const

export default {
    title: 'Features/Fleets/FleetPhaseLabel',
    component: FleetPhaseLabel,
    parameters: {
        docs: {
            description: {
                component: [
                    'The spaced-out state word every fleet view shows: Active (blinking), Completed or Cancelled (red). An upcoming fleet renders nothing, the countdown stands in for it. It appears in fleet list rows, the feed on the home page and the status block on `/fleets/upcoming/<id>`.',
                    'Completed fleets can pass `completed_detail` (the end time and duration texts) to add the line under the word; leaving it `undefined` shows the bare word.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        phase: { control: 'inline-radio', options: phases, description: 'Where the fleet is in its life: cancelled wins over tracking, a tracked fleet is active until it has an end time.' },
        completed_detail: { control: 'object', description: 'Completed only: end time, duration and tooltip texts, or `false` for none.' },
    },
    args: { phase: 'active' },
}

export const Active = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const label = within(canvasElement).getByText('Active')
        await expect(label).toHaveClass('blink-animation')
        await expect(label).not.toHaveClass('status-text--danger')
    },
}

export const Upcoming = {
    args: { phase: 'upcoming' },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // Nothing to say before the fleet starts: the countdown sits where the label would.
        await expect(canvasElement.querySelector('.status-text')).toBeNull()
        await expect(canvasElement.textContent?.trim()).toBe('')
    },
}

export const Cancelled = {
    args: { phase: 'cancelled' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Cancelled')).toHaveClass('status-text--danger')
    },
}

export const CompletedBare = {
    args: { phase: 'completed' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Completed')).toBeVisible()
        await expect(canvasElement.querySelector('small')).toBeNull()
    },
}

export const CompletedWithDuration = {
    args: { phase: 'completed', completed_detail: completed_tracking_texts },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Completed')).toBeVisible()
        await expect(canvas.getByText(/Nov 14, 2026, 21:31/)).toBeVisible()
        await expect(canvas.getByText('2h 27m')).toHaveAttribute('data-tippy-content', completed_tracking_texts.fleet_tracking_hint)
    },
}

export const CompletedWithoutTracking = {
    args: { phase: 'completed', completed_detail: false },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // `false` means "tracking texts unavailable": the word only, no empty parentheses.
        await expect(within(canvasElement).getByText('Completed')).toBeVisible()
        await expect(canvasElement.textContent).not.toContain('(')
    },
}
