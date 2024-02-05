export const HTTP_404_Not_Found = (body = null):Response => {
    return new Response(body, {
        status: 404,
        statusText: 'Not found'
    });
}

export const HTTP_403_Forbidden = (body = null):Response => {
    return new Response(body, {
        status: 403,
        statusText: 'Forbidden'
    });
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