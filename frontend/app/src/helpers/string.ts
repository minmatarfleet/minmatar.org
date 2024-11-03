import _slugify from 'slugify';
import { marked } from 'marked';
import * as cheerio from 'cheerio';

export const remove_space = (text:string):string => {
    return text.replaceAll(" ", "_")
}

export const query_string = (params):string => {
    return new URLSearchParams(params).toString()
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
        remove: /[*+~.,\-\()'"!:@]/g
    })
}

export const is_html = RegExp.prototype.test.bind(/(<([^>]+)>)/i)

export const capitalize = (text:string):string => {
    return text.charAt(0).toUpperCase() + text.slice(1);
}

export const remove_line_breaks = (text:string):string => {
    return text.replace(/(\r\n|\n|\r)/gm, "")
}

export async function parse_markdown(text:string) {
    return await marked.parseInline(text)
}

export function get_error_message(status:number, endpoint:string) {
    return `HTTP error! Status — ${status}<br><pre style="width: fit-content"><code>${endpoint}</code></pre>`
}

export function decode_unicode_escapes(text) {
    return text.replace(/\\u([0-9A-Fa-f]{4})/g, (match, p1) => String.fromCharCode(parseInt(p1, 16)));
}

export async function strip_markdown(text:string) {
    const $ = cheerio.load(await marked.parse(text))
    return $('p:first').text()
}

export const parse_error_message = (error_details:string) => {
    // Regular expression to match the error message inside the single quotes after "error": 
    const regex = /'error': '([^']+)'/;
    const match = error_details.match(regex);
    
    if (match && match[1]) {
        return match[1];
    } else {
        return null; // or handle the case when the pattern doesn't match
    }
}

export const get_parenthesis_content = (str:string) => {
    const match = str.match(/\(([^)]+)\)/);

    return match ? match[1] : ''
}