
import _slugify from 'slugify';

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

export const slugify = (string:string):string => {
    return _slugify(string, {
        replacement: '_',
        remove: /[*+~.\-\()'"!:@]/g
    })
}

export const is_html = RegExp.prototype.test.bind(/(<([^>]+)>)/i)