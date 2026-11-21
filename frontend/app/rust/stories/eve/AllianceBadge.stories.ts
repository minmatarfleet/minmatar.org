import { expect, within } from 'storybook/test'
import AllianceBadge from '@components/blocks/AllianceBadge.astro'
import { EVE } from '../_controls'

const logo = (size: number) => `https://images.evetech.net/alliances/${EVE.alliance_id}/logo?size=${size}`
const alliance = (extra = {}) => ({ id: EVE.alliance_id, name: EVE.alliance_name, ...extra })

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/AllianceBadge',
    component: AllianceBadge,
    parameters: {
        docs: {
            description: {
                component: [
                    'Alliance logo with its name beside it; the default slot renders under the name at every size (ticker, member count, standing). The alliance twin of `CorporationBadge`, but it is never a link.',
                    'Always pass `alliance.name`: without it the component fetches the name from ESI while rendering, which Storybook cannot do. `size` lives on the `alliance` object (`xs` 24px, `sm` 32px, `lg` 64px).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        alliance: { control: 'object', description: '`{ id, name?, size?: xs | sm | lg }`. The name is looked up from ESI when missing.' },
    },
    args: {
        alliance: alliance(),
        slots: { default: '<small>FL33T</small>' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(EVE.alliance_name)).toBeVisible()
        await expect(canvas.getByText(EVE.alliance_ticker)).toBeVisible()
        const img = canvasElement.querySelector('img') as HTMLElement
        await expect(img).toHaveAttribute('src', logo(32))
        await expect(img).toHaveAttribute('width', '32')
        await expect(img).toHaveAttribute('height', '32')
    },
}

export const ExtraSmall = {
    args: { alliance: alliance({ size: 'xs' }) },
    play: async ({ canvasElement }: Ctx) => {
        const img = canvasElement.querySelector('img') as HTMLElement
        await expect(img).toHaveAttribute('width', '24')
        await expect(img).toHaveAttribute('src', logo(32))
        await expect(within(canvasElement).getByText(EVE.alliance_ticker)).toBeVisible()
    },
}

export const Large = {
    args: { alliance: alliance({ size: 'lg' }), slots: { default: '<small>FL33T · 1,204 pilots</small>' } },
    play: async ({ canvasElement }: Ctx) => {
        const img = canvasElement.querySelector('img') as HTMLElement
        await expect(img).toHaveAttribute('width', '64')
        await expect(img).toHaveAttribute('src', logo(64))
        await expect(within(canvasElement).getByText('FL33T · 1,204 pilots')).toBeVisible()
    },
}

export const NoSlot = {
    args: { slots: {} },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText(EVE.alliance_name)).toBeVisible()
        await expect(within(canvasElement).queryByText(EVE.alliance_ticker)).toBeNull()
    },
}

export const AlliedPartner = {
    args: { alliance: alliance({ id: 99003214, name: 'Brave Collective' }), slots: { default: '<small>Allied</small>' } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Brave Collective')).toBeVisible()
        await expect(canvasElement.querySelector('img')).toHaveAttribute('src', 'https://images.evetech.net/alliances/99003214/logo?size=32')
    },
}
