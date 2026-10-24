import type { IntelReport } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/intel`

// A d-scan or Local report shared from the desktop app's Intel window.
export async function get_intel_report(access_token:string, report_id:string) {
    return await api_request<IntelReport>(`${API_ENDPOINT}/reports/${encodeURIComponent(report_id)}`, {
        token: access_token,
        error: 'Error fetching intel report',
    })
}
