import { api_status_is } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/tech`

export async function ping() {
    return await api_status_is(`${API_ENDPOINT}/ping`, {
        error: 'Error on ping',
    })
}
