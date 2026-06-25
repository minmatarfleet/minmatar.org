import type { APIRoute } from 'astro'

import {
    buildUrlsetXml,
    getPublicSitemapPagePaths,
    getSitemapOrigin,
    XML_RESPONSE_HEADERS,
} from '@helpers/sitemap_xml'

export const prerender = false

export const GET: APIRoute = ({ request }) => {
    const origin = getSitemapOrigin(request)
    const entries = getPublicSitemapPagePaths().map((path) => ({
        loc: new URL(path, `${origin}/`).href,
    }))

    return new Response(buildUrlsetXml(entries), { headers: XML_RESPONSE_HEADERS })
}
