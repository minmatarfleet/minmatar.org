const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { read_number_setting, find_character_files, EveWindowSettings } = require('../src/main/eve_settings')
const { background_alpha } = require('../src/renderer/eve_window')

// One marshalled setting as EVE writes it: (FILETIME, value) then the key.
function setting(key, value_bytes) {
    const filetime = Buffer.from('2ae6fc6c0d5ddd01', 'hex')
    return Buffer.concat([Buffer.from([0x2c, 0x2f, 0x08]), filetime, value_bytes, Buffer.from([0x13, key.length]), Buffer.from(key, 'latin1')])
}
const float64 = n => { const b = Buffer.alloc(9); b[0] = 0x0a; b.writeDoubleLE(n, 1); return b }

function settings_file(...settings) {
    // dict header + entries, surrounded by unrelated data
    return Buffer.concat([Buffer.from('7e61000000160d', 'hex'), ...settings, Buffer.from([0x13, 0x05]), Buffer.from('inbox')])
}

test('reads windowTransparency (float64)', () => {
    const file = settings_file(setting('windowTransparency', float64(0.148)), setting('windowTransparencyLightMode', float64(0.162)))
    assert.equal(read_number_setting(file, 'windowTransparency'), 0.148)
    assert.equal(read_number_setting(file, 'windowTransparencyLightMode'), 0.162)
})

test('reads the compact zero/one encodings', () => {
    assert.equal(read_number_setting(settings_file(setting('windowTransparency', Buffer.from([0x0b]))), 'windowTransparency'), 0)
    assert.equal(read_number_setting(settings_file(setting('windowTransparency', Buffer.from([0x09]))), 'windowTransparency'), 1)
})

test('missing key, or key not preceded by a (time, value) pair -> null', () => {
    assert.equal(read_number_setting(settings_file(setting('somethingElse', float64(0.5))), 'windowTransparency'), null)
    const bare = Buffer.concat([float64(0.5), Buffer.from([0x13, 18]), Buffer.from('windowTransparency')])
    assert.equal(read_number_setting(bare, 'windowTransparency'), null)
})

function fake_eve_install() {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'eve-'))
    const dir = path.join(root, 'CCP', 'EVE', 'c_ccp_eve_tq_tranquility', 'settings_Default')
    fs.mkdirSync(dir, { recursive: true })
    fs.mkdirSync(path.join(root, 'CCP', 'EVE', 'c_ccp_eve_tq_tranquility', 'settings_Default_backup0'))
    return { root, dir }
}

test('finds character files and skips backup profiles', () => {
    const { root, dir } = fake_eve_install()
    fs.writeFileSync(path.join(dir, 'core_char_111.dat'), settings_file(setting('windowTransparency', float64(0.3))))
    fs.writeFileSync(path.join(dir, 'core_user_9.dat'), 'x')
    fs.writeFileSync(path.join(root, 'CCP', 'EVE', 'c_ccp_eve_tq_tranquility', 'settings_Default_backup0', 'core_char_222.dat'), 'x')
    assert.deepEqual(find_character_files(root).map(f => f.character_id), [111])
})

test('follows the chosen character, defaults to the last saved one, and falls back to 1.0', () => {
    const { root, dir } = fake_eve_install()
    fs.writeFileSync(path.join(dir, 'core_char_111.dat'), settings_file(setting('windowTransparency', float64(0.3))))
    fs.writeFileSync(path.join(dir, 'core_char_222.dat'), settings_file(setting('somethingElse', float64(0.5))))
    fs.utimesSync(path.join(dir, 'core_char_222.dat'), new Date(), new Date(Date.now() + 1000))

    const watcher = new EveWindowSettings({ local_app_data: root })
    watcher.poll()
    assert.deepEqual(watcher.current, { transparency: 1, character_id: 222, found: false, badge_offset: null, ui_scale: 1 })
    watcher.set_character(111)
    assert.deepEqual(watcher.current, { transparency: 0.3, character_id: 111, found: true, badge_offset: null, ui_scale: 1 })
})

test('background follows EVE transparency: more transparent setting -> lighter background', () => {
    assert.ok(background_alpha(0.148, true) < background_alpha(1, true))
    assert.ok(background_alpha(0.148, false) < background_alpha(1, false))
    assert.ok(background_alpha(0, true) >= 0)
    assert.ok(background_alpha(1, false) <= 1)
    assert.equal(background_alpha(NaN, true), background_alpha(1, true))
})

test('ESI name lookup identifies the app and pins the API version', async () => {
    const { character_id_for_name } = require('../src/main/eve_settings')
    let seen
    const id = await character_id_for_name('Header Check Pilot', async (url, options) => {
        seen = { url, headers: options.headers }
        return { ok: true, json: async () => ({ characters: [{ id: 7, name: 'Header Check Pilot' }] }) }
    })
    assert.equal(id, 7)
    assert.equal(seen.url, 'https://esi.evetech.net/universe/ids')
    assert.match(seen.headers['User-Agent'], /^MinmatarFleetDesktop\/\d+\.\d+\.\d+ /)
    assert.match(seen.headers['X-Compatibility-Date'], /^\d{4}-\d\d-\d\d$/)
})

test('reads int-pair settings (notification badge offset) in every int encoding', () => {
    const { read_int_pair_setting } = require('../src/main/eve_settings')
    const pair = (a, b) => Buffer.concat([Buffer.from([0x2c]), a, b])
    const int8 = n => Buffer.from([0x06, n & 0xff])
    const int16 = n => { const b = Buffer.alloc(3); b[0] = 0x05; b.writeInt16LE(n, 1); return b }
    const int32 = n => { const b = Buffer.alloc(5); b[0] = 0x04; b.writeInt32LE(n, 1); return b }
    const key = 'notification_badge_offset'
    assert.deepEqual(read_int_pair_setting(settings_file(setting(key, pair(int8(16), int8(16)))), key), [16, 16])
    assert.deepEqual(read_int_pair_setting(settings_file(setting(key, pair(int16(300), Buffer.from([0x08])))), key), [300, 0])
    assert.deepEqual(read_int_pair_setting(settings_file(setting(key, pair(int32(70000), int8(-5)))), key), [70000, -5])
    assert.equal(read_int_pair_setting(settings_file(setting(key, float64(1))), key), null)
})

test('reads UI scale from core_public__.yaml for the current window mode', () => {
    const { read_public_settings, ui_scale_from } = require('../src/main/eve_settings')
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'eve-pub-'))
    fs.writeFileSync(path.join(dir, 'core_public__.yaml'), 'device:\r\n  UIScaleFullscreen: [134366344689451158, 1.0]\r\n  UIScaleWindowed: [134366345551403519, 1.25]\r\n  UIScaleWindowedSetAutomatically: [134366345551403519, false]\r\n  WindowMode: [134366334128151575, 2]\r\n  FullScreenResolution: [134366334120228931, null]\r\n')
    const pub = read_public_settings(dir)
    assert.equal(pub.UIScaleWindowed, 1.25)
    assert.equal(pub.UIScaleWindowedSetAutomatically, false)
    assert.equal(pub.FullScreenResolution, null)
    assert.equal(ui_scale_from(pub), 1.25)
    assert.equal(ui_scale_from({ ...pub, WindowMode: 0 }), 1.0)
    assert.equal(ui_scale_from({}), 1)
    assert.deepEqual(read_public_settings(path.join(dir, 'missing')), {})
})

test('picks up a moved notification badge as soon as EVE rewrites the file', async () => {
    const { EveWindowSettings } = require('../src/main/eve_settings')
    const { root, dir } = fake_eve_install()
    const file = path.join(dir, 'core_char_111.dat')
    const badge = (x, y) => setting('notification_badge_offset', Buffer.from([0x2c, 0x06, x, 0x06, y]))
    fs.writeFileSync(file, settings_file(badge(16, 16)))
    const watcher = new EveWindowSettings({ local_app_data: root, poll_ms: 1e9 })   // no interval: only the folder watch
    let timeout
    try {
        watcher.start()
        assert.deepEqual(watcher.current.badge_offset, [16, 16])
        const moved = new Promise(resolve => watcher.on('change', resolve))
        fs.writeFileSync(file, settings_file(badge(16, 10)))
        // poll() only rereads a file whose mtime moved. Linux file systems stamp mtimes at kernel-tick
        // granularity, so a rewrite within a few ms of the first write can keep the same mtime; EVE's real
        // saves are seconds apart. Move it forward so the test checks the watch, not the clock.
        const later = new Date(Date.now() + 2000)
        fs.utimesSync(file, later, later)
        const value = await Promise.race([moved, new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('no change within 3 s')), 3000) })])
        assert.deepEqual(value.badge_offset, [16, 10])
    } finally {
        // An open fs.watch keeps node alive: always close it, or a failure hangs the whole test run.
        clearTimeout(timeout)
        watcher.stop()
    }
})
