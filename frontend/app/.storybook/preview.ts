import '@fontsource-variable/montserrat'
import '@fontsource/qahiri'
import 'tippy.js/dist/tippy.css'
import 'medium-zoom/dist/style.css'
import '../src/styles/base.scss'
import '../src/styles/tailwind.css'
import './rust.scss'
import { bind_swap_init } from '@helpers/swap_init'
import { bind_partial_styles } from '@helpers/htmx_partial_styles'

import { cancel_pending_htmx_mocks, install_htmx_mocks, type HtmxMocks } from './htmx_mocks'
import { rust_theme } from './theme'

declare global {
    interface Window {
        htmx?: { process: (el: Element) => void };
        Alpine?: { initTree: (el: Element) => void };
    }
}

install_htmx_mocks(window)
// The site's own swap wiring (Alpine on swapped content, one tippy delegate)
// and partial-CSS handling, exactly as FooterScripts and HeadScripts bind them.
bind_swap_init(window as any)
bind_partial_styles(window as any)

// Storybook swaps each story's HTML into its root; htmx only scans the page
// on load, so process the new story roots (never content htmx swapped itself,
// or hx-trigger="load" would fire twice).
const STORY_ROOTS = '#storybook-root, .docs-story [id^="story--"], .sb-story'
new MutationObserver((records) => {
    for (const record of records) {
        const parent = record.target as Element
        if (!(parent instanceof Element) || !parent.matches(STORY_ROOTS))
            continue
        record.addedNodes.forEach((node) => {
            if (node instanceof Element)
                window.htmx?.process(node)
        })
    }
}).observe(document.documentElement, { childList: true, subtree: true })

const preview = {
    parameters: {
        layout: 'padded',
        docs: {
            theme: rust_theme,
        },
        backgrounds: {
            options: {
                site: { name: 'Site', value: '#121212' },
                component: { name: 'Component', value: 'rgb(25, 25, 25)' },
            },
        },
        controls: {
            expanded: true,
            sort: 'requiredFirst',
        },
        a11y: {
            // Reported in the Accessibility panel and by rust/browser_test.mjs
            // (--a11y-strict fails on them). The existing components have
            // violations to fix first; switch to 'error' once they are clean.
            test: 'todo',
        },
        options: {
            storySort: {
                order: [
                    'Rust', ['Introduction', 'Architecture', 'Writing stories'],
                    'Foundations', ['Colors', 'Colours not yet tokens', 'Typography', 'Spacing and layout', 'Motion, layers and glass', 'Themes', 'Icons', 'Logos'],
                    'Layout',
                    'Components', ['Forms', 'Feedback', 'Data display', 'Navigation', 'Overlays'],
                    'EVE', ['SDE'],
                    'Page',
                    'Features', ['Fleets', 'Campaigns', 'Industry', 'Ships', 'Corporations and tribes', 'Intel and combat', 'Content'],
                ],
            },
        },
    },
    // The accessibility modes the site toggles on <body> (Foundations/Themes).
    globalTypes: {
        theme: {
            description: 'Colour mode',
            toolbar: {
                title: 'Theme',
                icon: 'contrast',
                items: [
                    { value: 'default', title: 'Default' },
                    { value: 'color-blind', title: 'Colour-blind mode' },
                ],
                dynamicTitle: true,
            },
        },
        ui_scale: {
            description: 'UI scaling (accessibility options)',
            toolbar: {
                title: 'UI scale',
                icon: 'zoom',
                items: ['80', '90', '100', '120'].map((value) => ({ value, title: `${value}%` })),
                dynamicTitle: true,
            },
        },
    },
    initialGlobals: {
        backgrounds: { value: 'site' },
        theme: 'default',
        ui_scale: '100',
    },
    beforeEach({ parameters, globals }: { parameters: { htmx?: HtmxMocks }; globals: Record<string, string> }) {
        cancel_pending_htmx_mocks(window)
        window.__rust_htmx_mocks = parameters.htmx ?? {}
        window.__rust_htmx_requests = []

        document.body.classList.toggle('color-blind-mode', globals.theme === 'color-blind')
        for (const scale of ['80', '90', '120'])
            document.body.classList.toggle(`ui-scaling-${scale}`, globals.ui_scale === scale)
    },
    tags: ['autodocs'],
}

export default preview
