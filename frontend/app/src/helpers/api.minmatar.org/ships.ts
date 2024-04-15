import type { Fitting } from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/fittings`

export async function get_fittings() {
    const headers = {
        'Content-Type': 'application/json',
    }

    console.log(`Requesting: ${API_ENDPOINT}/`)

    try {
        const response = await fetch(`${API_ENDPOINT}/`, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as Fitting[];
    } catch (error) {
        throw new Error(`Error fetching sigs: ${error.message}`);
    }
}

export async function get_fitting_by_id(id:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    console.log(`Requesting: ${API_ENDPOINT}/${id}`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${id}`, {
            headers: headers
        })

        // console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as Fitting;
    } catch (error) {
        throw new Error(`Error fetching sigs: ${error.message}`);
    }
}