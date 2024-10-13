export const HTTP_404_Not_Found = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 404,
        statusText: 'Not found'
    });
}

/*import Page_403 from '@/pages/403.astro'
import { experimental_AstroContainer as AstroContainer } from 'astro/container';*/

export const HTTP_403_Forbidden = async () => {
    /*const container = await AstroContainer.create();

    return new Response(
        await container.renderToString(Page_403), {
            status: 403,
            headers: { 'Content-type': 'text/html' },
            statusText: 'Forbidden',
        }
    ) as Response;*/

    return new Response(null, {
        status: 403,
        statusText: 'Forbidden'
    });
}

export const HTTP_200_Success = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 200,
        statusText: 'Success'
    });
}

export const HTTP_400_Bad_Request = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 400,
        statusText: 'Bad Request'
    });
}

export const HTTP_500_Server_Error = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 500,
        statusText: 'Server Error'
    });
}