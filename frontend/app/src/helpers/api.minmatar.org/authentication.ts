const API_ENDPOINT =  `${import.meta.env.API_URL}/api/auth`

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

        console.log(response)

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return (response.status === 200);
    } catch (error) {
        throw new Error(`Error deleting account: ${error.message}`);
    }
}