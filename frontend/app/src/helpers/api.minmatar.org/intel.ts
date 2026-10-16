import type { IntelReport } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/intel`

// A d-scan or Local report shared from the desktop app's Intel window.
export async function get_intel_report(access_token:string, report_id:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/reports/${encodeURIComponent(report_id)}`

    console.log(`Requesting GET: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'GET'
        })

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ), {
                cause: response.status
            })
        }

        return await response.json() as IntelReport;
    } catch (error) {
        throw new Error(`Error fetching intel report: ${error.message}`, { cause: error.cause });
    }
}
