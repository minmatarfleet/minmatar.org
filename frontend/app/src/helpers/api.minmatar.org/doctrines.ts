import type { Doctrine } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/doctrines`

export async function get_doctrines() {
    return await api_request<Doctrine[]>(API_ENDPOINT, {
        error: 'Error fetching sigs',
    })
}

/** Every doctrine, retired ones included (the plain list leaves them out). */
export async function get_doctrines_with_retired() {
    return await api_request<Doctrine[]>(`${API_ENDPOINT}?include_retired=true`, {
        error: 'Error fetching doctrines',
    })
}

export async function get_doctrine_by_id(id:number) {
    return await api_request<Doctrine>(`${API_ENDPOINT}/${id}`, {
        error: 'Error fetching sigs',
    })
}
