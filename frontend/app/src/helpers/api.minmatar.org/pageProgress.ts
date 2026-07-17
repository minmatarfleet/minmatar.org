import { parse_response_error } from '@helpers/string'
import type {
    PageProgressStatusResponse,
    MarkSectionReadResponse,
    PageAckResponse,
    PageProgressImportPage,
    PageProgressImportResponse,
} from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/page-progress`

function page_url(page_key: string, suffix = ''): string {
    const trimmed = page_key.replace(/^\/+|\/+$/g, '')
    return `${API_ENDPOINT}/${trimmed}${suffix}`
}

export async function get_page_progress(
    access_token: string,
    page_key: string,
    options: { version?: string; sections?: string[] } = {},
): Promise<PageProgressStatusResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const params = new URLSearchParams()
    if (options.version) params.set('version', options.version)
    if (options.sections?.length) params.set('sections', options.sections.join(','))

    const query = params.toString()
    const ENDPOINT = `${page_url(page_key)}${query ? `?${query}` : ''}`
    const METHOD = 'GET'

    const response = await fetch(ENDPOINT, { headers, method: METHOD })
    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as PageProgressStatusResponse
}

export async function post_section_read(
    access_token: string,
    page_key: string,
    section_id: string,
    payload: { version: string; page_title?: string; section_total?: number },
): Promise<MarkSectionReadResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = page_url(page_key, `/sections/${encodeURIComponent(section_id)}/read`)
    const METHOD = 'POST'

    const response = await fetch(ENDPOINT, {
        headers,
        method: METHOD,
        body: JSON.stringify({
            version: payload.version,
            page_title: payload.page_title ?? '',
            section_total: payload.section_total ?? 0,
        }),
    })

    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as MarkSectionReadResponse
}

export async function post_page_ack(
    access_token: string,
    page_key: string,
    payload: { version: string; sections: string[]; page_title?: string },
): Promise<PageAckResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = page_url(page_key, '/ack')
    const METHOD = 'POST'

    const response = await fetch(ENDPOINT, {
        headers,
        method: METHOD,
        body: JSON.stringify({
            version: payload.version,
            sections: payload.sections,
            page_title: payload.page_title ?? '',
        }),
    })

    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as PageAckResponse
}

/** Merge anonymous/local progress into the authenticated user's server records. */
export async function post_page_progress_import(
    access_token: string,
    pages: PageProgressImportPage[],
): Promise<PageProgressImportResponse> {
    const headers = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${access_token}`,
    }

    const ENDPOINT = `${API_ENDPOINT}/import`
    const METHOD = 'POST'

    const response = await fetch(ENDPOINT, {
        headers,
        method: METHOD,
        body: JSON.stringify({ pages }),
    })

    if (!response.ok)
        throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`), {
            cause: response.status,
        })

    return (await response.json()) as PageProgressImportResponse
}
