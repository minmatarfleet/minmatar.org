import { expect, within } from 'storybook/test'
import FreightRouteRow from '@components/blocks/market_settings/FreightRouteRow.astro'
import { public_freight_route, shadow_freight_route } from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Industry/FreightRouteRow',
    component: FreightRouteRow,
    decorators: [(story: () => string) => `<table class="[ manage-table ]">${story()}</table>`],
    parameters: {
        docs: {
            description: {
                component: 'A freight route summary with its editor expanded. The shadow label and switch reflect the saved contract visibility.',
            },
        },
    },
    args: { route: public_freight_route, open: true, detail: {} },
}

export const PublicRoute = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Jita → Amamake')).toBeVisible()
        await expect(canvas.getByRole('switch', { name: 'Shadow contracts' })).not.toBeChecked()
        await expect(canvas.getAllByText('Shadow contracts')).toHaveLength(1)
    },
}

export const ShadowRoute = {
    args: { route: shadow_freight_route },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const visibility = canvas.getByRole('switch', { name: 'Shadow contracts' })
        await expect(visibility).toBeChecked()
        await expect(visibility).toHaveAccessibleDescription(/signed-in alliance members/i)
        await expect(canvas.getAllByText('Shadow contracts')).toHaveLength(2)
        await expect(canvas.getByRole('button', { name: 'Save' })).toBeEnabled()
    },
}
