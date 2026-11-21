import { expect, within } from 'storybook/test'
import TrainingCharacterRow from '@components/blocks/TrainingCharacterRow.astro'
import type { PlayArgs } from './_helpers'
import {
    training_main, training_alt_many_ready, training_new, training_not_for_fleets, training_long_name,
} from '../../../fixtures/features/ships'

const grid = (Story: () => unknown) =>
    `<div style="--training-columns: minmax(11rem, 15rem) minmax(0, 1fr) 17rem 7rem">${Story()}</div>`

export default {
    title: 'Features/Ships/TrainingCharacterRow',
    component: TrainingCharacterRow,
    decorators: [grid],
    parameters: {
        docs: {
            description: {
                component: 'One character on the Training tab (`/account/`): portrait and SP, the single ship it is training for (opens its plan; a bin stops the goal), the ships it can already fly and an action menu. The row opens the character with htmx. The scenarios show a main in training, an alt with more ready ships than icons, a fresh character, a character marked not for fleets and an over-long name.',
            },
        },
    },
    argTypes: {
        character: { control: 'object', description: 'The `TrainingCharacterSummary`: SP, goals, the goal in training and the ships it is ready in.' },
    },
    args: { character: training_main },
}

export const InTraining = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText("Kel'dar Atram")).toBeVisible()
        await expect(canvas.getByText(/94M SP/)).toBeVisible()
        await expect(canvas.getByText('1 of 2 ready')).toBeVisible()
        await expect(canvas.getByText('Scimitar - Shield Logistics')).toBeVisible()
        await expect(canvas.getByText('3.4 days')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Stop training for Scimitar - Shield Logistics' }).getAttribute('hx-post'))
            .toContain('mode=remove_goal&character_id=2112954532&fitting_id=1207')
        await expect(canvasElement.querySelectorAll('.training-row__ready img')).toHaveLength(5)
    },
}

export const ManyReadyShips = {
    args: { character: training_alt_many_ready },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('✓ Done')).toBeVisible()
        await expect(canvasElement.querySelectorAll('.training-row__ready img')).toHaveLength(6)
        await expect(canvas.getByRole('button', { name: 'All 8 ready ships' })).toHaveTextContent('+2')
    },
}

export const NewCharacter = {
    args: { character: training_new },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Nothing in training')).toBeVisible()
        await expect(canvas.getByText('None yet')).toBeVisible()
        await expect(canvas.getByRole('button', { name: '+ Pick a ship' })).toBeVisible()
    },
}

export const NotForFleets = {
    args: { character: training_not_for_fleets },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Amamake Hauler')).toBeVisible()
        await expect(canvas.getAllByText('Not for fleets').length).toBeGreaterThan(0)
        await expect(canvas.queryByRole('button', { name: '+ Pick a ship' })).toBeNull()
    },
}

export const LongNames = {
    args: { character: training_long_name },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(training_long_name.name)).toBeVisible()
        await expect(canvas.getByText('under 1 h')).toBeVisible()
        await expect(canvas.getByText(/820k SP/)).toBeVisible()
    },
}
