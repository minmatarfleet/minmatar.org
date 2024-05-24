const API_ENDPOINT =  `${import.meta.env.EVE_API_URL ?? 'https://esi.evetech.net/latest'}/route`

export async function get_route(origin:number, destination:number) {
    const headers = {
        'Content-Type': 'application/json',
    }

    console.log(`Requesting: ${API_ENDPOINT}/${origin}/${destination}/?datasource=tranquility&flag=shortest`)

    try {
        const response = await fetch(`${API_ENDPOINT}/${origin}/${destination}/?datasource=tranquility&flag=shortest`, {
            headers: headers
        })

        if (!response.ok) {
            if (response.status === 404)
                return [ ]

            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return await response.json() as number[]
    } catch (error) {
        throw new Error(`Error fetching alliance: ${error.message}`);
    }
}