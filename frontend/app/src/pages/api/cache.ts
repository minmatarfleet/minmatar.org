import { HTTP_200_Success } from '@helpers/http_responses'

export async function DELETE({ params, cookies }) {
    cookies.delete('primary_pilot', { path: '/' })

    return HTTP_200_Success()
}