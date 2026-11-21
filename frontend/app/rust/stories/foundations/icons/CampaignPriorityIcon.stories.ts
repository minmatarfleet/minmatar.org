import { expect } from 'storybook/test'
import CampaignPriorityIcon from '@components/blocks/CampaignPriorityIcon.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Foundations/Icons/CampaignPriorityIcon',
    component: CampaignPriorityIcon,
    parameters: {
        docs: {
            description: {
                component: 'The three-tier priority chevron for campaign systems: three stacked chevrons in red for high, two in orange for medium, one in green for low, with the priority as its accessible label. Use it wherever a campaign objective shows its priority.',
            },
        },
    },
    argTypes: {
        priority: { control: 'inline-radio', options: ['high', 'medium', 'low'], description: 'Campaign system priority.' },
    },
    args: { priority: 'high' },
}

const chevrons = (canvas: HTMLElement) => canvas.querySelectorAll('svg path, svg polyline').length

export const High = {
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('svg')).not.toBeNull()
        await expect(chevrons(canvasElement)).toBeGreaterThanOrEqual(3)
    },
}

export const Medium = {
    args: { priority: 'medium' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(chevrons(canvasElement)).toBeGreaterThanOrEqual(2)
    },
}

export const Low = {
    args: { priority: 'low' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(chevrons(canvasElement)).toBeGreaterThanOrEqual(1)
    },
}
