import type { APIRoute } from 'astro'

import {
    buildSitemapIndexXml,
    getSitemapOrigin,
    XML_RESPONSE_HEADERS,
} from '@helpers/sitemap_xml'

export const prerender = false

export const GET: APIRoute = ({ request }) => {
    const origin = getSitemapOrigin(request)
    const today = new Date().toISOString().slice(0, 10)

    const body = buildSitemapIndexXml([
        { loc: `${origin}/sitemap-pages.xml`, lastmod: today },
        { loc: `${origin}/sitemap-fittings.xml`, lastmod: today },
    ])

    return new Response(body, { headers: XML_RESPONSE_HEADERS })
}
