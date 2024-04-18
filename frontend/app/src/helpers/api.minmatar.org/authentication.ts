import type { UserProfile } from '@dtypes/api.minmatar.org'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/users`

export async function get_user_by_id(user_id:number) {
    const headers = {
        'Content-Type': 'application/json'
    }

    console.log(`Requesting: ${API_ENDPOINT}/${user_id}/profile`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${user_id}/profile`, {
            headers: headers
        })
        
        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
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

    console.log(`Requesting: ${API_ENDPOINT}?username=${user_name}`)

    try {
        const response = await fetch(`${API_ENDPOINT}?username=${user_name}`, {
            headers: headers
        })
        
        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
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

    console.log(`Requesting DELETE: ${API_ENDPOINT}/delete`)

    try {
        const response = await fetch(`${API_ENDPOINT}/delete`, {
            method: 'DELETE',
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error deleting account: ${error.message}`);
    }
}