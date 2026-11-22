import { describe, expect, test } from 'vitest'

import { classify_post, post_source_url, youtube_embed_url } from '@helpers/content_viewer'

const VIDEO = `<div class="hidden">
![image](https://i.ytimg.com/vi/6rqoUHCj5P0/maxresdefault.jpg)
</div>
<lite-youtube videoid="6rqoUHCj5P0" posterquality="maxresdefault" autoload></lite-youtube>

[Posted on Reddit](https://www.reddit.com/r/Eve/comments/1xwuuvi/eve_online_the_cope/)
`

const POSTER = `![image](https://preview.redd.it/nab787osd00i1.png?width=1080&format=png)

[Posted on Reddit](https://www.reddit.com/r/Eve/comments/1xpf9he/the_goonswarm_effect/)
`

const ARTICLE = `![image](https://preview.redd.it/ra73i1q297zh1.png?width=1586)
Hello conquest engine exciters!

${'It is time for another frontline report, which sums up everything that has happened across the warzone. '.repeat(5)}`

describe('content viewer', () => {
    test('a lite-youtube post is a video', () => {
        expect(classify_post(VIDEO)).toEqual({ kind: 'video', embed_url: youtube_embed_url('6rqoUHCj5P0'), text: '' })
    })

    test('a YouTube link is a video too', () => {
        expect(classify_post('Watch https://www.youtube.com/watch?v=dQw4w9WgXcQ now')).toMatchObject({ kind: 'video', embed_url: youtube_embed_url('dQw4w9WgXcQ') })
        expect(classify_post('https://youtu.be/dQw4w9WgXcQ')).toMatchObject({ kind: 'video', embed_url: youtube_embed_url('dQw4w9WgXcQ') })
    })

    test('one image and a source link is a poster', () => {
        expect(classify_post(POSTER)).toEqual({
            kind: 'image',
            image: 'https://preview.redd.it/nab787osd00i1.png?width=1080&format=png',
            text: '',
        })
    })

    test('an image with a long write-up is an article', () => {
        expect(classify_post(ARTICLE)).toEqual({ kind: 'article' })
    })

    test('text alone is an article', () => {
        expect(classify_post('Just words.')).toEqual({ kind: 'article' })
    })

    test('several images and a source link is a gallery', () => {
        expect(classify_post('![a](https://x/1.png)\n\n![b](https://x/2.png)\n\n[Posted on Reddit](https://www.reddit.com/r/Eve/comments/g1/x/)')).toEqual({
            kind: 'gallery',
            images: ['https://x/1.png', 'https://x/2.png'],
            text: '',
        })
    })

    test("Reddit's embedded player is a video", () => {
        const post = '<div class="hidden">\n![image](https://external-preview.redd.it/p.png)\n</div>\n'
            + '<iframe class="reddit-embed" src="https://embed.reddit.com/r/Eve/comments/1xnjsr1/goons/?embed=true&amp;theme=dark" title="Goons"></iframe>\n\n'
            + '[Posted on Reddit](https://www.reddit.com/r/Eve/comments/1xnjsr1/goons/)'
        expect(classify_post(post)).toEqual({
            kind: 'video',
            embed_url: 'https://embed.reddit.com/r/Eve/comments/1xnjsr1/goons/?embed=true&theme=dark',
            text: '',
        })
    })

    test('embed and source helpers', () => {
        expect(youtube_embed_url('6rqoUHCj5P0')).toBe('https://www.youtube-nocookie.com/embed/6rqoUHCj5P0?autoplay=1&rel=0&modestbranding=1')
        expect(post_source_url(POSTER)).toBe('https://www.reddit.com/r/Eve/comments/1xpf9he/the_goonswarm_effect/')
        expect(post_source_url('nothing')).toBeNull()
    })
})
