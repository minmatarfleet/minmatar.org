import { expect, within, userEvent } from 'storybook/test'
import TrainingOverview from '@components/blocks/TrainingOverview.astro'
import { register_edge_fade, type PlayArgs } from './_helpers'
import {
    training_overview_typical, training_overview_single_account, training_overview_empty,
} from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/TrainingOverview',
    component: TrainingOverview,
    decorators: [(Story: () => unknown) => { if (typeof window !== 'undefined') register_edge_fade(); return Story() }],
    parameters: {
        docs: {
            description: {
                component: 'The Training tab, `/account/` (Training): "What you can bring" across doctrines and roles, then every character grouped by account, each with the ship it trains for and the ships it can fly. Characters not yet on an account sit in a collapsible group. The scenarios show two accounts plus unplaced characters, a pilot with one seat and no accounts, and a pilot with no characters.',
            },
        },
    },
    argTypes: {
        overview: { control: 'object', description: 'The `TrainingOverview` payload: accounts with characters, unplaced characters and the `bring` matrix.' },
    },
    args: { overview: training_overview_typical },
}

export const TwoAccountsAndUnplaced = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'What you can bring' })).toBeVisible()
        await expect(canvas.getByRole('heading', { name: 'Your characters' })).toBeVisible()
        await expect(canvas.getByRole('heading', { name: 'Account 1' })).toBeVisible()
        await expect(canvas.getByRole('heading', { name: 'Account 2' })).toBeVisible()
        await expect(canvas.getByRole('heading', { name: /Not on an account yet · 1 characters/ })).toBeVisible()
        await expect(canvas.getAllByRole('button', { name: 'Move a character' })).toHaveLength(2)
        await expect(canvasElement.querySelectorAll('.training-row')).toHaveLength(5)
    },
}

export const UnplacedGroupToggles = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        const toggle = canvas.getByRole('button', { name: 'Show' })
        await expect(toggle).toHaveAttribute('aria-expanded', 'false')
        await userEvent.click(toggle)
        await expect(canvas.getByRole('button', { name: 'Hide' })).toHaveAttribute('aria-expanded', 'true')
    },
}

export const SingleSeatNoAccounts = {
    args: { overview: training_overview_single_account },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('.training-row')).toHaveLength(1)
        await expect(canvas.queryByRole('heading', { name: /Account/ })).toBeNull()
        await expect(canvas.getAllByText('✓').length).toBeGreaterThan(0)
    },
}

export const NoCharacters = {
    args: { overview: training_overview_empty },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No characters yet')).toBeVisible()
        await expect(canvas.getByText('Add a character on the Characters tab to see what it can fly.')).toBeVisible()
        await expect(canvas.getByText('No doctrines yet')).toBeVisible()
    },
}
