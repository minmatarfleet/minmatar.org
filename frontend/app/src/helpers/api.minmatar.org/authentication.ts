import type { UserProfile } from '@dtypes/api.minmatar.org'
import { get_error_message } from '@helpers/string'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/users`

export async function get_user_by_id(user_id:number) {
    const headers = {
        'Content-Type': 'application/json'
    }

    const ENDPOINT = `${API_ENDPOINT}/${user_id}/profile`
    
    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })
        
        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as UserProfile;
    } catch (error) {
        throw new Error(`Error fetching user profile: ${error.message}`);
    }
}

export async function get_user_by_name(user_name:string) {
    const headers = {
        'Content-Type': 'application/json'
    }

    const ENDPOINT = `${API_ENDPOINT}?username=${user_name}`
    
    console.log(`Requesting: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers
        })
        
        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `GET ${ENDPOINT}`
            ))
        }

        return await response.json() as UserProfile;
    } catch (error) {
        throw new Error(`Error fetching user profile: ${error.message}`);
    }
}

export async function delete_account(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/delete`
    
    console.log(`Requesting DELETE: ${API_ENDPOINT}/delete`)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'DELETE',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `DELETE ${ENDPOINT}`
            ))
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error deleting account: ${error.message}`);
    }
}

export async function sync_user_with_discord(access_token:string, user_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${user_id}/sync`
    
    console.log(ENDPOINT)

    try {
        const response = await fetch(ENDPOINT, {
            method: 'POST',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(get_error_message(
                response.status,
                `POST ${ENDPOINT}`
            ))
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error syncing user roles with Discord: ${error.message}`);
    }
}