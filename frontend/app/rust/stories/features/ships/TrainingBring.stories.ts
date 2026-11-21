import { expect, within } from 'storybook/test'
import TrainingBring from '@components/blocks/TrainingBring.astro'
import { register_edge_fade, type PlayArgs } from './_helpers'
import { training_bring_one_seat, training_bring_multi_seat, training_bring_empty } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/TrainingBring',
    component: TrainingBring,
    decorators: [(Story: () => unknown) => { if (typeof window !== 'undefined') register_edge_fade(); return Story() }],
    parameters: {
        docs: {
            description: {
                component: '"What you can bring" on the Training tab (`/account/`): one row per doctrine, one cell per role (frontline, tackle, logistics...). A pilot with two or more seats (accounts, or characters on none) sees how many ships they can bring at once as ×N; a pilot with one sees a tick. A role nobody flies yet shows how long until someone will. Cells open the role by account. On phones the table becomes collapsible lists. The scenarios show one seat, several seats with a long wait, and no doctrines.',
            },
        },
    },
    argTypes: {
        bring: { control: 'object', description: 'The `TrainingBring` payload: seats, role columns and a doctrine row per strategic and other doctrine, each with its cells.' },
    },
    args: { bring: training_bring_multi_seat },
}

export const OneSeat = {
    args: { bring: training_bring_one_seat },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        const table = canvas.getByRole('table')
        await expect(Array.from(table.querySelectorAll('thead th')).map(h => h.textContent)).toEqual(['Doctrine', 'Frontline', 'Tackle', 'Logistics'])
        await expect(canvas.getAllByText('✓').length).toBeGreaterThanOrEqual(3)
        await expect(canvas.getAllByText('Ready in 2 of 3 roles').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('Every role ready').length).toBeGreaterThan(0)
        // 3.4 days until Logistics is ready.
        await expect(canvas.getAllByText('3.4 days').length).toBeGreaterThan(0)
    },
}

export const MultipleSeats = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByText('Strategic').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('Other doctrines').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('×3').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('You can bring 3 at once').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('None of your characters yet').length).toBeGreaterThan(0)
        // Unfilled roles show their wait (0.4 days is 10 h), or "Nobody close".
        await expect(canvas.getAllByText('10 h').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('Nobody close').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('41 days').length).toBeGreaterThan(0)
    },
}

export const CellsOpenTheRole = {
    play: async ({ canvasElement }: PlayArgs) => {
        const cell = within(canvasElement).getAllByRole('button', { name: '3 of your characters can fly Hurricane Autocannon Fleet Frontline at the same time' })[0]
        await expect(cell.getAttribute('x-on:click')).toContain('/partials/training_doctrine_component/?doctrine_id=31&column=Frontline')
    },
}

export const NoDoctrines = {
    args: { bring: training_bring_empty },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText('No doctrines yet')).toBeVisible()
        await expect(within(canvasElement).queryByRole('table')).toBeNull()
    },
}
