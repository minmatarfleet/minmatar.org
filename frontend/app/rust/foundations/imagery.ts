// Server-side: lists the files in an imagery collection, grouped by picture.
// Namespace imports, read lazily: see tokens.ts.
import * as fs from 'node:fs'
import * as path from 'node:path'
import { IMAGERY_COLLECTIONS, in_collection, variant_key, type ImageryCollection } from './imagery_collections'

const app_root = () => process.env.RUST_APP_ROOT ?? process.cwd()

export interface ImageryItem {
    key:        string;         // corporations/rattini/hero
    url:        string;         // what a page uses (public files), or the src path
    preview:    string;         // URL Storybook can load
    files:      string[];       // every variant's file name
}

function walk(dir: string, base: string, out: string[]) {
    if (!fs.existsSync(dir))
        return out
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const relative = base ? `${base}/${entry.name}` : entry.name
        if (entry.isDirectory()) {
            if (!(base === '' && ['fonts', 'js', 'models', 'resources', 'sounds', 'ccpwgl'].includes(entry.name)))
                walk(path.join(dir, entry.name), relative, out)
        } else {
            out.push(relative)
        }
    }
    return out
}

const cache = new Map<string, string[]>()

export function media_files(root: 'public' | 'src') {
    if (!cache.has(root)) {
        const dir = root === 'public' ? path.join(app_root(), 'public') : path.join(app_root(), 'src/assets')
        cache.set(root, walk(dir, '', []).sort())
    }
    return cache.get(root)!
}

export function collection_by_id(id: string): ImageryCollection {
    const collection = IMAGERY_COLLECTIONS.find((c) => c.id === id)
    if (!collection)
        throw new Error(`Unknown imagery collection: ${id}`)
    return collection
}

const PREFERRED = ['.jpg', '.jpeg', '.png', '.svg', '.webp', '.avif', '.gif', '.webm', '.mp4']

export function list_imagery(collection: ImageryCollection): ImageryItem[] {
    // src/assets files are listed relative to src/, as "assets/..."
    const files = collection.root === 'src'
        ? media_files('src').map((f) => `assets/${f}`)
        : media_files('public')
    const chosen = files.filter((f) => in_collection(collection, f))

    const groups = new Map<string, string[]>()
    for (const file of chosen) {
        const key = variant_key(file)
        groups.set(key, [...(groups.get(key) ?? []), file])
    }

    return [...groups.entries()].map(([key, group]) => {
        const sorted = [...group].sort((a, b) =>
            PREFERRED.indexOf(path.extname(a).toLowerCase()) - PREFERRED.indexOf(path.extname(b).toLowerCase())
            || a.length - b.length)
        const main = sorted[0]
        const url = collection.root === 'src' ? `src/${main}` : `/${main}`
        return {
            key,
            url,
            // src/assets isn't served by URL on the site (pages import it), so
            // Storybook ships it as a static dir (.storybook/main.ts). Relative,
            // so it resolves under /rust/ in production.
            preview: collection.root === 'src' ? main.replace(/^assets\//, 'src-assets/') : `/${main}`,
            files: sorted.map((f) => f.split('/').pop()!),
        }
    })
}
