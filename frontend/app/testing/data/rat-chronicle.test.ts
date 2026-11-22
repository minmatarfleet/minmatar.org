/**
 * The Rat Chronicle's data: every chapter sits in an era, addresses from before
 * the regrouping still lead somewhere, and every epigraph is a real verse of
 * the Rat Bible (the list the Discord bot quotes from), so the two never drift.
 */
import { describe, expect, test } from 'vitest'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import {
    ratChronicleChapters,
    rat_chronicle_eras,
    legacy_chronicle_chapter_ids,
    resolve_chronicle_chapter_id,
    get_chronicle_eras_with_chapters,
} from '@/data/rat-chronicle'
import type { ChronicleBlock } from '@/data/rat-chronicle'

const RAT_BIBLE_PATH = join(process.cwd(), '..', '..', 'backend', 'reminders', 'messages', 'rat_quotes.py')

/** The verses as `citation - 'text'` strings, read from the backend's list. */
function rat_bible(): Map<string, string> {
    const source = readFileSync(RAT_BIBLE_PATH, 'utf8')
    const verses = new Map<string, string>()
    for (const match of source.matchAll(/^\s*"(.+)",\s*$/gm)) {
        const line = match[1].replace(/\\"/g, '"')
        const split = line.indexOf(" - '")
        if (split === -1) continue
        verses.set(line.slice(0, split).trim(), line.slice(split + 4).replace(/'$/, '').trim())
    }
    return verses
}

const blocks_of = (chapter: (typeof ratChronicleChapters)[number]): ChronicleBlock[] =>
    chapter.sections.flatMap((section) => section.blocks)

describe('the Rat Chronicle', () => {
    test('chapters are numbered in order and have unique addresses', () => {
        expect(ratChronicleChapters.map((chapter) => chapter.number)).toEqual(
            ratChronicleChapters.map((_, index) => index + 1),
        )
        const ids = ratChronicleChapters.map((chapter) => chapter.id)
        expect(new Set(ids).size).toBe(ids.length)
        for (const id of ids) expect(id).toMatch(/^[a-z0-9]+(-[a-z0-9]+)*$/)
    })

    test('every chapter sits in an era, and eras keep their chapters together', () => {
        const era_ids = rat_chronicle_eras.map((era) => era.id)
        for (const chapter of ratChronicleChapters) expect(era_ids).toContain(chapter.era)
        // In reading order the eras never interleave: A A B B, never A B A.
        const order = ratChronicleChapters.map((chapter) => era_ids.indexOf(chapter.era))
        expect(order).toEqual([...order].sort((a, b) => a - b))
        expect(get_chronicle_eras_with_chapters().flatMap((group) => group.chapters)).toEqual(ratChronicleChapters)
    })

    test('every era with chapters has an intro', () => {
        for (const { era } of get_chronicle_eras_with_chapters()) {
            expect(era.intro.length, `${era.name} needs an intro`).toBeGreaterThan(0)
        }
    })

    test('addresses from before the regrouping lead to a current chapter', () => {
        const ids = new Set(ratChronicleChapters.map((chapter) => chapter.id))
        for (let number = 1; number <= 11; number++) {
            const retired = `chapter-${number}`
            expect(resolve_chronicle_chapter_id(retired), `${retired} must still lead somewhere`).toBeDefined()
        }
        for (const [retired, current] of Object.entries(legacy_chronicle_chapter_ids)) {
            expect(ids.has(retired), `${retired} is a current chapter, not a retired address`).toBe(false)
            expect(ids.has(current), `${retired} points at ${current}, which is not a chapter`).toBe(true)
        }
    })

    test('every epigraph is a verse of the Rat Bible, word for word', () => {
        const verses = rat_bible()
        expect(verses.size).toBeGreaterThan(50)
        for (const chapter of ratChronicleChapters) {
            const verse = verses.get(chapter.epigraph.citation)
            expect(verse, `${chapter.title}: "${chapter.epigraph.citation}" is not in the Rat Bible`).toBeDefined()
            expect(chapter.epigraph.text).toBe(verse)
        }
    })

    test('a linked piece leads somewhere', () => {
        for (const chapter of ratChronicleChapters) {
            for (const block of blocks_of(chapter)) {
                const pieces = block.type === 'pieces' ? block.items : block.type === 'quote' && block.source ? [block.source] : []
                for (const piece of pieces) {
                    expect(piece.title.length).toBeGreaterThan(0)
                    expect(piece.post_id !== undefined || Boolean(piece.href), `${chapter.title}: "${piece.title}" has no post and no link`).toBe(true)
                    if (piece.href) expect(piece.href).toMatch(/^https:\/\//)
                }
            }
        }
    })

    test('every chapter has people and at least four sections', () => {
        for (const chapter of ratChronicleChapters) {
            expect(chapter.sections.length, chapter.title).toBeGreaterThanOrEqual(4)
            expect(chapter.charactersOfTheAge?.groups.length ?? 0, `${chapter.title} needs Characters of the Age`).toBeGreaterThan(0)
        }
    })
})
