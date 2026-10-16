import { describe, expect, it } from 'vitest'

import { render_reddit_markdown } from '@helpers/reddit_markdown'

describe('render_reddit_markdown', () => {
    it('renders Markdown', () => {
        const html = render_reddit_markdown('# Join us\n\n**Fights** every day\n\n- one\n- two')
        expect(html).toContain('<h1>Join us</h1>')
        expect(html).toContain('<strong>Fights</strong>')
        expect(html).toContain('<li>one</li>')
    })

    it('joins single line breaks like Reddit', () => {
        expect(render_reddit_markdown('one\ntwo')).not.toContain('<br>')
    })

    it('shows raw HTML as text', () => {
        const html = render_reddit_markdown('<script>alert(1)</script>\n\nhi <b>there</b>')
        expect(html).not.toContain('<script>')
        expect(html).not.toContain('<b>')
        expect(html).toContain('&lt;script&gt;')
    })

    it('shows inline images as text', () => {
        const html = render_reddit_markdown('![logo](https://example.com/a.png)')
        expect(html).not.toContain('<img')
        expect(html).toContain('![logo](https://example.com/a.png)')
    })

    it('only links web addresses', () => {
        const html = render_reddit_markdown('[discord](https://discord.gg/x) [bad](javascript:alert(1))')
        expect(html).toContain('<a href="https://discord.gg/x"')
        expect(html).toContain('rel="nofollow noopener noreferrer"')
        expect(html).not.toContain('javascript:')
    })
})
