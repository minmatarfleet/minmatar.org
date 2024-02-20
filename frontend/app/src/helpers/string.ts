export const remove_space = (text:string):string => {
    return text.replaceAll(" ", "_")
}

export const query_string = (params):URLSearchParams => {
    return new URLSearchParams(params)
}

export const is_valid_http_url = (string:string):boolean => {
    let url;

    try {
        url = new URL(string);
    } catch (_) {
        return false;  
    }

    return url.protocol === "http:" || url.protocol === "https:";
}