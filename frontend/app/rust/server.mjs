// Serves Rust, the component library, at /rust in production.
//
//   /rust/              the static Storybook UI (storybook-static/)
//   /rust/render-api/*  the @storybook-astro render server (storybook-server/),
//                       which renders each story's Astro component to HTML
//   /rust/health        200 once a real component has rendered
//
// The render server loads components through Vite SSR at runtime, so it only
// accepts the .astro files the Storybook build listed; anything else is a 400.
//
// Run from frontend/app after `npm run rust:build`: `node rust/server.mjs`.
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Hono } from 'hono'
import { serve } from '@hono/node-server'
import { serveStatic } from '@hono/node-server/serve-static'
import { load_display_env } from './display_env.mjs'

const app_dir = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const static_dir = resolve(app_dir, process.env.RUST_STATIC_DIR ?? 'storybook-static')
const server_entry = resolve(app_dir, process.env.RUST_SERVER_DIR ?? 'storybook-server', 'index.js')

const BASE = '/rust'
const RENDER_PREFIX = `${BASE}/render-api`
const PORT = Number(process.env.PORT ?? 6007)
const HOST = process.env.HOST ?? '0.0.0.0'
const MAX_RENDER_BODY = 512 * 1024

// The build writes the story components into the bundle's runtime config;
// the first one warms the renderer up.
export function read_story_components(entry_source) {
    const match = /const runtimeConfig = (\{.*?\});\n/s.exec(entry_source)
    if (!match)
        throw new Error('storybook-server/index.js has no runtimeConfig; rebuild with `npm run rust:build`')
    const config = JSON.parse(match[1])
    return Object.keys(config.componentPathMap ?? {})
}

// What a render request may name: .astro files under the app's component
// folders (stories nest any of them in slots), and nothing else.
export function component_allowlist(root = app_dir) {
    const dirs = [resolve(root, 'src/components'), resolve(root, 'rust/components')]
    return {
        has(id) {
            if (typeof id !== 'string' || !id.endsWith('.astro') || id.includes('\0'))
                return false
            const path = resolve(id)
            return path === id && dirs.some((dir) => path.startsWith(`${dir}/`)) && existsSync(path)
        },
    }
}

// Every component a render request names (the story's, and any nested in
// args or slots) must be one the build listed.
export function find_unlisted_component(value, allowed, depth = 0) {
    if (depth > 32)
        return '(nested too deep)'
    if (Array.isArray(value)) {
        for (const entry of value) {
            const found = find_unlisted_component(entry, allowed, depth + 1)
            if (found)
                return found
        }
        return null
    }
    if (value && typeof value === 'object') {
        for (const [key, entry] of Object.entries(value)) {
            if ((key === 'component' || key === 'moduleId') && typeof entry === 'string') {
                if (!allowed.has(entry.split('?')[0]))
                    return entry
                continue
            }
            const found = find_unlisted_component(entry, allowed, depth + 1)
            if (found)
                return found
        }
    }
    return null
}

export async function create_rust_app({ render_app, allowed_components, static_root = static_dir }) {
    const app = new Hono()
    let healthy = false

    app.get(BASE, (c) => c.redirect(`${BASE}/`, 301))

    app.get(`${BASE}/health`, (c) => healthy ? c.text('OK') : c.text('Starting', 503))

    app.all(`${RENDER_PREFIX}/*`, async (c) => {
        const path = c.req.path.slice(RENDER_PREFIX.length) || '/'
        if (c.req.method === 'POST' && path === '/render') {
            const length = Number(c.req.header('content-length') ?? 0)
            if (length > MAX_RENDER_BODY)
                return c.text('Too large', 413)

            const body = await c.req.text()
            if (body.length > MAX_RENDER_BODY)
                return c.text('Too large', 413)

            let payload
            try {
                payload = JSON.parse(body)
            } catch {
                return c.text('Invalid JSON', 400)
            }
            if (!payload || typeof payload !== 'object' || typeof payload.component !== 'string')
                return c.text('Missing component', 400)

            const unlisted = find_unlisted_component(payload, allowed_components)
            if (unlisted)
                return c.text('Unknown component', 400)

            return render_app.fetch(new Request(new URL('/render', c.req.url), {
                method: 'POST',
                headers: { 'content-type': 'application/json' },
                body,
            }))
        }
        if (c.req.method === 'GET' && path === '/')
            return c.text('OK')
        return c.text('Not found', 404)
    })

    app.use(`${BASE}/*`, async (c, next) => {
        await next()
        // Hashed bundles never change; the HTML and index.json must.
        if (c.res.status === 200) {
            const immutable = /\/(_astro|sb-manager|sb-addons|sb-common-assets)\//.test(c.req.path)
            c.res.headers.set('cache-control', immutable ? 'public, max-age=31536000, immutable' : 'no-cache')
        }
    })

    app.use(`${BASE}/*`, serveStatic({
        root: static_root,
        rewriteRequestPath: (path) => path.slice(BASE.length) || '/',
    }))

    // Production: frontend serves /images, /fonts and /js on the same origin
    // and edge sends only /rust here. Locally and in CI there is no frontend,
    // so RUST_SERVE_PUBLIC=1 serves the app's public/ for everything else.
    if (process.env.RUST_SERVE_PUBLIC === '1')
        app.use('*', serveStatic({ root: resolve(app_dir, 'public') }))

    app.notFound((c) => c.text('Not found', 404))

    return {
        app,
        mark_healthy() { healthy = true },
    }
}

// Renders the first story component once, so /rust/health only turns green
// when Vite SSR, Astro and the component tree all work in this container.
async function warm_up(render_app, story_components) {
    const component = story_components[0]
    if (!component)
        throw new Error('The Storybook build lists no components')
    const response = await render_app.fetch(new Request('http://rust.local/render', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ component, args: {}, slots: {} }),
    }))
    const html = await response.text()
    if (!response.ok || !html.trim())
        throw new Error(`Warm-up render of ${component} failed (${response.status}): ${html.slice(0, 300)}`)
}

async function main() {
    // Date formats the components render with (rust/display.env), over the
    // build's dummy values.
    load_display_env()
    const story_components = read_story_components(readFileSync(server_entry, 'utf8'))
    const allowed_components = component_allowlist()
    // The render bundle resolves the project's snapshot relative to itself and
    // loads Astro/Vite from node_modules, so run it from the app directory.
    process.chdir(app_dir)
    const { default: render_app } = await import(server_entry)

    const { app, mark_healthy } = await create_rust_app({ render_app, allowed_components })

    serve({ fetch: app.fetch, port: PORT, hostname: HOST }, () => {
        console.log(`Rust on http://${HOST}:${PORT}${BASE}/ (${story_components.length} story components)`)
    })

    const started = Date.now()
    await warm_up(render_app, story_components)
    mark_healthy()
    console.log(`Rust render server warm in ${Date.now() - started} ms`)
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    main().catch((error) => {
        console.error(error)
        process.exit(1)
    })
}
