import { slugifySectionId } from '@helpers/pageProgress'
import { chapter1 } from './chapter-1'
import { chapter2 } from './chapter-2'
import { chapter3 } from './chapter-3'
import { chapter4 } from './chapter-4'
import { chapter5 } from './chapter-5'
import { chapter6 } from './chapter-6'
import { chapter7 } from './chapter-7'
import { chapter8 } from './chapter-8'
import { chapter9 } from './chapter-9'
import { chapter10 } from './chapter-10'
import { chapter11 } from './chapter-11'
import type { ChronicleChapter, ChronicleSection } from './types'

export const ratChronicleChapters: ChronicleChapter[] = [
    chapter1,
    chapter2,
    chapter3,
    chapter4,
    chapter5,
    chapter6,
    chapter7,
    chapter8,
    chapter9,
    chapter10,
    chapter11,
]

export function getChronicleChapterById(chapter_id: string): ChronicleChapter | undefined {
    return ratChronicleChapters.find((chapter) => chapter.id === chapter_id)
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

export type { ChronicleBlock, ChronicleCharacter, ChronicleCharacterOfTheAge, ChronicleCharactersOfTheAge, ChronicleChapter, ChronicleSection } from './types'
export { formatChronicleDescription, formatChronicleText } from './format-text'
