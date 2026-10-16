import { Marked } from 'marked'

const HTML_ESCAPES: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
}

function escape_html(text: string): string {
    return text.replace(/[&<>"']/g, (char) => HTML_ESCAPES[char])
}

function is_web_url(href: string): boolean {
    return /^(https?:\/\/|mailto:)/i.test(href.trim())
}

// Close to what Reddit shows: raw HTML and inline images come out as text,
// and only web links become links.
const reddit_marked = new Marked({ gfm: true, breaks: false }).use({
    renderer: {
        html(html: string) {
            return escape_html(html)
        },
        image(href: string, _title: string | null, text: string) {
            return escape_html(`![${text}](${href})`)
        },
        link(href: string, title: string | null | undefined, text: string) {
            if (!is_web_url(href)) return text
            const title_attribute = title ? ` title="${escape_html(title)}"` : ''
            return `<a href="${escape_html(href)}"${title_attribute} target="_blank" rel="nofollow noopener noreferrer">${text}</a>`
        },
    },
})

export function render_reddit_markdown(markdown: string): string {
    return reddit_marked.parse(markdown, { async: false }) as string
}
