import { expect, within } from 'storybook/test'
import CorporationDepartures from '@components/blocks/CorporationDepartures.astro'
import {
    departures_answered,
    departures_open,
    departures_with_alts,
    flagged_joins,
} from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/CorporationDepartures',
    component: CorporationDepartures,
    parameters: {
        docs: {
            description: {
                component: [
                    'The CEO-only Departures tab on a tracked corporation\'s page (#3198, `docs/exits/exit-flow-design.md` section 04): who left, when, where they went (Exit, Alliance move or NPC corp), and the CEO\'s answer.',
                    'Filter chips switch between rows needing an answer, answered rows and all, with counts. Ticking rows and saving one answer covers them all; alts on one account that left together are one row. Choosing "Can\'t rejoin" asks for confirmation and requires a note. The partial `corporation_departures_component` fetches and posts; the block only renders.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        groups: { control: 'object', description: 'Every confirmed departure; the counts and the filter come from it.' },
        corporation_name: { control: 'text' },
        state: { control: 'inline-radio', options: ['open', 'answered', 'all'] },
        partial_url: { control: 'text' },
        flash: { control: 'object' },
        flagged_joins: { control: 'object', description: 'Pilots marked can\'t rejoin who joined: keep with a note, or remove in game.' },
    },
    args: {
        groups: departures_open,
        corporation_name: 'Example Corp',
        state: 'open',
        partial_url: '/partials/corporation_departures_component/?corporation_id=98000001',
    },
}

export const Open = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: '4 pilots left Example Corp' })).toBeVisible()
        await expect(canvas.getByText('Arkan Veld')).toBeVisible()
        await expect(canvas.getByText('Mira Stonehand')).toBeVisible()
        // Answered rows are under the Answered filter, not here.
        await expect(canvas.queryByText('Kesh Varo')).toBeNull()
        await expect(canvas.getByText('2 of 4 answered')).toBeVisible()
        await expect(canvas.getAllByText('NPC corp').length).toBeGreaterThan(0)
        await expect(canvas.getByText(/Who sees your answers/)).toBeVisible()
        await expect(canvas.getByRole('checkbox', { name: 'Select Arkan Veld' })).toBeInTheDocument()
        await expect(canvas.getByRole('button', { name: 'Save' })).toBeVisible()
    },
}

export const Answered = {
    args: { state: 'answered' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Kesh Varo')).toBeVisible()
        await expect(canvas.getByText('Alliance move')).toBeVisible()
        await expect(canvasElement.querySelector('.is-flagged')?.textContent).toContain("Can't rejoin")
        await expect(canvas.getByText('“Awoxed a corp Orca”')).toBeVisible()
    },
}

export const AllAnswered = {
    args: { groups: departures_answered },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Nothing to answer')).toBeVisible()
        await expect(canvas.getByText('2 of 2 answered')).toBeVisible()
        await expect(canvas.queryByRole('button', { name: 'Save' })).toBeNull()
    },
}

export const WithAlts = {
    args: { groups: departures_with_alts, corporation_name: 'Example Corp' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: '1 pilot left Example Corp' })).toBeVisible()
        await expect(canvas.getByText('+ 2 alts')).toBeVisible()
        await expect(canvas.getByText(/one answer covers the account/)).toBeVisible()
        const box = canvas.getByRole('checkbox', { name: 'Select Toren Ashblade' }) as HTMLInputElement
        await expect(box.value).toBe('106,107,108')
    },
}

export const NoDepartures = {
    args: { groups: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No departures yet')).toBeVisible()
    },
}

export const WithFlaggedJoin = {
    name: 'A flagged pilot joined',
    args: { flagged_joins },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Flagged pilots who joined' })).toBeVisible()
        await expect(canvas.getByText('Dren Halvik', { selector: 'strong' })).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Keep them' })).toBeVisible()
        await expect(canvas.getByRole('button', { name: "I'll remove them" })).toBeVisible()
        await expect(canvas.getByText(/Removal expected/)).toBeVisible()
    },
}
