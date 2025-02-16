import { parse_response_error } from '@helpers/string'
import type { NotificationSubscription, NotificationSubscriptionsFull } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/subscriptions`

export async function get_user_subscriptions(access_token:string, user_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}?user_id=${user_id}`
    const METHOD = 'GET'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD,
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))
        
        return await response.json() as NotificationSubscription[]
    } catch (error) {
        throw new Error(`Error fetching user notifications: ${error.message}`);
    }
}

export async function create_subscription(access_token:string, user_id:number, subscription:string) {
    const data = JSON.stringify({
        user_id: user_id,
        subscription: subscription,
    })

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/`
    const METHOD = 'POST'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)
    console.log(data)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD,
            body: data,
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))
                
        return await response.json() as NotificationSubscription
    } catch (error) {
        throw new Error(`Error creating subscription: ${error.message}`);
    }
}

export async function remove_subscription(access_token:string, subscription_id:number) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = `${API_ENDPOINT}/${subscription_id}`
    const METHOD = 'DELETE'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD,
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))
        
        return subscription_id
    } catch (error) {
        throw new Error(`Error deleting subscription: ${error.message}`);
    }
}

export async function get_all_subscriptions(access_token:string) {
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${access_token}`
    }

    const ENDPOINT = API_ENDPOINT
    const METHOD = 'GET'

    console.log(`Requesting ${METHOD}: ${ENDPOINT}`)

    try {
        const response = await fetch(ENDPOINT, {
            headers: headers,
            method: METHOD,
        })

        // console.log(response)

        if (!response.ok)
            throw new Error(await parse_response_error(response, `${METHOD} ${ENDPOINT}`))
        
        return await response.json() as NotificationSubscriptionsFull[]
    } catch (error) {
        throw new Error(`Error fetching user notifications: ${error.message}`);
    }
}