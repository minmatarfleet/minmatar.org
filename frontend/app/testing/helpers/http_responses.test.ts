import { describe, expect, it } from 'vitest'

import {
    HTTP_403_Forbidden,
    HTTP_404_Not_Found,
    status_page_rewrite,
} from '@helpers/http_responses'

const page = (path: string, headers: Record<string, string> = {}) =>
    new Request(`https://my.minmatar.org${path}`, { headers })

describe('HTTP_403_Forbidden', () => {
    it('is a bare 403 with no client-side page swap', async () => {
        const response = HTTP_403_Forbidden()

        expect(response.status).toBe(403)
        expect(await response.text()).toBe('')
    })
})

describe('status_page_rewrite', () => {
    it('renders the 403 page for page requests', () => {
        expect(status_page_rewrite(page('/fleets/1/'), HTTP_403_Forbidden())).toBe('/403')
    })

    it('leaves htmx partials and API routes with the bare status', () => {
        expect(status_page_rewrite(page('/fleets/1/', { 'HX-Request': 'true' }), HTTP_403_Forbidden())).toBeNull()
        expect(status_page_rewrite(page('/partials/fleet_detail_component/'), HTTP_403_Forbidden())).toBeNull()
        expect(status_page_rewrite(page('/api/industry/planner/plans'), HTTP_403_Forbidden())).toBeNull()
    })

    it('ignores other responses', () => {
        expect(status_page_rewrite(page('/x/'), HTTP_404_Not_Found())).toBeNull()
        expect(status_page_rewrite(page('/x/'), new Response('no', { status: 403 }))).toBeNull()
        expect(status_page_rewrite(page('/x/'), new Response('ok'))).toBeNull()
    })
})
