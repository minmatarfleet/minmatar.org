const test = require('node:test')
const assert = require('node:assert/strict')
const { ClipboardWatch, detect_paste } = require('../src/main/clipboard_watch')

const DSCAN = '587\tRifter\tRifter\t1,204 km\n670\tCapsule\tCapsule\t-\n2203\tAcolyte I\tAcolyte I\t12 km\r\n'
const LOCAL = 'Kesra Lund\nJo Smith\nkesra lund\nA.B. O\'Neil\n'

test('detect_paste: same rules as the backend, a d-scan or Local', () => {
    assert.deepEqual(detect_paste(DSCAN), { kind: 'dscan', count: 3 })
    assert.deepEqual(detect_paste(LOCAL), { kind: 'local', count: 3 })   // names count once
    // One plain line is usually chat, not Local.
    assert.equal(detect_paste('ok thanks'), null)
    assert.equal(detect_paste(''), null)
    assert.equal(detect_paste('https://my.minmatar.org/intel/scans/abc123'), null)
    assert.equal(detect_paste('[Rifter, Tackle]\nDamage Control II\n200mm AutoCannon II'), null)   // a fit from the Fleets window
    assert.equal(detect_paste('[ 2026.10.18 12:00:00 ] Kesra Lund > hi\nJo Smith'), null)
    assert.equal(detect_paste('x'.repeat(200_001)), null)
})

function harness(initial = '') {
    let text = initial
    const copies = []
    let tick = null
    const watch = new ClipboardWatch({
        read: () => text,
        on_copy: (copied, found) => copies.push([copied, found]),
        timers: { setInterval: fn => { tick = fn; return 1 }, clearInterval: () => { tick = null } },
    })
    return {
        watch, copies,
        copy: next => { text = next },
        tick: () => tick && tick(),
        get running() { return !!tick },
    }
}

test('a new d-scan or Local copy opens; what was on the clipboard before the window came up does not', () => {
    const h = harness(DSCAN)
    h.watch.set_active(true)
    h.tick()
    assert.deepEqual(h.copies, [])
    h.copy(LOCAL)
    h.tick()
    h.tick()   // the same copy opens once
    assert.deepEqual(h.copies, [[LOCAL, { kind: 'local', count: 3 }]])
    h.copy('just some text')
    h.tick()
    h.copy(DSCAN)
    h.tick()
    assert.deepEqual(h.copies.map(([, found]) => found.kind), ['local', 'dscan'])
})

test('text the window already got by Ctrl+V does not open again', () => {
    const h = harness()
    h.watch.set_active(true)
    h.watch.mark_used(DSCAN)
    h.copy(DSCAN)
    h.tick()
    assert.deepEqual(h.copies, [])
})

test('stopping stops reading, and starting again takes a fresh baseline', () => {
    const h = harness()
    h.watch.set_active(true)
    h.watch.set_active(false)
    assert.equal(h.running, false)
    h.copy(DSCAN)
    h.watch.set_active(true)
    h.tick()
    assert.deepEqual(h.copies, [])
})

test('only a hash of the clipboard is kept', () => {
    const h = harness()
    h.watch.set_active(true)
    h.copy(LOCAL)
    h.tick()
    assert.ok(!JSON.stringify(h.watch, (k, v) => (['read', 'on_copy'].includes(k) ? undefined : v)).includes('Kesra'))
})

test('a busy clipboard is skipped, not thrown', () => {
    const watch = new ClipboardWatch({ read: () => { throw new Error('busy') }, on_copy: () => {}, timers: { setInterval: () => 1, clearInterval: () => {} } })
    assert.doesNotThrow(() => { watch.set_active(true); watch.check() })
})
