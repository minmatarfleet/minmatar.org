import type { APIRoute } from 'astro'

import { get_fittings } from '@helpers/api.minmatar.org/ships'
import {
    buildUrlsetXml,
    getSitemapOrigin,
    XML_RESPONSE_HEADERS,
} from '@helpers/sitemap_xml'

export const prerender = false

export const GET: APIRoute = async ({ request }) => {
    const origin = getSitemapOrigin(request)

    try {
        const fittings = await get_fittings()
        const entries = fittings.map((f) => {
            const loc = `${origin}/ships/fittings/normal/${f.id}`
            const lastmod = f.updated_at
                ? new Date(f.updated_at as unknown as string).toISOString().slice(0, 10)
                : ''
            return { loc, lastmod }
        })

        return new Response(buildUrlsetXml(entries), { headers: XML_RESPONSE_HEADERS })
    } catch {
        return new Response(buildUrlsetXml([]), { headers: XML_RESPONSE_HEADERS })
    }
}
