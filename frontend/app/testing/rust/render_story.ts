// Renders a Rust (Storybook) story the way the Storybook render server does,
// with Astro's Container API, so every story is also a vitest case.
//
// A story's args are props, except `slots` ({ name: content }) and the
// per-slot `slot-<name>` controls. Slot content is an HTML string, an array of
// contents, a component, or a configured component: { component, props?, slots? }
// (the shape @storybook-astro's renderer takes).
import { experimental_AstroContainer as AstroContainer } from 'astro/container'

type Container = Awaited<ReturnType<typeof AstroContainer.create>>

export type SlotContent = string | number | SlotContent[] | ((...args: unknown[]) => unknown) | {
    component: unknown;
    props?: Record<string, unknown>;
    slots?: Record<string, SlotContent>;
}

let container_promise: Promise<Container> | null = null

export function get_container() {
    container_promise ??= AstroContainer.create()
    return container_promise
}

export function split_args(args: Record<string, unknown>) {
    const props: Record<string, unknown> = {}
    const slots: Record<string, SlotContent> = { ...((args.slots as Record<string, SlotContent>) ?? {}) }

    for (const [key, value] of Object.entries(args)) {
        if (key === 'slots')
            continue
        if (key.startsWith('slot-')) {
            if (value !== undefined)
                slots[key.slice(5)] = value as SlotContent
            continue
        }
        props[key] = value
    }

    return { props, slots }
}

async function render_slot(content: SlotContent): Promise<string> {
    if (content === null || content === undefined)
        return ''
    if (typeof content === 'string' || typeof content === 'number')
        return String(content)
    if (Array.isArray(content))
        return (await Promise.all(content.map(render_slot))).join('')
    if (typeof content === 'function')
        return render_component(content, {}, {})

    return render_component(content.component, content.props ?? {}, content.slots ?? {})
}

export async function render_component(
    component: unknown,
    props: Record<string, unknown>,
    slots: Record<string, SlotContent>,
) {
    const container = await get_container()
    const rendered_slots: Record<string, string> = {}
    for (const [name, content] of Object.entries(slots))
        rendered_slots[name] = await render_slot(content)

    return container.renderToString(component as any, {
        props,
        slots: rendered_slots,
    })
}

export async function render_story(component: unknown, args: Record<string, unknown>) {
    const { props, slots } = split_args(args)
    return render_component(component, props, slots)
}

// Storybook decorators, the two forms @storybook-astro supports:
//   a bare Astro component, which wraps the story as its default slot;
//   a function `(Story, context) => string` that drops `${Story()}` into HTML.
export async function apply_decorators(html: string, decorators: unknown[], context: Record<string, unknown>) {
    // The first decorator in the list is the innermost, as in Storybook
    // (story decorators before component decorators).
    for (const decorator of decorators) {
        if (typeof decorator === 'function' && (decorator as any).isAstroComponentFactory) {
            html = await render_component(decorator, {}, { default: html })
            continue
        }
        if (typeof decorator === 'function') {
            const token = `@@rust-story-${Math.random().toString(36).slice(2)}@@`
            const result = (decorator as (story: () => unknown, ctx: unknown) => unknown)(() => ({ toString: () => token }), context)
            if (typeof result === 'string') {
                html = result.split(token).join(html)
                continue
            }
            if (result && typeof result === 'object' && 'component' in (result as any)) {
                const { component, props = {}, slots = {} } = result as any
                html = await render_component(component, props, { ...slots, default: html })
                continue
            }
            // Returned the story untouched (a side-effect decorator).
            continue
        }
    }
    return html
}
