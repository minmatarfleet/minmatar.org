import { expect, within } from 'storybook/test'
import MoonMetenoxKills from '@components/blocks/universe/MoonMetenoxKills.astro'
import { metenox_kills_two } from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/MoonMetenoxKills',
    component: MoonMetenoxKills,
    parameters: {
        docs: {
            description: {
                component: [
                    "The Metenox tab of a moon row on Universe › Moons (`/universe/#moons`): every Metenox Moon Drill killed at that moon, newest first, read hourly from zKillboard. Each row has the EVE time, the owner's corporation and alliance, the alliance (else corporation) that did the most damage with its pilot count, and a zKillboard link. The newest owner is the best guess at who holds the moon.",
                    'The scenarios show a moon that changed hands twice, one kill by a corporation with no alliance, and a moon with no kills.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        kills: { control: 'object', description: 'Metenox kills at the moon (`MoonMetenoxKill[]`), newest first.' },
    },
    args: { kills: metenox_kills_two },
}

type Ctx = { canvasElement: HTMLElement }

export const ChangedHands = {
    name: 'Changed hands twice',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('table', { name: 'Metenox' })).toBeInTheDocument()
        await expect(canvasElement.querySelectorAll('tbody tr')).toHaveLength(2)
        await expect(canvas.getByText('Holder Corp B')).toBeInTheDocument()
        await expect(canvas.getByText('34 pilots')).toBeInTheDocument()
        const links = canvas.getAllByRole('link', { name: 'zKill' })
        await expect(links[0]).toHaveAttribute('href', 'https://zkillboard.com/kill/131204118/')
    },
}

export const NoAlliance = {
    name: 'Owner with no alliance',
    args: { kills: metenox_kills_two.slice(1) },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Holder Corp A')).toBeInTheDocument()
        await expect(canvas.getByText('No alliance')).toBeInTheDocument()
    },
}

export const NoKills = {
    name: 'No kills',
    args: { kills: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No Metenox killed here')).toBeInTheDocument()
        await expect(canvasElement.querySelector('table')).toBeNull()
    },
}
