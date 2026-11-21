import { expect, within } from 'storybook/test'
import TimezoneTags from '@components/blocks/TimezoneTags.astro'

type Ctx = { canvasElement: HTMLElement }

const tag = (extra = {}) => ({ brackets: ['EUTZ'], secondary: [], weekend: [], source: 'activity', ...extra })

export default {
    title: 'EVE/TimezoneTags',
    component: TimezoneTags,
    parameters: {
        docs: {
            description: {
                component: [
                    'A pilot\'s timezones, rendered the same on every page: one tag per bracket (USTZ, EUTZ, AUTZ, each with a `+` late-night variant). Solid when earned from activity, dashed when only declared, muted when outside the pilot\'s home region or weekend-only.',
                    'No known brackets shows "No TZ yet"; `on_leave` replaces everything with "On Leave" where leave matters. Each tag is focusable and carries a tooltip (`data-tippy-content`) with what it means, its hours in EVE time today and where the data comes from; `show_source` drops that last part. Pass the pilot\'s `timezone` object from the API unchanged.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        timezone: { control: 'object', description: 'API `TimezoneTag`: `{ brackets, secondary, weekend, source: activity | declared }`. Null or empty shows "No TZ yet".' },
        on_leave: { control: 'boolean', description: 'Show "On Leave" instead of the brackets.' },
        show_source: { control: 'boolean', description: 'Append "From when they fly..." / "Declared..." to each tooltip.' },
    },
    args: {
        timezone: tag(),
        on_leave: false,
        show_source: true,
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const eu = within(canvasElement).getByText('EUTZ')
        await expect(eu).toHaveClass('tz-tag')
        await expect(eu).not.toHaveClass('tz-tag--declared')
        await expect(eu).not.toHaveClass('tz-tag--minor')
        await expect(eu).toHaveAttribute('tabindex', '0')
        const tip = eu.getAttribute('data-tippy-content') as string
        await expect(tip).toContain('EU evening')
        await expect(tip).toContain('EVE')
        await expect(tip).toContain('From when they fly, fight and are on comms')
    },
}

export const AllBrackets = {
    args: { timezone: tag({ brackets: ['USTZ', 'USTZ+', 'EUTZ', 'EUTZ+', 'AUTZ', 'AUTZ+'] }) },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        for (const code of ['USTZ', 'USTZ+', 'EUTZ', 'EUTZ+', 'AUTZ', 'AUTZ+'])
            await expect(canvas.getByText(code)).toBeVisible()
        await expect(canvas.getByText('USTZ+').getAttribute('data-tippy-content')).toContain('US late night')
        await expect(canvas.getByText('AUTZ').getAttribute('data-tippy-content')).toContain('AU evening')
    },
}

export const MultipleActive = {
    args: { timezone: tag({ brackets: ['EUTZ', 'EUTZ+'] }) },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('EUTZ')).toBeVisible()
        await expect(canvas.getByText('EUTZ+')).toBeVisible()
        await expect(canvasElement.querySelectorAll('.tz-tag')).toHaveLength(2)
    },
}

export const Declared = {
    args: { timezone: tag({ brackets: ['USTZ'], source: 'declared' }) },
    play: async ({ canvasElement }: Ctx) => {
        const us = within(canvasElement).getByText('USTZ')
        await expect(us).toHaveClass('tz-tag--declared')
        await expect(us.getAttribute('data-tippy-content')).toContain('Declared, not enough activity yet')
    },
}

export const SecondaryAndWeekend = {
    args: { timezone: tag({ brackets: ['EUTZ', 'USTZ', 'AUTZ'], secondary: ['USTZ'], weekend: ['AUTZ'] }) },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('EUTZ')).not.toHaveClass('tz-tag--minor')
        await expect(canvas.getByText('USTZ')).toHaveClass('tz-tag--minor')
        await expect(canvas.getByText('USTZ').getAttribute('data-tippy-content')).toContain('outside their home timezone')
        await expect(canvas.getByText('AUTZ')).toHaveClass('tz-tag--minor')
        await expect(canvas.getByText('AUTZ').getAttribute('data-tippy-content')).toContain('weekends only')
    },
}

export const WithoutSource = {
    args: { show_source: false },
    play: async ({ canvasElement }: Ctx) => {
        const tip = within(canvasElement).getByText('EUTZ').getAttribute('data-tippy-content') as string
        await expect(tip).not.toContain('From when they fly')
        await expect(tip).toContain('EU evening')
    },
}

export const NoTimezoneYet = {
    args: { timezone: null },
    play: async ({ canvasElement }: Ctx) => {
        const none = within(canvasElement).getByText('No TZ yet')
        await expect(none).toHaveClass('tz-tag--none')
        await expect(none).toHaveAttribute('title', 'No activity or declared prime time yet')
    },
}

export const OnLeave = {
    args: { on_leave: true, timezone: tag({ brackets: ['USTZ'] }) },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('On Leave')).toHaveClass('tz-tag--leave')
        await expect(canvas.queryByText('USTZ')).toBeNull()
    },
}
