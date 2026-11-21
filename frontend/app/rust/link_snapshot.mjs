// Post-build step for `npm run rust:build`.
//
// The render server (storybook-server/index.js) renders from a snapshot of the
// project in storybook-server/project, but @storybook-astro only copies the
// story components into it, not what their frontmatter imports (@helpers,
// @json, src/data, styles). Rust always runs next to the full app (the `rust`
// image ships it), so point the snapshot at the app itself, and drop the copy
// of public/ the build makes: the render server never serves files.
import { existsSync, mkdirSync, readdirSync, rmSync, symlinkSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const app = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const server = join(app, 'storybook-server')

if (!existsSync(join(server, 'index.js'))) {
    console.error('storybook-server/index.js is missing; run storybook build first')
    process.exit(1)
}

const KEEP = new Set(['index.js', 'index.js.map', 'project'])
for (const entry of readdirSync(server))
    if (!KEEP.has(entry))
        rmSync(join(server, entry), { recursive: true, force: true })

// A directory of links, not one link to the app: the app contains
// storybook-server/, and a link back to it would loop for any file walker.
const LINKED = ['src', 'rust', 'node_modules', 'astro.config.mjs', 'package.json', 'tsconfig.json', 'svelte.config.js', '.env.BUILDONLY']
const project = join(server, 'project')
rmSync(project, { recursive: true, force: true })
mkdirSync(project)
for (const entry of LINKED)
    if (existsSync(join(app, entry)))
        symlinkSync(join('..', '..', entry), join(project, entry))

console.log(`storybook-server/project links ${LINKED.join(', ')} from frontend/app`)
