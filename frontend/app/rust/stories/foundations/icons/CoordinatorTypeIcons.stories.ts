import { expect } from 'storybook/test'
import CoordinatorTypeIcons from '@components/blocks/CoordinatorTypeIcons.astro'
import { EVE } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const SHIPS = [
    { eve_type_id: EVE.rifter_type_id, eve_type_name: EVE.rifter_name },
    { eve_type_id: EVE.stabber_type_id, eve_type_name: EVE.stabber_name },
    { eve_type_id: 644, eve_type_name: 'Typhoon' },
]

export default {
    title: 'Foundations/Icons/CoordinatorTypeIcons',
    component: CoordinatorTypeIcons,
    parameters: {
        docs: {
            description: {
                component: 'A row of EVE type icons from the Image Server, for the hulls an industry coordinator builds. Pass `types` (`eve_type_id`, `eve_type_name`); each renders as an `ItemPicture` named by the type.',
            },
        },
    },
    argTypes: {
        types: { control: 'object', description: 'The types to show: `{ eve_type_id, eve_type_name }[]`.' },
        size: { control: false, description: 'Icon size; only 32 is supported.' },
    },
    args: { types: SHIPS, size: 32 },
}

const images = (canvas: HTMLElement) => [...canvas.querySelectorAll('img')]

export const Hulls = {
    play: async ({ canvasElement }: Ctx) => {
        const imgs = images(canvasElement)
        await expect(imgs.length).toBe(3)
        await expect(imgs[0].getAttribute('src')).toContain(`/types/${EVE.rifter_type_id}/`)
    },
}

export const One = {
    args: { types: SHIPS.slice(0, 1) },
    play: async ({ canvasElement }: Ctx) => {
        await expect(images(canvasElement).length).toBe(1)
    },
}

export const None = {
    args: { types: [] },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(images(canvasElement).length).toBe(0)
    },
}
