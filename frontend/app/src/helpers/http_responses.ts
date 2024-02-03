export const HTTP_404_Not_Found = ():Response => {
    return new Response(null, {
        status: 404,
        statusText: 'Not found'
    });
}

export const HTTP_403_Forbidden = ():Response => {
    return new Response(null, {
        status: 403,
        statusText: 'Forbidden'
    });
}