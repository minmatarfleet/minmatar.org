const AMAMAKE_LOCATION_ID = 1022167642188
const R_6KYM_LOCATION_ID = 1051465618860

const lookup_location_name = (location_id:number) => {
    if (location_id === AMAMAKE_LOCATION_ID) return 'Amamake - 5 times nearly AT winners'
    if (location_id === R_6KYM_LOCATION_ID) return 'R-6KYM - DO NOT USE'

    return null
}

export const get_location_video_cover = (location: string | number) => {
    const LOCATION_VIDEO_COVERS = {
        'R-6KYM - DO NOT USE': '/videos/r6-loop.webm',
        'R-6KYM - Casper Anchored It': '/videos/r6-2-loop.webm',
        'Amamake - 5 times nearly AT winners': '/videos/amamake-loop.webm',
        'Jita': '/videos/jita-loop.webm',
        'amarr': '/videos/emperor-loop.webm',
        'amamake': '/videos/amamake-loop.webm',
        'r6': '/videos/r6-loop.webm',
    }

    const location_name = typeof location === 'number' ? lookup_location_name(location) : location

    return location_name ? LOCATION_VIDEO_COVERS[location_name] : null
}

export const get_location_video_cover_thumb = (location: string | number) => {
    const LOCATION_VIDEO_COVERS_THUMBS = {
        'R-6KYM - DO NOT USE': '/images/home-r6-cover.jpg',
        'R-6KYM - Casper Anchored It': '/images/home-r6-2-cover.jpg',
        'Amamake - 5 times nearly AT winners': '/images/home-amamake-cover.jpg',
        'Jita': '/images/home-jita-cover.jpg',
        'amarr': '/images/home-amarr-cover.jpg',
        'amamake': '/images/home-amamake-cover.jpg',
        'r6': '/images/home-r6-cover.jpg',
    }

    const location_name = typeof location === 'number' ? lookup_location_name(location) : location

    return location_name ? LOCATION_VIDEO_COVERS_THUMBS[location_name] : null
}

export const get_location_cover = (location: string | number) => {
    const LOCATION_COVERS = {
        'R-6KYM - DO NOT USE': '/images/home-r6-cover-eve.jpg',
        'R-6KYM - Casper Anchored It': '/images/home-r6-2-cover-eve.jpg',
        'Amamake - 5 times nearly AT winners': '/images/home-amamake-cover-eve.jpg',
        'Jita': '/images/home-jita-cover-eve.jpg',
        'amarr': '/images/home-amarr-cover-eve.jpg',
        'amamake': '/images/home-amamake-cover-eve.jpg',
        'r6': '/images/home-r6-cover-eve.jpg',
    }

    const location_name = typeof location === 'number' ? lookup_location_name(location) : location

    return location_name ? LOCATION_COVERS[location_name] : null
}

export const get_location_cover_990 = (location: string | number) => {
    const LOCATION_COVERS_990 = {
        'R-6KYM - DO NOT USE': '/images/home-r6-cover-eve.jpg',
        'R-6KYM - Casper Anchored It': '/images/home-r6-2-cover-eve.jpg',
        'Amamake - 5 times nearly AT winners': '/images/home-amamake-cover-eve.jpg',
        'Jita': '/images/home-jita-cover-eve.jpg',
        'amarr': '/images/home-amarr-cover-eve.jpg',
        'amamake': '/images/home-amamake-cover-eve.jpg',
        'r6': '/images/home-r6-cover-eve.jpg',
    }

    const location_name = typeof location === 'number' ? lookup_location_name(location) : location

    return location_name ? LOCATION_COVERS_990[location_name] : null
}