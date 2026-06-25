import { chapter1 } from './chapter-1'
import { chapter2 } from './chapter-2'
import { chapter3 } from './chapter-3'
import { chapter4 } from './chapter-4'
import type { ChronicleChapter } from './types'

export const ratChronicleChapters: ChronicleChapter[] = [
    chapter1,
    chapter2,
    chapter3,
    chapter4,
]

export function getChronicleChapterById(chapter_id: string): ChronicleChapter | undefined {
    return ratChronicleChapters.find((chapter) => chapter.id === chapter_id)
}

export const defaultChronicleChapterId = ratChronicleChapters[0]?.id ?? 'chapter-1'

export type { ChronicleBlock, ChronicleCharacter, ChronicleCharacterOfTheAge, ChronicleCharactersOfTheAge, ChronicleChapter, ChronicleSection } from './types'
export { formatChronicleDescription, formatChronicleText } from './format-text'
