import { esi_request } from '@helpers/api.eveonline/client'

export async function get_route(origin:number, destination:number) {
    return await esi_request<number[]>(`/route/${origin}/${destination}/?datasource=tranquility&flag=shortest`, {
        error: 'Error fetching route',
        allow: [404],
        fallback: [],
    })
}
