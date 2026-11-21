import { expect, within } from 'storybook/test'
import UsefulForShips from '@components/blocks/UsefulForShips.astro'
import type { PlayArgs } from './_helpers'
import { useful_for_few, useful_for_many } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/UsefulForShips',
    component: UsefulForShips,
    parameters: {
        docs: {
            description: {
                component: 'A row of round hull icons showing which fittings a skill or module is useful for, with a "+N" chip for the rest (its tooltip lists their names). It is used in the training plan dialog and skill rows on the Training tab (`/account/`). The scenarios show two ships, thirteen ships cut at the default of ten, a custom limit and size, and no ships (nothing drawn).',
            },
        },
    },
    argTypes: {
        ships: { control: 'object', description: 'The ships to show: `{ ship_id, fitting_name }`. The tooltip is the fitting name.' },
        max: { control: { type: 'number', min: 1 }, description: 'How many icons to draw before collapsing the rest into "+N".' },
        size: { control: { type: 'number', min: 16 }, description: 'Icon diameter in px.' },
    },
    args: { ships: useful_for_few, max: 10, size: 24 },
}

const icons = (canvasElement: HTMLElement) => canvasElement.querySelectorAll('.useful-for-ships__icon')

export const FewShips = {
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(icons(canvasElement)).toHaveLength(2)
        await expect(canvasElement.querySelector('.useful-for-ships__more')).toBeNull()
        await expect(within(canvasElement).getByAltText('Rifter - Amamake Brawler')).toBeVisible()
    },
}

export const ManyShipsCollapsed = {
    args: { ships: useful_for_many },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(icons(canvasElement)).toHaveLength(10)
        const more = canvasElement.querySelector('.useful-for-ships__more') as HTMLElement
        await expect(more).toHaveTextContent('+3')
        await expect(more.getAttribute('data-tippy-content')).toBe('Rupture - Armor Brawler, Tempest - Long Range, Typhoon - Mid-range Battleship')
    },
}

export const CustomLimitAndSize = {
    args: { ships: useful_for_many, max: 4, size: 40 },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(icons(canvasElement)).toHaveLength(4)
        await expect(canvasElement.querySelector('.useful-for-ships__more')).toHaveTextContent('+9')
    },
}

export const NoShips = {
    parameters: { rust: { allow_empty: true } },
    args: { ships: [] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(icons(canvasElement)).toHaveLength(0)
        await expect(canvasElement.querySelector('.useful-for-ships')).toBeNull()
    },
}
