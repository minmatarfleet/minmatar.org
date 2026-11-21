import { expect, within } from 'storybook/test'
import IntelMembersTable from '@components/blocks/IntelMembersTable.astro'
import { members_crosscheck, ensure_edge_fade } from '../../../fixtures/features/intel-and-combat'

ensure_edge_fade()

export default {
    title: 'Features/Intel and combat/IntelMembersTable',
    component: IntelMembersTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'Our own pilots who keep turning up on another bloc\'s kills, on the Members tab of `/intel/affiliations/`. These are leads for the intel team, not proof, and the hint above the table says so.',
                    'Rows show the pilot (with their main when they are an alt), the bloc, shared kills, months together, the last month seen and the groups they were flying with. The scenarios cover a typical list, an alt whose main differs, very long names and the empty state.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: { members: { control: 'object', description: 'Crosscheck rows from the API.' } },
    args: { members: members_crosscheck },
}

type Ctx = { canvasElement: HTMLElement }

export const Typical = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/These are leads, not proof/)).toBeVisible()
        await expect(canvas.getByRole('columnheader', { name: 'Flying with' })).toBeVisible()
        await expect(canvas.getAllByRole('row')).toHaveLength(members_crosscheck.length + 1)
        const pilot = canvas.getByText('Auga Defender').closest('a') as HTMLElement
        await expect(pilot).toHaveAttribute('href', '/intel/affiliations/character/2119873501/')
        await expect(canvas.getByText('64')).toBeVisible()
        await expect(canvas.getAllByText('2026-10', { selector: '.data-grid-muted' })).toHaveLength(3)
    },
}

export const AltShowsMain = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText("main Kel'dar Atram")).toBeVisible()
        // A pilot whose "main" is itself gets no caption.
        await expect(canvas.queryByText('main Hek Trader Alt')).toBeNull()
    },
}

export const BlocAndGroupLinks = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Goonswarm Federation' })).toHaveAttribute('href', '/intel/affiliations/blocs/11/')
        await expect(canvas.getAllByRole('link', { name: 'Snuffed Out' })[0]).toHaveAttribute('href', '/intel/affiliations/alliance/99010079/')
        await expect(canvasElement.querySelectorAll('.intel-bloc-tag--likely')).toHaveLength(1)
    },
}

export const LongNames = {
    args: { members: [members_crosscheck[3]] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/A Pilot With An Exceedingly Long Name Indeed/)).toBeVisible()
        await expect(canvas.getByText('1280')).toBeVisible()
    },
}

export const Empty = {
    args: { members: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('None of our pilots keeps turning up with another bloc.')).toBeVisible()
        await expect(canvas.queryByRole('table')).toBeNull()
    },
}
