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

export type ChronicleBlock =
    | { type: 'paragraph'; text: string }
    | { type: 'beat'; text: string }
    | { type: 'quote'; text: string; character_id?: number; character_name?: string; attribution?: string }

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

// Legacy alias for quote attribution portraits
export type ChronicleCharacter = Pick<ChronicleCharacterOfTheAge, 'character_id' | 'character_name'>
