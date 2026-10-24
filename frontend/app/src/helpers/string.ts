import _slugify from 'slugify';
import { marked } from 'marked';
import * as cheerio from 'cheerio';

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

export const remove_line_breaks = (text:string):string => {
    return text.replace(/(\r\n|\n|\r)/gm, "")
}

export function decode_unicode_escapes(text) {
    return text.replace(/\\u([0-9A-Fa-f]{4})/g, (match, p1) => String.fromCharCode(parseInt(p1, 16)));
}

export async function strip_markdown(text:string) {
    const $ = cheerio.load(await marked.parse(text))
    return $('p:first').text()
}

export const parse_error_message = (error_details:string) => {
    if (typeof error_details !== 'string')
        return null
    // Regular expression to match the error message inside the single quotes after "error": 
    const regex = /'error': '([^']+)'/;
    const match = error_details.match(regex);
    
    if (match && match[1]) {
        return match[1];
    } else {
        return null; // or handle the case when the pattern doesn't match
    }
}

export const get_parenthesis_content_last = (str:string) => {
    const matches = str.match(/\(([^)]+)\)/g)

    if (matches) {
        const last_match = matches[matches.length - 1]
        return last_match.slice(1, -1)
    }

    return null
}

export const b64_to_Uint8Array = (b64encoded_string:string):Uint8Array => {
    const binaryString = atob(b64encoded_string)

    const len = binaryString.length
    const uint8Array = new Uint8Array(len)
    for (let i = 0; i < len; i++)
        uint8Array[i] = binaryString.charCodeAt(i)

    return uint8Array
}

export const remove_trailing_slash = (str:string) => {
    return str.replace(/\/$/, '')
}

const HTML_ESCAPES: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
}

/** Escape text for an HTML string (tippy allowHTML content, set:html). */
export function escape_html(text: string): string {
    return text.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char])
}
