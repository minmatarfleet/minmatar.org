import { expect, within } from 'storybook/test'
import IntelAffiliationRow from '@components/blocks/IntelAffiliationRow.astro'
import {
    affiliation_suggested, affiliation_confirmed, affiliation_rejected, affiliation_ended,
    affiliation_manual, affiliation_pilot_associate, affiliation_long_name,
} from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/IntelAffiliationRow',
    component: IntelAffiliationRow,
    parameters: {
        docs: {
            description: {
                component: [
                    'One row of the affiliation database: subject, bloc, relation, status, confidence, the plain-English evidence line, and a Confirm / Reject form. Appears on `/intel/affiliations/` (Review tab), on every bloc page and on entity profile pages.',
                    'The scenarios cover each status (suggested, confirmed, rejected, ended), hand-made rows with no evidence, a pilot associate, and the form feedback line. The form posts to `intel_affiliation_decision_component`, which answers with this row again.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        affiliation: { control: 'object', description: 'The API row: entity, bloc, relation, status, source, confidence, evidence.' },
        show_entity: { control: 'boolean', description: 'Leave the subject out (on its own profile page).' },
        show_bloc: { control: 'boolean', description: 'Leave the bloc out (on the bloc page).' },
        status_message: { control: 'object', description: 'Success or error line after a decision.' },
    },
    args: { affiliation: affiliation_suggested, show_entity: true, show_bloc: true, status_message: null },
}

type Ctx = { canvasElement: HTMLElement }

export const SuggestedInferred = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Snuffed Out' })).toHaveAttribute('href', '/intel/affiliations/alliance/99010079/')
        await expect(canvas.getByText('Goonswarm Federation')).toBeVisible()
        await expect(canvas.getByText('Pet', { selector: '.intel-affiliation__relation' })).toBeVisible()
        await expect(canvas.getByText('82% confidence')).toBeVisible()
        await expect(canvas.getByText(/Goonswarm Federation on 20% of its kills/)).toBeVisible()
        await expect(canvas.getByText(/429 kills together/)).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Confirm' })).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Reject' })).toBeVisible()
        await expect(canvasElement.querySelector('article')).toHaveClass('intel-affiliation--suggested')
    },
}

export const Confirmed = {
    args: { affiliation: affiliation_confirmed },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Confirmed', { selector: '.intel-affiliation__status' })).toBeVisible()
        await expect(canvas.getByText(/Confirmed by Bear That Cares on 2026-11-03/)).toBeVisible()
        // A confirmed row saves a relation change instead of confirming again.
        await expect(canvas.getByRole('button', { name: 'Save' })).toBeVisible()
        await expect(canvas.getByRole('combobox', { name: 'Relation' }).querySelector('option[selected]')).toHaveValue('ally')
    },
}

export const Rejected = {
    args: { affiliation: affiliation_rejected },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('article')).toHaveClass('intel-affiliation--rejected')
        await expect(canvas.getByText(/22 shot at each other/)).toBeVisible()
        await expect(canvas.getByText('They shoot each other every week.')).toBeVisible()
        // A rejection sticks: no second Reject button.
        await expect(canvas.queryByRole('button', { name: 'Reject' })).toBeNull()
    },
}

export const Ended = {
    args: { affiliation: affiliation_ended },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Ended', { selector: '.intel-affiliation__status' })).toBeVisible()
        await expect(canvasElement.querySelector('article')).toHaveClass('intel-affiliation--ended')
        await expect(canvas.getByText(/2025-01 – 2026-04/)).toBeVisible()
    },
}

export const ManualRowNoEvidence = {
    args: { affiliation: affiliation_manual },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Added by hand')).toBeVisible()
        await expect(canvas.getByText('Seen in their Discord.')).toBeVisible()
        await expect(canvas.queryByText(/confidence/)).toBeNull()
    },
}

export const PilotAssociateLikelyBloc = {
    args: { affiliation: affiliation_pilot_associate },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Dead Drop Scout' })).toHaveAttribute('href', '/intel/affiliations/character/2119873420/')
        await expect(canvas.getByText(/on 57 kills with Snuffed Out across 5 months/)).toBeVisible()
        await expect(canvas.getByText('flies from an NPC corporation', { exact: false })).toBeVisible()
        await expect(canvasElement.querySelector('.intel-bloc-tag--likely')).not.toBeNull()
    },
}

export const OnBlocPageNoBloc = {
    args: { show_bloc: false },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Snuffed Out' })).toBeVisible()
        await expect(canvas.queryByRole('link', { name: /Goonswarm/ })).toBeNull()
        await expect(canvasElement.querySelector('.intel-affiliation__arrow')).toBeNull()
    },
}

export const DecisionFeedback = {
    args: { affiliation: affiliation_confirmed, status_message: { kind: 'error', text: 'Not saved: the bloc was merged.' } },
    play: async ({ canvasElement }: Ctx) => {
        const status = within(canvasElement).getByRole('status')
        await expect(status).toHaveTextContent('Not saved: the bloc was merged.')
        await expect(status).toHaveClass('intel-affiliation__message--error')
    },
}

export const LongEntityName = {
    args: { affiliation: affiliation_long_name },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText(/The Imperial Fedo Navy Reserve Auxiliary/)).toBeVisible()
    },
}
