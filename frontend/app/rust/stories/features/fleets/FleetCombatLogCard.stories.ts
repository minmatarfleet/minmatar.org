import { expect, within, waitFor } from 'storybook/test'
import FleetCombatLogCard from '@components/blocks/FleetCombatLogCard.astro'
import { combat_log, combat_log_unattributed, combat_log_long_name } from '../../../fixtures/features/fleets'

// Entrance animations (up to ~1s of delay plus duration) start at opacity 0, so wait for them to settle before asserting visibility.
const settle = (check: () => unknown) => waitFor(check, { timeout: 3000 })

export default {
    title: 'Features/Fleets/FleetCombatLogCard',
    component: FleetCombatLogCard,
    parameters: {
        docs: {
            description: {
                component: 'A combat log saved to the intel library, one card per upload: the pilot who logged it, when it was uploaded, the character and system it was logged in, and a Share button that copies its link. The card opens the log at `/intel/combatlog/<id>`. It sits in the saved logs grid on the fitting render page and in the combat log table.',
                // The "On <character> @ <system>" line only shows when the upload names a character.
            },
        },
    },
    argTypes: {
        log: { control: 'object', description: 'The saved combat log: id, upload time, uploader, logger and where it was logged.' },
    },
    args: { log: combat_log },
}

export const Typical = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { name: 'Tarsus Rennir' })).toBeVisible())
        await settle(() => expect(canvas.getByText('On Tarsus Rennir @ Amamake')).toBeVisible())
        await expect(canvasElement.querySelector('a')?.getAttribute('href')).toContain('/intel/combatlog/5501')
        // The Share action sits in the card's hover-revealed actions (opacity 0 until hover), so it is only in the DOM here.
        await expect(canvas.getByText('Share')).toBeInTheDocument()
    },
}

export const Unattributed = {
    args: { log: combat_log_unattributed },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { name: 'Tarsus Rennir' })).toBeVisible())
        await expect(canvas.queryByText(/^On /)).toBeNull()
        await expect(canvasElement.querySelector('a')?.getAttribute('href')).toContain('/intel/combatlog/5502')
    },
}

export const LongName = {
    args: { log: combat_log_long_name },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { name: /Bartholomew-Alexander of the Heimatar Highlands the Third/ })).toBeVisible())
        await settle(() => expect(canvas.getByText(/On Bartholomew-Alexander .* @ Old Man Star/)).toBeVisible())
    },
}
