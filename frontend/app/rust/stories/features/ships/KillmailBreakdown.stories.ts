import { expect, within, waitFor } from 'storybook/test'
import KillmailBreakdown from '@components/blocks/KillmailBreakdown.astro'
import type { PlayArgs } from './_helpers'
import {
    killmail_rifter_loss, killmail_no_fleet, killmail_wrong_program, killmail_not_eligible,
} from '../../../fixtures/features/ships'

// Entrance animations (up to ~1s of delay plus duration) start at opacity 0, so wait for them to settle before asserting visibility.
const settle = (check: () => unknown) => waitFor(check, { timeout: 3000 })

export default {
    title: 'Features/Ships/KillmailBreakdown',
    component: KillmailBreakdown,
    parameters: {
        docs: {
            description: {
                component: 'The result of pasting a killmail into the SRP wizard (`/srp/`): who lost which ship for how much, then what the pilot has to do next. If the ship is covered by the chosen program, the pilot picks the fleet it was lost in from the candidate fleets (or "None of the fleets"); if the hull belongs to another program or to none, the block explains and offers the program buttons. The scenarios show each of those outcomes.',
            },
        },
    },
    argTypes: {
        killmail_analysis: { control: 'object', description: 'The analysis of the pasted killmail: pilot, hull, value, SRP program and candidate fleets.' },
        program: { control: 'inline-radio', options: ['subcapitals', 'dreads', 'carriers'], description: 'The SRP program tab the pilot is on.' },
        external_killmail_link: { control: 'text', description: 'The zKillboard link carried into the SRP request.' },
    },
    args: {
        killmail_analysis: killmail_rifter_loss,
        program: 'subcapitals',
        external_killmail_link: 'https://zkillboard.com/kill/134510244/',
    },
}

export const CandidateFleets = {
    tags: ['browser'],
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByText('Can you see the fleet you lost your ship listed here?')).toBeVisible())
        await settle(() => expect(canvas.getByRole('button', { name: 'None of the fleets' })).toBeVisible())
        await settle(() => expect(canvas.getByText("Kel'dar Atram")).toBeVisible())
        await settle(() => expect(canvas.getByText('18,400,000 ISK')).toBeVisible())
    },
}

export const NoCandidateFleet = {
    args: { killmail_analysis: killmail_no_fleet },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByText(/We couldn’t find any active fleet around your killmail time/)).toBeVisible())
        await expect(canvas.queryByRole('button', { name: 'None of the fleets' })).toBeNull()
    },
}

export const WrongProgram = {
    args: { killmail_analysis: killmail_wrong_program },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.textContent).toMatch(/You are submitting a killmail for/)
        await expect(canvasElement.querySelectorAll('strong')).toHaveLength(2)
    },
}

export const ShipNotEligible = {
    args: { killmail_analysis: killmail_not_eligible },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByText(/not eligible for any of the current SRP programs/)).toBeVisible())
        await settle(() => expect(canvas.getByText('41,900,000 ISK')).toBeVisible())
        await settle(() => expect(canvas.getByText('Republic Fleet Firetail')).toBeVisible())
    },
}
