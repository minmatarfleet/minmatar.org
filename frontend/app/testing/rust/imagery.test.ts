// Every image, background and video the app ships appears in Foundations ›
// Imagery: each file is in a collection, and each collection has a story.
import { describe, expect, test } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { IMAGERY_COLLECTIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, in_collection } from '../../rust/foundations/imagery_collections'
import { media_files, list_imagery } from '../../rust/foundations/imagery'

const APP = resolve(__dirname, '../..')
const stories = readFileSync(resolve(APP, 'rust/stories/foundations/Imagery.stories.ts'), 'utf8')

describe('Rust imagery', () => {
    test('every image and video in public/ and src/assets is in a collection', () => {
        const files = [
            ...media_files('public').map((file) => ({ root: 'public', file })),
            ...media_files('src').map((file) => ({ root: 'src', file: `assets/${file}` })),
        ].filter(({ file }) => IMAGE_EXTENSIONS.test(file) || VIDEO_EXTENSIONS.test(file))
        expect(files.length).toBeGreaterThan(200)

        const homeless = files.filter(({ root, file }) =>
            !IMAGERY_COLLECTIONS.some((c) => c.root === root && in_collection(c, file)))
        expect(homeless.map((f) => `${f.root}/${f.file}`), 'add these to rust/foundations/imagery_collections.ts').toEqual([])
    })

    test('every collection has files and a story', () => {
        for (const collection of IMAGERY_COLLECTIONS) {
            expect(list_imagery(collection).length, collection.id).toBeGreaterThan(0)
            expect(stories, `Imagery.stories.ts needs a story for '${collection.id}'`).toContain(`collection: '${collection.id}'`)
        }
    })
})
