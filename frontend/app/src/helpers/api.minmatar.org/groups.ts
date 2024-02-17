import type { Group, GroupRequest } from '@dtypes/api.minmatar.org'

const API_ENDPOINT =  `${import.meta.env.API_URL}/api/groups`

export async function get_groups(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/`)

    try {
        const response = await fetch(`${API_ENDPOINT}/`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as Group[];
    } catch (error) {
        throw new Error(`Error fetching groups: ${error.message}`);
    }
}

export async function get_available_groups(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/available`)

    try {
        const response = await fetch(`${API_ENDPOINT}/available`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as Group[];
    } catch (error) {
        throw new Error(`Error fetching available groups: ${error.message}`);
    }
}

export async function get_group_by_id(access_token:string, id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${id}`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as Group;
    } catch (error) {
        throw new Error(`Error fetching available groups: ${error.message}`);
    }
}

export async function get_group_requests(access_token:string, group_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${group_id}/requests`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${group_id}/requests`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as GroupRequest[];
    } catch (error) {
        throw new Error(`Error fetching group requests: ${error.message}`);
    }
}

export async function create_group_request(access_token:string, group_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${group_id}/requests`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${group_id}/requests`, {
            method: 'POST',
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as GroupRequest;
    } catch (error) {
        throw new Error(`Error creating group request: ${error.message}`);
    }
}

export async function approve_group_request(access_token:string, group_id:number, request_id: number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${group_id}/requests/${request_id}/approve`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${group_id}/requests/${request_id}/approve`, {
            method: 'POST',
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as GroupRequest;
    } catch (error) {
        throw new Error(`Error approving group request: ${error.message}`);
    }
}

export async function deny_group_request(access_token:string, group_id:number, request_id: number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${group_id}/requests/${request_id}/deny`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${group_id}/requests/${request_id}/deny`, {
            method: 'POST',
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as GroupRequest;
    } catch (error) {
        throw new Error(`Error denying group request: ${error.message}`);
    }
}

export async function get_group_users(access_token:string, group_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${group_id}/users`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${group_id}/users`, {
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as string[];
    } catch (error) {
        throw new Error(`Error getting group users: ${error.message}`);
    }
}

export async function remove_user_from_group(access_token:string, group_id:number, user_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    console.log(`Requesting: ${API_ENDPOINT}/${group_id}/users/${user_id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${group_id}/users/${user_id}`, {
            method: 'DELETE',
            headers: headers
        })

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error removing user from group: ${error.message}`);
    }
}