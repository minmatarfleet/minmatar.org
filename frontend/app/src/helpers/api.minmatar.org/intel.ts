import type { IntelPreview, IntelRecent, IntelReport } from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/intel`

export type IntelPasteKind = 'dscan' | 'local'

// A d-scan or Local report shared from /dscan/ or the desktop app's Intel window.
export async function get_intel_report(access_token:string, report_id:string) {
    return await api_request<IntelReport>(`${API_ENDPOINT}/reports/${encodeURIComponent(report_id)}`, {
        token: access_token,
        error: 'Error fetching intel report',
    })
}

// Parse a paste without sharing it: its kind, line count and, for a d-scan, the system it names.
export async function preview_intel_report(access_token:string, text:string, kind?:IntelPasteKind | null) {
    return await api_request<IntelPreview>(`${API_ENDPOINT}/reports/preview`, {
        method: 'POST',
        token: access_token,
        body: { text, kind: kind || null },
    })
}

// Share a paste. A blank system on a d-scan is read from the scan itself.
export async function create_intel_report(access_token:string, text:string, system:string, note:string, kind?:IntelPasteKind | null) {
    return await api_request<IntelReport>(`${API_ENDPOINT}/reports`, {
        method: 'POST',
        token: access_token,
        body: { text, system, note, kind: kind || null },
    })
}

// Shared reports plus capital and Amarr fleet pings from the last 2 hours.
export async function get_recent_intel(access_token:string) {
    return await api_request<IntelRecent>(`${API_ENDPOINT}/recent`, {
        token: access_token,
        error: 'Error fetching recent intel',
    })
}
