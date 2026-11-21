import { fileURLToPath } from 'node:url'
import remark_gfm from 'remark-gfm'
import type { StorybookConfig } from '@storybook-astro/framework'

// Rust, the Minmatar Fleet component library (my.minmatar.org/rust).
// `server` render mode: the static UI asks a small Node render server
// (storybook-server/, built next to storybook-static/) for each story's HTML,
// so controls re-render real Astro components in production too.
const config: StorybookConfig = {
    stories: [
        '../rust/docs/**/*.mdx',
        '../rust/stories/**/*.stories.ts',
    ],
    addons: [
        {
            name: '@storybook/addon-docs',
            // Tables and task lists in the MDX pages.
            options: { mdxPluginOptions: { mdxCompileOptions: { remarkPlugins: [remark_gfm] } } },
        },
        '@storybook/addon-a11y',
    ],
    framework: {
        name: '@storybook-astro/framework',
        options: {
            renderMode: 'server',
            // Slot HTML from the browser is sanitized before it is rendered.
            // The default allowlist drops form controls and the Alpine, htmx,
            // aria and data attributes our markup is made of; allow those, and
            // still never <script>, on* handlers or javascript: URLs.
            sanitization: {
                sanitizeHtml: {
                    allowedTags: [
                        'a', 'abbr', 'article', 'aside', 'b', 'blockquote', 'br', 'button', 'caption', 'cite', 'code',
                        'col', 'colgroup', 'dd', 'del', 'details', 'dfn', 'div', 'dl', 'dt', 'em', 'fieldset', 'figcaption',
                        'figure', 'footer', 'form', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hr', 'i', 'img', 'input',
                        'ins', 'kbd', 'label', 'legend', 'li', 'main', 'mark', 'meter', 'nav', 'ol', 'optgroup', 'option',
                        'output', 'p', 'picture', 'pre', 'progress', 'q', 's', 'samp', 'section', 'select', 'small',
                        'source', 'span', 'strong', 'sub', 'summary', 'sup', 'table', 'tbody', 'td', 'template', 'textarea',
                        'tfoot', 'th', 'thead', 'time', 'tr', 'u', 'ul', 'var', 'svg', 'path', 'g', 'circle', 'rect',
                        'line', 'polyline', 'polygon', 'use', 'defs', 'title',
                    ],
                    allowedAttributes: {
                        '*': [
                            'class', 'style', 'id', 'title', 'role', 'lang', 'dir', 'hidden', 'tabindex', 'slot',
                            'aria-*', 'data-*', 'x-*', 'hx-*', ':*',
                            'href', 'target', 'rel', 'download', 'src', 'srcset', 'sizes', 'alt', 'width', 'height', 'loading',
                            'name', 'value', 'type', 'checked', 'selected', 'disabled', 'readonly', 'required', 'placeholder',
                            'min', 'max', 'step', 'minlength', 'maxlength', 'pattern', 'multiple', 'for', 'form', 'label',
                            'autocomplete', 'rows', 'cols', 'open', 'datetime', 'colspan', 'rowspan', 'scope', 'start', 'reversed',
                            'viewBox', 'fill', 'stroke', 'stroke-width', 'd', 'cx', 'cy', 'r', 'x', 'y', 'x1', 'y1', 'x2', 'y2',
                            'points', 'xmlns', 'xlink:href', 'transform', 'opacity',
                        ],
                    },
                    allowedSchemes: ['http', 'https', 'mailto', 'data'],
                    allowedSchemesByTag: { img: ['http', 'https', 'data'] },
                    allowVulnerableTags: false,
                    // Keep empty values (<option value="">); the default drops them.
                    nonBooleanAttributes: [],
                    // Alpine's shorthand (@click) can't be expressed as an allowed
                    // attribute name; components use x-on: anyway.
                    parser: { lowerCaseAttributeNames: false },
                },
            },
            server: {
                // Same origin as the UI; edge routes /rust to the rust service.
                serverUrl: process.env.RUST_RENDER_URL ?? '/rust/render-api',
            },
        },
    },
    // Components link site assets by absolute path (/images, /fonts, /js).
    // In production the main site serves those on the same origin, so the
    // build ships without public/ (118 MB); local dev serves it directly.
    staticDirs: [
        // rust/public: tokens.json (the DTCG token export) at /rust/tokens.json.
        '../rust/public',
        // src/assets (planet art), for Foundations › Imagery.
        { from: '../src/assets', to: '/src-assets' },
        ...(process.env.RUST_STATIC_PUBLIC === '0' ? [] : ['../public']),
    ],
    async viteFinal(vite_config, { configType }) {
        // Browser-only alias for the preview bundle (see shims/async_hooks.ts).
        const aliases = Array.isArray(vite_config.resolve?.alias) ? vite_config.resolve.alias : Object.entries(vite_config.resolve?.alias ?? {}).map(([find, replacement]) => ({ find, replacement }))
        vite_config.resolve = {
            ...vite_config.resolve,
            alias: [
                { find: /^node:async_hooks$/, replacement: fileURLToPath(new URL('./shims/async_hooks.ts', import.meta.url)) },
                ...aliases,
            ],
        }
        // The site's public/ (118 MB) stays out of the build; see staticDirs.
        if (configType === 'PRODUCTION') {
            vite_config.publicDir = false
            // The preview bundle follows the imports in .astro frontmatter
            // (gates.ts -> node:crypto, sharp, ...), which only ever run on the
            // render server. Vite stubs Node built-ins for the browser; let the
            // named imports from those stubs resolve to undefined instead of
            // failing the build.
            vite_config.build = {
                ...vite_config.build,
                rollupOptions: { ...vite_config.build?.rollupOptions, shimMissingExports: true },
            }
        }
        return vite_config
    },
    core: {
        disableTelemetry: true,
        disableWhatsNewNotifications: true,
    },
    features: {
        // No "Get started" checklist on a deployed library.
        sidebarOnboardingChecklist: false,
        menuOnboardingChecklist: false,
    },
    docs: {
        defaultName: 'Docs',
    },
}

export default config
