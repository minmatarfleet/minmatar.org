// Read-only source scanning shared by the conventions tests.
//
// Everything here works on text: no Astro compiler, no PostCSS. Each rule
// therefore looks only where its pattern is unambiguous (inside <style>, after
// the frontmatter, inside a class attribute, ...) so a match is a real hit.

import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const APP_ROOT = join(dirname(fileURLToPath(import.meta.url)), '../..')
export const SRC_ROOT = join(APP_ROOT, 'src')

const SOURCE_EXTENSIONS = /\.(astro|ts|js|mjs|scss|css)$/

export interface SourceFile {
    /** Path relative to frontend/app, with forward slashes (`src/components/...`). */
    path: string
    text: string
}

export interface Hit {
    line: number
    snippet: string
}

/** A region of a file, with the offset it starts at so hits report real line numbers. */
export interface Region {
    text: string
    offset: number
}

let cached: SourceFile[] | null = null

export function source_files(): SourceFile[] {
    if (cached) return cached
    const out: SourceFile[] = []
    const walk = (dir: string) => {
        for (const entry of readdirSync(dir, { withFileTypes: true })) {
            const full = join(dir, entry.name)
            if (entry.isDirectory()) walk(full)
            else if (entry.isFile() && SOURCE_EXTENSIONS.test(entry.name))
                out.push({ path: relative(APP_ROOT, full).split(sep).join('/'), text: readFileSync(full, 'utf8') })
        }
    }
    walk(SRC_ROOT)
    cached = out.sort((a, b) => a.path.localeCompare(b.path))
    return cached
}

export function line_at(text: string, index: number): number {
    let line = 1
    for (let i = 0; i < index && i < text.length; i++) if (text.charCodeAt(i) === 10) line++
    return line
}

/** The part of an .astro file after its `---` frontmatter fence (template + client scripts + styles). */
export function astro_template(text: string): Region {
    if (!text.startsWith('---')) return { text, offset: 0 }
    const close = text.indexOf('\n---', 3)
    if (close < 0) return { text, offset: 0 }
    const offset = close + 4
    return { text: text.slice(offset), offset }
}

/** CSS a file contributes: whole .scss/.css files, `<style>` blocks and inline `style="..."` attributes of .astro files. */
export function css_regions(file: SourceFile): Region[] {
    if (/\.(scss|css)$/.test(file.path)) return [{ text: file.text, offset: 0 }]
    if (!file.path.endsWith('.astro')) return []
    const regions: Region[] = []
    for (const m of file.text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)) {
        regions.push({ text: m[1], offset: m.index! + m[0].indexOf('>') + 1 })
    }
    const template = astro_template(file.text)
    for (const m of template.text.matchAll(/\sstyle=(["'])([^"']*)\1/g)) {
        regions.push({ text: m[2], offset: template.offset + m.index! + m[0].indexOf(m[1]) + 1 })
    }
    return regions
}

/** Run a global regex over regions and turn matches into hits with file line numbers. */
export function hits_in(file: SourceFile, regions: Region[], pattern: RegExp, accept: (m: RegExpMatchArray) => boolean = () => true): Hit[] {
    const hits: Hit[] = []
    for (const region of regions) {
        for (const m of region.text.matchAll(pattern)) {
            if (!accept(m)) continue
            const index = region.offset + m.index!
            hits.push({ line: line_at(file.text, index), snippet: m[0].replace(/\s+/g, ' ').trim().slice(0, 80) })
        }
    }
    return hits
}
