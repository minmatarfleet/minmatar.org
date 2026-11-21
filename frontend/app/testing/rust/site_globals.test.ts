// The Storybook preview loads copies of FooterScripts' inline Alpine globals
// (.storybook/site_globals.js). Keep them identical to the site's.
import { expect, test } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const APP = resolve(__dirname, '../..')

test('site_globals.js matches the inline globals in FooterScripts.astro', () => {
    const footer = readFileSync(resolve(APP, 'src/components/partials/FooterScripts.astro'), 'utf8')
    const copy = readFileSync(resolve(APP, '.storybook/site_globals.js'), 'utf8')
    const blocks = [...footer.matchAll(/<script is:inline>\n([\s\S]*?)<\/script>/g)].map((m) => m[1])
        .filter((block) => block.includes('function neocom_clock') || block.includes('window.edge_fade'))
    expect(blocks.length).toBe(2)
    for (const block of blocks)
        expect(copy, 'run the extraction again: FooterScripts changed').toContain(block)
})
