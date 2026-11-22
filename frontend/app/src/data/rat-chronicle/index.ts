import { slugifySectionId } from '@helpers/pageProgress'
import { amarr_collapses } from './amarr-collapses'
import { dronelands } from './dronelands'
import { letting_them_go } from './letting-them-go'
import { providence_war } from './providence-war'
import { rat_genesis } from './rat-genesis'
import { sosala } from './sosala'
import { the_siege_of_aldodan } from './the-siege-of-aldodan'
import { the_siege_of_auga } from './the-siege-of-auga'
import { the_waifu_wars } from './the-waifu-wars'
import { rat_chronicle_eras } from './eras'
import type { ChronicleChapter, ChronicleChapterSource, ChronicleEra, ChronicleEraId, ChronicleSection } from './types'

/** The book in reading order. A chapter's number is its place here. */
const chapters_in_order: ChronicleChapterSource[] = [
    rat_genesis,
    the_siege_of_auga,
    amarr_collapses,
    providence_war,
    sosala,
    the_siege_of_aldodan,
    the_waifu_wars,
    letting_them_go,
    dronelands,
]

export const ratChronicleChapters: ChronicleChapter[] = chapters_in_order.map((chapter, index) => ({
    ...chapter,
    number: index + 1,
}))

export function getChronicleChapterById(chapter_id: string): ChronicleChapter | undefined {
    return ratChronicleChapters.find((chapter) => chapter.id === chapter_id)
}

/**
 * Addresses the chronicle used before it was regrouped under eras, and the
 * chapter each one's content now lives in. Old links keep working: the page
 * redirects them.
 */
export const legacy_chronicle_chapter_ids: Record<string, string> = {
    'chapter-1': 'rat-genesis',
    'chapter-2': 'the-siege-of-auga',
    'chapter-3': 'amarr-collapses',
    'chapter-4': 'amarr-collapses',
    'chapter-5': 'providence-war',
    'chapter-6': 'sosala',
    'chapter-7': 'sosala',
    'chapter-8': 'the-siege-of-aldodan',
    'chapter-9': 'the-waifu-wars',
    'chapter-10': 'letting-them-go',
    'chapter-11': 'dronelands',
}

/** The current chapter id for an address: itself, or where a retired one moved to. */
export function resolve_chronicle_chapter_id(chapter_id: string): string | undefined {
    if (getChronicleChapterById(chapter_id)) return chapter_id
    const moved = legacy_chronicle_chapter_ids[chapter_id]
    return moved && getChronicleChapterById(moved) ? moved : undefined
}

export { rat_chronicle_eras }

export function get_chronicle_era_by_id(era_id: ChronicleEraId): ChronicleEra {
    return rat_chronicle_eras.find((era) => era.id === era_id) ?? rat_chronicle_eras[0]
}

/** The eras in order, each with its chapters. An era with no chapter yet is left out. */
export function get_chronicle_eras_with_chapters(): { era: ChronicleEra; chapters: ChronicleChapter[] }[] {
    return rat_chronicle_eras
        .map((era) => ({ era, chapters: ratChronicleChapters.filter((chapter) => chapter.era === era.id) }))
        .filter((group) => group.chapters.length > 0)
}

/** True when the chapter is the first of its era, which is where the era's intro is shown. */
export function is_first_chapter_of_era(chapter: ChronicleChapter): boolean {
    return ratChronicleChapters.find((entry) => entry.era === chapter.era)?.id === chapter.id
}

export const defaultChronicleChapterId = ratChronicleChapters[0]?.id ?? 'chapter-1'

/** Stable page-progress id for a chronicle section within a chapter. */
export function chronicleSectionId(chapterId: string, section: ChronicleSection): string {
    const slug = slugifySectionId(section.title) || slugifySectionId(section.roman) || 'section'
    return `${chapterId}-${slug}`
}

/** All trackable story sections across chapters (page progress section list). */
export function getChronicleProgressSections(): { id: string; title: string; chapterId: string }[] {
    const sections: { id: string; title: string; chapterId: string }[] = []
    const seen = new Set<string>()
    for (const chapter of ratChronicleChapters) {
        for (const section of chapter.sections) {
            let id = chronicleSectionId(chapter.id, section)
            if (seen.has(id)) {
                let n = 2
                while (seen.has(`${id}-${n}`)) n += 1
                id = `${id}-${n}`
            }
            seen.add(id)
            sections.push({
                id,
                title: `Ch. ${chapter.number}: ${section.title}`,
                chapterId: chapter.id,
            })
        }
    }
    return sections
}

export type {
    ChronicleBlock,
    ChronicleCharacter,
    ChronicleCharacterOfTheAge,
    ChronicleCharactersOfTheAge,
    ChronicleChapter,
    ChronicleChapterSource,
    ChronicleEra,
    ChronicleEraId,
    ChroniclePiece,
    ChronicleSection,
} from './types'
export { formatChronicleDescription, formatChronicleText } from './format-text'
