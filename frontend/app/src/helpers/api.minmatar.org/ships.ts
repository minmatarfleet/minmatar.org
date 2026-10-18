import type { Fitting } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/fittings`

export async function get_fittings() {
    return await api_request<Fitting[]>(API_ENDPOINT, {
        error: 'Error fetching sigs',
    })
}

export async function get_fitting_by_id(id:number) {
    return await api_request<Fitting>(`${API_ENDPOINT}/${id}`, {
        error: 'Error fetching sigs',
    })
}
