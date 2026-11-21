import { expect, within } from 'storybook/test'
import SystemCard from '@components/blocks/SystemCard.astro'
import { system_cards } from '../../../fixtures/features/campaigns'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/SystemCard',
    component: SystemCard,
    decorators: [(Story: () => string) => `<div style="max-width: 16rem">${Story()}</div>`],
    parameters: {
        docs: {
            description: {
                component: [
                    'A card for one solar system in the theatre: the sun picture, constellation and region, the system name with its security status, the moon count, a progress bar and the distance in light years from home. The slot (right side of the footer) takes extra actions.',
                    'Scenarios: the home system Amamake (shows "Home system" instead of a distance), a neighbouring lowsec system, a far system without moons, a system with no progress, and a finished one.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        system: { control: 'object', description: 'Name, ids, sun type, distance, region, constellation, security, moons and progress (0 to 100).' },
    },
    args: { system: system_cards.amamake },
}

export const HomeSystem = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: /Amamake/ })).toBeVisible()
        await expect(canvas.getByText('Hed ‹ Heimatar')).toBeVisible()
        await expect(canvas.getByText('0.4')).toBeVisible()
        await expect(canvas.getByText('11 moons')).toBeVisible()
        await expect(canvas.getByText('Home system')).toBeVisible()
        await expect(canvasElement.querySelector('progress')).toHaveAttribute('value', '61')
    },
}

export const NeighbouringSystem = {
    args: { system: system_cards.auga },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: /Auga/ })).toBeVisible()
        await expect(canvas.getByText('0.42')).toBeVisible()
        await expect(canvasElement.querySelector('progress')).toHaveAttribute('value', '78')
    },
}

export const FarSystemNoMoons = {
    args: { system: system_cards.huola },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Sasen ‹ The Bleak Lands')).toBeVisible()
        await expect(canvas.getByText('6.18')).toBeVisible()
        await expect(canvas.getByText('0 moons')).toBeVisible()
    },
}

export const NoProgress = {
    args: { system: system_cards.vard },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: /Vard/ })).toBeVisible()
        await expect(canvas.getByText('4 moons')).toBeVisible()
        await expect(canvasElement.querySelector('progress')).not.toBeNull()
    },
}

export const Complete = {
    args: { system: system_cards.lowsec_edge },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: /Old Man Star/ })).toBeVisible()
        await expect(canvasElement.querySelector('progress')).toHaveAttribute('value', '100')
        await expect(canvas.getByText('12.50')).toBeVisible()
    },
}
