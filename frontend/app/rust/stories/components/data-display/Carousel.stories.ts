import { expect, within } from 'storybook/test'
import Carousel from '@components/blocks/Carousel.astro'
import { radio_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const slide = (title: string) => `<div class="swiper-slide" style="width: min(100%, 16rem)"><div class="card border component" style="padding: var(--space-m)">${title}</div></div>`
const SLIDES = ['Rifter', 'Wolf', 'Jaguar', 'Slasher', 'Breacher', 'Burst'].map(slide).join('')

/** The Swiper options Alpine will start the carousel with. */
const swiper_options = (canvasElement: HTMLElement) => {
    const x_data = canvasElement.querySelector('[x-data]')?.getAttribute('x-data') ?? ''
    return JSON.parse(x_data.match(/\.\.\.(\{.*\}),\n/)?.[1] ?? 'null')
}

export default {
    title: 'Components/Data display/Carousel',
    component: Carousel,
    parameters: {
        docs: {
            description: {
                component: [
                    'A Swiper carousel with the prev/next markup and styling the site\'s reels share: a relatively positioned wrapper, the `.swiper` with its `.swiper-wrapper` track, optional pagination bullets, and the arrows as siblings of the `.swiper`, so they appear once Swiper has initialised and hide when there is nothing further to scroll to. Callers put their slides in the default slot, each wrapped in `<div class="swiper-slide">`.',
                    'It uses the global `Swiper` from HeadScripts, started after the 100 ms the reels have always waited for hidden or swapped-in markup, and destroyed when the carousel is removed. `slides_per_view` and `breakpoints` (min viewport width in px, with the slide count from there up) set how many slides show. `nav_tone` picks the arrow colour (the reels split between `highlight` and `fleet-yellow`); `nav_offset` sets how far the arrows sit from the edge. The arrows are labelled and keyboard-reachable, and hidden below the `lg` breakpoint by default, where touch swipes.',
                    'Swiper is a CDN script: in vitest the stories assert the markup and the options handed to Swiper; Storybook runs the real carousel.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        slides_per_view: { control: 'text', description: 'Slides visible at once: a number, or `auto` to size by the slide width.' },
        breakpoints: { control: 'object', description: 'Min viewport widths in px: `{ 650: { slides_per_view: 2, space_between: 10 } }`.' },
        space_between: { control: 'number', description: 'Gap between slides in px.' },
        loop: { control: 'boolean', description: 'Wrap from the last slide to the first.' },
        autoplay_ms: { control: 'number', description: 'Advance on its own every this many ms; 0 is off.' },
        navigation: { control: 'boolean', description: 'Show the prev/next arrows.' },
        pagination: { control: 'boolean', description: 'Show clickable pagination bullets under the track.' },
        nav_tone: radio_control(['highlight', 'fleet-yellow'] as const, 'Arrow colour.'),
        nav_offset: { control: 'text', description: 'Arrow distance from the edge as a CSS length; negative sits outside the reel.' },
        hide_nav_on_mobile: { control: 'boolean', description: 'Hide the arrows below the `lg` breakpoint.' },
        align: radio_control(['start', 'center', 'end', 'stretch'] as const, 'Vertical alignment of slides in the track.'),
        initial_slide: { control: 'number', description: 'Index of the slide shown first.' },
        direction: radio_control(['horizontal', 'vertical'] as const, 'Slides stack vertically; give the `.swiper` a height.'),
        effect: radio_control(['slide', 'fade'] as const, '`fade` cross-fades between slides.'),
        mousewheel: { control: 'object', description: '`true`, or `{ forceToAxis: true }`, to scroll with the wheel.' },
        rewind: { control: 'boolean', description: 'Jump from the last slide back to the first.' },
        nested: { control: 'boolean', description: 'Inside another Swiper: touches belong to the innermost.' },
        allow_touch_move: { control: 'boolean', description: 'Off, the reel moves only by the arrows, bullets and `go_slide`.' },
        hash_navigation: { control: 'boolean', description: 'Keep the slide in the URL hash (`data-hash` on each slide).' },
        breakpoints_base: radio_control(['window', 'container'] as const, 'Measure `breakpoints` against the viewport or the carousel itself.'),
        selector: { control: 'text', description: 'The caller\'s own `.swiper` (a selector for it or an ancestor). Only the track and bullets render inside it.' },
        prev_el: { control: 'text', description: 'Selector of an arrow the caller placed (with `selector`).' },
        next_el: { control: 'text', description: 'Selector of an arrow the caller placed (with `selector`).' },
        pagination_class: { control: 'text', description: 'Class for the bullets container.' },
        control_id: { control: 'text', description: 'Names the carousel for the `carousel:go` / `carousel:next` window events.' },
    },
    args: {
        slides_per_view: 'auto',
        space_between: 10,
        navigation: true,
        pagination: false,
        nav_tone: 'highlight',
        nav_offset: '-46px',
        hide_nav_on_mobile: true,
        align: 'start',
        slots: { default: SLIDES },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByText(/Rifter|Wolf|Jaguar|Slasher|Breacher|Burst/)).toHaveLength(6)
        const swiper = canvasElement.querySelector('.swiper') as HTMLElement
        await expect(swiper.querySelector('.swiper-wrapper')).not.toBeNull()
        const prev = canvas.getByRole('button', { name: 'Previous slide', hidden: true })
        const next = canvas.getByRole('button', { name: 'Next slide', hidden: true })
        await expect(prev).toHaveClass('swiper-button-prev')
        await expect(next).toHaveClass('swiper-button-next')
        // The arrows are siblings of .swiper: the initialised-state CSS depends on it.
        await expect(prev.previousElementSibling).toBe(swiper)
        await expect(next.previousElementSibling).toBe(prev)
        await expect(prev).toHaveAttribute('tabindex', '0')
        await expect(swiper.querySelector('.swiper-pagination')).toBeNull()
        await expect(canvasElement.firstElementChild).toHaveClass('carousel--highlight')
    },
}

export const YellowArrows = {
    args: { nav_tone: 'fleet-yellow', nav_offset: 'var(--space-l)' },
    play: async ({ canvasElement }: Ctx) => {
        const root = canvasElement.firstElementChild as HTMLElement
        await expect(root).toHaveClass('carousel--fleet-yellow')
        await expect(root.getAttribute('style')).toContain('--carousel-nav-offset: var(--space-l)')
    },
}

export const WithPagination = {
    args: { pagination: true, slides_per_view: 1, space_between: 0 },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('.swiper > .swiper-pagination')).not.toBeNull()
        const options = swiper_options(canvasElement)
        await expect(options.pagination).toEqual({ clickable: true, dynamicBullets: true })
        await expect(options.slidesPerView).toBe(1)
    },
}

export const ResponsiveBreakpoints = {
    args: {
        slides_per_view: 1,
        space_between: 8,
        breakpoints: { 650: { slides_per_view: 2, space_between: 12 }, 1000: { slides_per_view: 3 } },
    },
    play: async ({ canvasElement }: Ctx) => {
        const options = swiper_options(canvasElement)
        await expect(options.breakpoints).toEqual({
            650: { slidesPerView: 2, spaceBetween: 12 },
            1000: { slidesPerView: 3 },
        })
        await expect(options.spaceBetween).toBe(8)
    },
}

export const AutoplayAndLoop = {
    args: { loop: true, autoplay_ms: 4000, slides_per_view: 1 },
    play: async ({ canvasElement }: Ctx) => {
        const options = swiper_options(canvasElement)
        await expect(options.loop).toBe(true)
        await expect(options.autoplay).toEqual({ delay: 4000 })
    },
}

export const WithoutNavigation = {
    args: { navigation: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).queryByRole('button', { name: 'Next slide', hidden: true })).toBeNull()
        await expect(canvasElement.querySelector('.swiper-button-prev')).toBeNull()
        await expect(canvasElement.querySelector('.swiper')?.getAttribute('x-data') ?? '').not.toContain('swiper-button-next')
    },
}

export const ArrowsOnMobile = {
    name: 'Arrows kept below the lg breakpoint',
    args: { hide_nav_on_mobile: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('.swiper-button-prev')?.className).not.toContain('hidden!')
    },
}

export const VerticalFeed = {
    name: 'Vertical with mousewheel',
    args: { direction: 'vertical', mousewheel: { forceToAxis: true }, slides_per_view: 1, navigation: false, pagination: true },
    play: async ({ canvasElement }: Ctx) => {
        const options = swiper_options(canvasElement)
        await expect(options.direction).toBe('vertical')
        await expect(options.mousewheel).toEqual({ forceToAxis: true })
    },
}

export const FadeWithoutTouch = {
    name: 'Fade, no touch, rewind',
    args: { effect: 'fade', allow_touch_move: false, rewind: true, nested: true, slides_per_view: 1 },
    play: async ({ canvasElement }: Ctx) => {
        const options = swiper_options(canvasElement)
        await expect(options.effect).toBe('fade')
        await expect(options.fadeEffect).toEqual({ crossFade: true })
        await expect(options.allowTouchMove).toBe(false)
        await expect(options.rewind).toBe(true)
        await expect(options.nested).toBe(true)
    },
}

export const OwnReel = {
    name: 'Caller keeps its .swiper (selector)',
    args: { selector: '#my-reel', navigation: false, hash_navigation: true, breakpoints_base: 'container', prev_el: '#my-reel-prev', next_el: '#my-reel-next' },
    play: async ({ canvasElement }: Ctx) => {
        // Only the track renders: no .swiper, wrapper or arrows of its own.
        await expect(canvasElement.querySelector('.swiper')).toBeNull()
        await expect(canvasElement.querySelector('.swiper-wrapper')).not.toBeNull()
        await expect(canvasElement.querySelector('.swiper-button-prev')).toBeNull()
        const x_data = canvasElement.querySelector('[x-data]')?.getAttribute('x-data') ?? ''
        await expect(x_data).toContain('#my-reel')
        await expect(x_data).toContain('#my-reel-next')
        const options = swiper_options(canvasElement)
        await expect(options.hashNavigation).toBe(true)
        await expect(options.breakpointsBase).toBe('container')
    },
}

export const External = {
    name: 'Controlled from outside',
    args: { control_id: 'tour', slides_per_view: 1 },
    play: async ({ canvasElement }: Ctx) => {
        const root = canvasElement.querySelector('.swiper')!
        const x_data = root.getAttribute('x-data') ?? ''
        // Slides call go_slide / next_slide; window events carousel:go and carousel:next do the same.
        await expect(x_data).toContain('go_slide(index)')
        await expect(x_data).toContain('next_slide()')
        await expect(root.getAttribute('x-on:carousel:go.window')).toContain('"tour"')
        await expect(root.getAttribute('x-on:carousel:next.window')).toContain('next_slide()')
    },
}

export const ArrowColour = {
    name: 'Arrows and bullets take the nav_tone colour',
    tags: ['browser'], // reads the computed colour Swiper paints with
    args: { nav_tone: 'fleet-yellow', pagination: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const root = canvasElement.firstElementChild as HTMLElement
        await expect(getComputedStyle(root).getPropertyValue('--swiper-theme-color').trim()).not.toBe('')
        const yellow = getComputedStyle(document.documentElement).getPropertyValue('--fleet-yellow').trim()
        const next = root.querySelector('.swiper-button-next') as HTMLElement
        const probe = document.createElement('span')
        probe.style.color = yellow
        document.body.append(probe)
        await expect(getComputedStyle(next).color).toBe(getComputedStyle(probe).color)
        probe.remove()
    },
}
