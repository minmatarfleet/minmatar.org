export type ChronicleCharacterOfTheAge = {
    character_id: number
    character_name: string
    role?: string
    description?: string
}

export type ChronicleCharactersOfTheAge = {
    groups: {
        label: string
        characters: ChronicleCharacterOfTheAge[]
    }[]
}

/** Something on the site or the wider web that a passage draws on: a poster, a paper, a comic, a video, a battle report. */
export type ChroniclePiece = {
    title: string
    /** A post on this site: opens in the content viewer. */
    post_id?: number
    /** The post's slug, for the link to its page. */
    post_slug?: string
    /** An outside link (a public battle report), used when there is no post. */
    href?: string
    /** A short label for what it is: "Frontlines", "Comic", "Battle report". */
    kind?: string
}

export type ChronicleBlock =
    | { type: 'paragraph'; text: string }
    | { type: 'beat'; text: string }
    | {
          type: 'quote'
          text: string
          character_id?: number
          character_name?: string
          attribution?: string
          /** Where the words come from, when the reader can open it. */
          source?: ChroniclePiece
      }
    | { type: 'pieces'; label: string; items: ChroniclePiece[] }

export type ChronicleEraId = 'auga' | 'sosala' | 'vard' | 'amamake'

/** An era is where the alliance lived. Chapters are what happened while living there. */
export type ChronicleEra = {
    id: ChronicleEraId
    name: string
    /** The home, as a pilot would say it. */
    home: string
    date_range: string
    yc: string
    /** A few paragraphs shown before the era's first chapter. */
    intro: ChronicleBlock[]
}

export type ChronicleSection = {
    roman: string
    title: string
    illustration?: {
        src: string
        alt: string
        caption?: string
    }
    blocks: ChronicleBlock[]
}

export type ChronicleChapter = {
    id: string
    era: ChronicleEraId
    number: number
    title: string
    dateRange: string
    yc: string
    realYear: string
    epigraph: {
        citation: string
        text: string
    }
    sections: ChronicleSection[]
    charactersOfTheAge?: ChronicleCharactersOfTheAge
}

/** A chapter as its file writes it. Its number comes from its place in the book. */
export type ChronicleChapterSource = Omit<ChronicleChapter, 'number'>

// Legacy alias for quote attribution portraits
export type ChronicleCharacter = Pick<ChronicleCharacterOfTheAge, 'character_id' | 'character_name'>
