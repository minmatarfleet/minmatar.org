import type { APIRoute } from 'astro'

import { getSitemapOrigin } from '@helpers/sitemap_xml'

export const prerender = false

export const GET: APIRoute = ({ request }) => {
    const origin = getSitemapOrigin(request)
    const body = `User-agent: *
Allow: /

Sitemap: ${origin}/sitemap.xml
`

    return new Response(body, {
        headers: {
            'Content-Type': 'text/plain; charset=utf-8',
        },
    })
}
