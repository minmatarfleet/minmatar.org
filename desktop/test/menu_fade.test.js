const test = require('node:test')
const assert = require('node:assert')
const { MenuFade, menu_zone, intersects, MENU_REACH } = require('../src/main/menu_fade')

function recorder(fade) {
    const events = []
    fade.on('fade', zone => events.push(['fade', zone]))
    fade.on('restore', () => events.push(['restore']))
    return events
}

test('menu_zone covers the reach around the click, scaled by EVE UI scale', () => {
    assert.deepStrictEqual(menu_zone({ x: 1000, y: 800 }, 1), {
        x: 1000 - MENU_REACH.left, y: 800 - MENU_REACH.up,
        width: MENU_REACH.left + MENU_REACH.right, height: MENU_REACH.up + MENU_REACH.down,
    })
    const big = menu_zone({ x: 1000, y: 800 }, 1.5)
    assert.strictEqual(big.width, Math.round((MENU_REACH.left + MENU_REACH.right) * 1.5))
    assert.strictEqual(big.x, Math.round(1000 - MENU_REACH.left * 1.5))
})

test('intersects', () => {
    const zone = { x: 0, y: 0, width: 100, height: 100 }
    assert.ok(intersects(zone, { x: 90, y: 90, width: 50, height: 50 }))
    assert.ok(!intersects(zone, { x: 100, y: 0, width: 50, height: 50 }))
})

test('right-click in EVE fades; the next click fades back in on release', () => {
    const fade = new MenuFade()
    const events = recorder(fade)
    fade.button({ b: 'r', down: true, eve: true, x: 500, y: 400 })
    fade.button({ b: 'r', down: false, eve: true, x: 500, y: 400 })   // releasing the right button keeps the menu
    assert.deepStrictEqual(events.map(e => e[0]), ['fade'])
    fade.button({ b: 'l', down: true, eve: true, x: 560, y: 430 })    // pick an entry
    assert.deepStrictEqual(events.map(e => e[0]), ['fade'])
    fade.button({ b: 'l', down: false, eve: true, x: 560, y: 430 })
    assert.deepStrictEqual(events.map(e => e[0]), ['fade', 'restore'])
    fade.restore()
})

test('a right-click on our own window does nothing', () => {
    const fade = new MenuFade()
    const events = recorder(fade)
    fade.button({ b: 'r', down: true, eve: false, x: 500, y: 400 })
    fade.button({ b: 'r', down: false, eve: false, x: 500, y: 400 })
    assert.deepStrictEqual(events, [])
})

test('a second right-click moves the menu and stays faded', () => {
    const fade = new MenuFade()
    const events = recorder(fade)
    fade.button({ b: 'r', down: true, eve: true, x: 500, y: 400 })
    fade.button({ b: 'r', down: false, eve: true, x: 500, y: 400 })
    fade.button({ b: 'r', down: true, eve: true, x: 900, y: 400 })
    fade.button({ b: 'r', down: false, eve: true, x: 900, y: 400 })
    assert.deepStrictEqual(events.map(e => e[0]), ['fade', 'fade'])
    assert.strictEqual(events[1][1].x, 900 - MENU_REACH.left)
    fade.restore()
})

test('gives up after the timeout (menu closed with Esc)', async () => {
    const fade = new MenuFade({ timeout_ms: 20 })
    const events = recorder(fade)
    fade.button({ b: 'r', down: true, eve: true, x: 500, y: 400 })
    await new Promise(resolve => setTimeout(resolve, 40))
    assert.deepStrictEqual(events.map(e => e[0]), ['fade', 'restore'])
})
