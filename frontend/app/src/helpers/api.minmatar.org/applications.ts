import type { CorporationApplication, CorporationApplicationDetails } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/applications/corporations`

export async function get_corporation_applications(access_token:string, corporation_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${corporation_id}/applications`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as CorporationApplication[];
    } catch (error) {
        throw new Error(`Error fetching corporation applications: ${error.message}`);
    }
}

export async function create_corporation_application(access_token:string, corporation_id:number, description:string) {
    const data = JSON.stringify({
        'description': description,
    });

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${corporation_id}/applications`
    
    console.log(`Requesting: POST ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            body: data,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
                response.status,
                `POST: ${ENDPOINT}`
            ));
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
    
    const ENDPOINT = `${API_ENDPOINT}/${corporation_id}/applications/${application_id}`

    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ));
        }

        return await response.json() as CorporationApplicationDetails;
    } catch (error) {
        throw new Error(`Error fetching corporation application: ${error.message}`);
    }
}

export async function accept_corporation_applications(access_token:string, corporation_id:number, application_id) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${corporation_id}/applications/${application_id}/accept`
    
    console.log(`Requesting: POST ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ));
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

    const ENDPOINT = `${API_ENDPOINT}/${corporation_id}/applications/${application_id}/reject`
    
    console.log(`Requesting: POST ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: 'POST'
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(await get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ));
        }

        return await response.json() as CorporationApplication[];
    } catch (error) {
        throw new Error(`Error rejecting corporation application: ${error.message}`);
    }
}