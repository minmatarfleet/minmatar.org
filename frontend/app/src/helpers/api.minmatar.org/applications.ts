import type { CorporationApplication } from '@dtypes/api.minmatar.org'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/applications/corporations`

export async function get_corporation_applications(access_token:string, corporation_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${corporation_id}/applications`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${corporation_id}/applications`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CorporationApplication[];
    } catch (error) {
        throw new Error(`Error fetching corporation applications: ${error.message}`);
    }
}

export async function create_corporation_application(access_token:string, corporation_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting POST: ${API_ENDPOINT}/${corporation_id}/applications`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${corporation_id}/applications`, {
            headers: headers,
            method: 'POST'
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CorporationApplication;
    } catch (error) {
        throw new Error(`Error creating corporation application: ${error.message}`);
    }
}

export async function get_corporation_applications_by_id(access_token:string, corporation_id:number, application_id) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${corporation_id}/applications/${application_id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${corporation_id}/applications/${application_id}`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CorporationApplication[];
    } catch (error) {
        throw new Error(`Error fetching corporation application: ${error.message}`);
    }
}

export async function accept_corporation_applications(access_token:string, corporation_id:number, application_id) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${corporation_id}/applications/${application_id}/accept`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${corporation_id}/applications/${application_id}/accept`, {
            headers: headers,
            method: 'POST'
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CorporationApplication[];
    } catch (error) {
        throw new Error(`Error accepting corporation application: ${error.message}`);
    }
}

export async function reject_corporation_applications(access_token:string, corporation_id:number, application_id) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${corporation_id}/applications/${application_id}/reject`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${corporation_id}/applications/${application_id}/reject`, {
            headers: headers,
            method: 'POST'
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as CorporationApplication[];
    } catch (error) {
        throw new Error(`Error rejecting corporation application: ${error.message}`);
    }
}