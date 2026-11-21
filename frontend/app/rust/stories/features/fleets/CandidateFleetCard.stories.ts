import { expect, userEvent, within, waitFor } from 'storybook/test'
import CandidateFleetCard from '@components/blocks/CandidateFleetCard.astro'
import {
    candidate_fleet, candidate_fleet_training, candidate_fleet_no_objective, candidate_fleet_long_fc,
} from '../../../fixtures/features/fleets'

// Entrance animations (up to ~1s of delay plus duration) start at opacity 0, so wait for them to settle before asserting visibility.
const settle = (check: () => unknown) => waitFor(check, { timeout: 3000 })

const SRP_FORM_PARTIAL = '/partials/srp_form_component'

export default {
    title: 'Features/Fleets/CandidateFleetCard',
    component: CandidateFleetCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'One fleet the pilot could have died in, offered by the SRP wizard once a killmail is pasted (`/srp/`, through KillmailBreakdown). The card shows the fleet type as a corner icon, the FC with corporation, the start time and an Objective button that opens the fleet objective. Clicking the card loads the SRP form for that fleet into the wizard.',
                    'The scenarios show a strategic fleet with an objective, a training fleet, a fleet with no objective, a long FC name, and the click that opens the SRP form.',
                ].join('\n\n'),
            },
        },
        htmx: { [SRP_FORM_PARTIAL]: '<p class="srp-form-stub">SRP form for the chosen fleet</p>' },
    },
    argTypes: {
        fleet: { control: 'object', description: 'The candidate fleet: id, type, objective, start time and the FC with corporation.' },
        program: { control: 'inline-radio', options: ['subcapitals', 'dreads', 'carriers'], description: 'The SRP program tab the pilot is on.' },
        external_killmail_link: { control: 'text', description: 'The zKillboard link carried into the SRP form request.' },
    },
    args: {
        fleet: candidate_fleet,
        program: 'subcapitals',
        external_killmail_link: 'https://zkillboard.com/kill/134510244/',
    },
}

export const StrategicWithObjective = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { name: /Fleet 9390/ })).toBeVisible())
        await settle(() => expect(canvas.getByText("Kel'dar Atram")).toBeVisible())
        await expect(canvasElement.querySelector('[data-tippy-content="Strategic fleet"]')).not.toBeNull()
        // The Objective button fades in on card hover (opacity 0 until then), so it is in the DOM but not visible here.
        await expect(canvas.getByRole('button', { name: 'Objective' })).toBeInTheDocument()
        await userEvent.click(canvas.getByRole('button', { name: 'Objective' }))
        await settle(() => expect(canvas.getByText('Amamake gate camp. Bring the Hurricane Brawl fit.')).toBeVisible())
    },
}

export const TrainingFleet = {
    args: { fleet: candidate_fleet_training },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('[data-tippy-content="Training fleet"]')).not.toBeNull()
        await settle(() => expect(within(canvasElement).getByRole('heading', { name: /Fleet 9392/ })).toBeVisible())
    },
}

export const NoObjective = {
    args: { fleet: candidate_fleet_no_objective },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.queryByRole('button', { name: 'Objective' })).toBeNull()
        await settle(() => expect(canvas.getByRole('heading', { name: /Fleet 9394/ })).toBeVisible())
    },
}

export const LongFcName = {
    args: { fleet: candidate_fleet_long_fc },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await settle(() => expect(within(canvasElement).getByText(/Bartholomew-Alexander of the Heimatar Highlands/)).toBeVisible())
    },
}

export const OpensSrpForm = {
    tags: ['browser'],
    // The card's hx-target is the wizard's program pane; htmx refuses to send a request without it.
    decorators: [(Story: () => string) => `<div id="subcapitals-main-content">${Story()}</div>`],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('button', { name: /Kel'dar Atram/ })
        await userEvent.click(card)
        const requests: { url: string }[] = (window as unknown as { __rust_htmx_requests?: { url: string }[] }).__rust_htmx_requests ?? []
        const last = new URL(requests[requests.length - 1].url, 'http://rust.local')
        await expect(last.pathname).toBe(SRP_FORM_PARTIAL)
        await expect(last.searchParams.get('fleet_id')).toBe('9390')
        await expect(last.searchParams.get('program')).toBe('subcapitals')
    },
}
