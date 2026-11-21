import { expect, within, waitFor } from 'storybook/test'
import CombatLogItem from '@components/blocks/CombatLogItem.astro'
import { saved_log_fleet, saved_log_fitting, saved_log_solo } from '../../../fixtures/features/intel-and-combat'

// Entrance animations (up to ~1s of delay plus duration) start at opacity 0, so wait for them to settle before asserting visibility.
const settle = (check: () => unknown) => waitFor(check, { timeout: 3000 })

export default {
    title: 'Features/Intel and combat/CombatLogItem',
    component: CombatLogItem,
    parameters: {
        docs: {
            description: {
                component: [
                    'A saved combat log card on the pilot\'s own list at `/intel/combatlog/`. The icon and title depend on what the log was filed against: a fleet, a fitting, or just the pilot. Each card has a Share (copy link) button and a trash button that opens the remove dialog.',
                    'The scenarios show the three kinds and the fitting card when the fitting could not be resolved.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        log: { control: 'object', description: 'Saved log: fleet_id and fitting_id decide the title; 0 means not set.' },
        fitting: { control: 'object', description: 'The fitting the log was filed against, when there is one.' },
    },
    args: { log: saved_log_solo },
}

type Ctx = { canvasElement: HTMLElement }

export const PilotLog = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { name: "Kel'dar Atram" })).toBeVisible())
        // Share sits in the card's hover-revealed actions (opacity 0 until hover), so it is only in the DOM here.
        await expect(canvas.getByRole('button', { name: /Share/ })).toBeInTheDocument()
        await expect(canvasElement.querySelectorAll('button').length).toBeGreaterThanOrEqual(2)
    },
}

export const FleetLog = {
    args: { log: saved_log_fleet },
    play: async ({ canvasElement }: Ctx) => {
        await settle(() => expect(within(canvasElement).getByRole('heading', { name: 'Fleet 92221' })).toBeVisible())
    },
}

export const FittingLogUnresolved = {
    args: { log: saved_log_fitting },
    play: async ({ canvasElement }: Ctx) => {
        await settle(() => expect(within(canvasElement).getByRole('heading', { name: 'Unknown fitting name' })).toBeVisible())
    },
}
