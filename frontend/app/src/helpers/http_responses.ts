import { useTranslatedPath } from '@i18n/utils';

const translatePath = useTranslatedPath('en');

export const HTTP_404_Not_Found = (body = null):Response => {
    return new Response(body, {
        status: 404,
        statusText: 'Not found'
    });
}

import Page_403 from '@/pages/403.astro'
import { experimental_AstroContainer as AstroContainer } from 'astro/container';

export const HTTP_403_Forbidden = async () => {
    const container = await AstroContainer.create();

    return new Response(
        await container.renderToString(Page_403, {
            routeType: 'page'
        }), {
            status: 403,
            headers: { 'Content-type': 'text/html' },
            statusText: 'Forbidden',
        }
    ) as Response;
}

export const HTTP_200_Success = (body = null):Response => {
    return new Response(body, {
        status: 200,
        statusText: 'Success'
    });
}

export const HTTP_400_Bad_Request = (body = null):Response => {
    return new Response(body, {
        status: 400,
        statusText: 'Bad Request'
    });
}