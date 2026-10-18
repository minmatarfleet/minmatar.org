const { test } = require('node:test')
const assert = require('node:assert/strict')
const { esc, plural, type_icon, type_render, portrait, corporation_logo, alliance_logo } = require('../src/renderer/ui_helpers')

test('esc makes any value safe for element text and quoted attributes', () => {
    const cases = [
        ['plain', 'plain'],
        ['<img src=x onerror=alert(1)>', '&lt;img src=x onerror=alert(1)&gt;'],
        ['Tom & Jerry', 'Tom &amp; Jerry'],
        ['say "hi"', 'say &quot;hi&quot;'],
        ["O'Neil", 'O&#39;Neil'],
        ['&amp;', '&amp;amp;'],
        [null, ''],
        [undefined, ''],
        [0, '0'],
        [false, 'false'],
        [42, '42'],
    ]
    for (const [input, expected] of cases) assert.equal(esc(input), expected, String(input))
})

test('plural adds an s unless told the plural', () => {
    assert.equal(plural(1, 'pilot'), '1 pilot')
    assert.equal(plural(0, 'pilot'), '0 pilots')
    assert.equal(plural(2, 'pilot'), '2 pilots')
    assert.equal(plural(1, 'loss', 'losses'), '1 loss')
    assert.equal(plural(3, 'loss', 'losses'), '3 losses')
    assert.equal(plural(5, 'more ship'), '5 more ships')
})

test('Image Server URLs', () => {
    assert.equal(type_icon(587), 'https://images.evetech.net/types/587/icon?size=64')
    assert.equal(type_icon(587, 32), 'https://images.evetech.net/types/587/icon?size=32')
    assert.equal(type_render(587), 'https://images.evetech.net/types/587/render?size=256')
    assert.equal(portrait(90000001), 'https://images.evetech.net/characters/90000001/portrait?size=64')
    assert.equal(corporation_logo(500002, 32), 'https://images.evetech.net/corporations/500002/logo?size=32')
    assert.equal(alliance_logo(99), 'https://images.evetech.net/alliances/99/logo?size=64')
    // An id can never break out of the URL or the attribute it sits in.
    assert.equal(portrait('1"/><script>'), 'https://images.evetech.net/characters/1%22%2F%3E%3Cscript%3E/portrait?size=64')
})
