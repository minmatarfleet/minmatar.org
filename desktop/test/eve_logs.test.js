const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { EveLogEngine } = require('../src/main/eve_logs')
const { parse_file_name } = require('../src/main/eve_logs/files')
const { combat, local_system_change, strip_markup } = require('../src/main/eve_logs/parse')

// ---------------------------------------------------------------- fixtures written the way EVE writes them

const pad = n => String(n).padStart(2, '0')
const NOW = new Date()
const day = `${NOW.getUTCFullYear()}${pad(NOW.getUTCMonth() + 1)}${pad(NOW.getUTCDate())}`
const stamp = (h, m, s = 0) => `[ ${NOW.getUTCFullYear()}.${pad(NOW.getUTCMonth() + 1)}.${pad(NOW.getUTCDate())} ${pad(h)}:${pad(m)}:${pad(s)} ]`

function logs_dir() {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'eve-logs-'))
    fs.mkdirSync(path.join(dir, 'Chatlogs'))
    fs.mkdirSync(path.join(dir, 'Gamelogs'))
    return dir
}

const utf16 = text => Buffer.from(text, 'utf16le')

function chat_file(dir, { channel, channel_id = channel.toLowerCase(), listener, id, time = '010000' }) {
    const file = path.join(dir, 'Chatlogs', `${channel}_${day}_${time}_${id}.txt`)
    const header = `\r\n\r\n\r\n        ---------------------------------------------------------------\r\n\r\n` +
        `          Channel ID:      ${channel_id}\r\n          Channel Name:    ${channel}\r\n          Listener:        ${listener}\r\n` +
        `          Session started: 2026.10.16 01:00:00\r\n        ---------------------------------------------------------------\r\n\r\n`
    fs.writeFileSync(file, Buffer.concat([Buffer.from([0xff, 0xfe]), utf16(header)]))
    return file
}
const chat_line = (file, time, sender, text) => fs.appendFileSync(file, utf16(`﻿${time} ${sender} > ${text}\r\n`))

function game_file(dir, { listener, id, time = '010000' }) {
    const file = path.join(dir, 'Gamelogs', `${day}_${time}_${id}.txt`)
    fs.writeFileSync(file, `------------------------------------------------------------\r\n  Gamelog\r\n  Listener: ${listener}\r\n  Session Started: 2026.10.16 01:00:00\r\n------------------------------------------------------------\r\n`)
    return file
}
const game_line = (file, time, kind, html) => fs.appendFileSync(file, `${time} (${kind}) ${html}\r\n`)

function engine_for(dir) {
    const engine = new EveLogEngine({ logs_dir: dir, poll_ms: 1e9, rescan_ms: 1e9 })
    const events = []
    for (const name of ['system', 'chat', 'message', 'game', 'combat', 'session']) engine.on(name, e => events.push({ name, ...e }))
    return { engine, events, of: name => events.filter(e => e.name === name) }
}

// ---------------------------------------------------------------- engine

test('rebuilds current state from existing logs without replaying old events', () => {
    const dir = logs_dir()
    const local = chat_file(dir, { channel: 'Local', listener: 'Kaleb Snowden', id: 95555292 })
    chat_line(local, stamp(1, 0, 5), 'EVE System', 'Channel changed to Local : Amamake')
    chat_line(local, stamp(1, 20), 'EVE System', 'Channel changed to Local : Siseide')
    const { engine, events } = engine_for(dir)
    let ready
    engine.on('ready', s => { ready = s })
    engine.start()
    engine.stop()
    assert.equal(events.length, 0)
    assert.deepEqual(ready.characters.map(c => [c.id, c.name, c.system]), [[95555292, 'Kaleb Snowden', 'Siseide']])
    assert.deepEqual(ready.characters[0].channels, ['Local'])
})

test('emits one system change per jump even though Local and the game log both report it', () => {
    const dir = logs_dir()
    const local = chat_file(dir, { channel: 'Local', listener: 'Kaleb Snowden', id: 1 })
    const game = game_file(dir, { listener: 'Kaleb Snowden', id: 1 })
    chat_line(local, stamp(1, 0, 5), 'EVE System', 'Channel changed to Local : Amamake')
    const { engine, of } = engine_for(dir)
    engine.start()

    game_line(game, stamp(1, 30, 1), 'None', 'Jumping from Amamake to Siseide')
    chat_line(local, stamp(1, 30, 3), 'EVE System', 'Channel changed to Local : Siseide')
    engine.poll()
    engine.stop()

    const systems = of('system')
    assert.equal(systems.length, 1)
    assert.deepEqual([systems[0].from, systems[0].to, systems[0].source], ['Amamake', 'Siseide', 'jump'])
    assert.equal(engine.character_by_name('kaleb snowden').system, 'Siseide')
    assert.deepEqual(engine.character(1).last_jump.to, 'Siseide')
})

test('"Channel changed to Corp : …" is not a system change', () => {
    const dir = logs_dir()
    const corp = chat_file(dir, { channel: 'Corp', listener: 'A', id: 2 })
    const { engine, of } = engine_for(dir)
    engine.start()
    chat_line(corp, stamp(2, 0), 'EVE System', 'Channel changed to Corp : Rattini Tribe')
    engine.poll()
    engine.stop()
    assert.equal(of('system').length, 0)
    assert.equal(of('chat').length, 1)
})

test('lines split across writes (mid-line and mid-UTF-16 character) are joined', () => {
    const dir = logs_dir()
    const local = chat_file(dir, { channel: 'Local', listener: 'A', id: 3 })
    const { engine, of } = engine_for(dir)
    engine.start()
    const bytes = utf16(`﻿${stamp(3, 0)} EVE System > Channel changed to Local : Auga\r\n`)
    fs.appendFileSync(local, bytes.subarray(0, 41))      // odd byte count: splits a UTF-16 code unit
    engine.poll()
    assert.equal(of('system').length, 0)
    fs.appendFileSync(local, bytes.subarray(41))
    engine.poll()
    engine.stop()
    assert.deepEqual(of('system').map(e => e.to), ['Auga'])
})

test('multi-line messages stay one message', () => {
    const dir = logs_dir()
    const fleet = chat_file(dir, { channel: 'Fleet', listener: 'A', id: 4 })
    const { engine, of } = engine_for(dir)
    engine.start()
    fs.appendFileSync(fleet, utf16(`﻿${stamp(4, 0)} EVE System > Channel MOTD: FC: Someone\r\nStaging: Amamake\r\nDoctrine: TFIs\r\n`))
    engine.poll()
    engine.stop()
    assert.equal(of('chat').length, 1)
    assert.equal(of('chat')[0].text, 'Channel MOTD: FC: Someone\nStaging: Amamake\nDoctrine: TFIs')
})

test('a message seen by several of your characters is one "message" with every listener', () => {
    const dir = logs_dir()
    const a = chat_file(dir, { channel: 'Minmatar Intel', channel_id: '-123', listener: 'Alt One', id: 10 })
    const b = chat_file(dir, { channel: 'Minmatar Intel', channel_id: '-123', listener: 'Alt Two', id: 11, time: '010001' })
    const { engine, of } = engine_for(dir)
    const intel = []
    const unwatch = engine.watch_channel(/intel/i, e => intel.push(e))
    engine.start()
    chat_line(a, stamp(5, 0), 'Scout', 'Amamake +3 hostiles')
    chat_line(b, stamp(5, 0), 'Scout', 'Amamake +3 hostiles')
    engine.poll()
    unwatch()
    chat_line(a, stamp(5, 1), 'Scout', 'clr')
    engine.poll()
    engine.stop()
    assert.equal(of('chat').length, 3)
    assert.equal(of('message').length, 2)
    assert.deepEqual(of('message')[0].listeners.map(l => l.name), ['Alt One', 'Alt Two'])
    assert.equal(intel.length, 1)
})

test('combat lines become structured events', () => {
    const dir = logs_dir()
    const game = game_file(dir, { listener: 'A', id: 5 })
    const { engine, of } = engine_for(dir)
    engine.start()
    game_line(game, stamp(6, 0), 'combat', '<color=0xff00ffff><b>448</b> <color=0x77ffffff><font size=10>to</font> <b><color=0xffffffff>Imperial Maller</b><font size=10><color=0x77ffffff> - Heavy Pulse Laser II - Hits')
    engine.poll()
    engine.stop()
    assert.deepEqual(of('combat')[0].combat, { type: 'damage', direction: 'out', amount: 448, other: 'Imperial Maller', weapon: 'Heavy Pulse Laser II', quality: 'Hits' })
})

test('ignores sessions older than the window, and survives a truncated file', () => {
    const dir = logs_dir()
    fs.writeFileSync(path.join(dir, 'Chatlogs', 'Local_20200101_000000_9.txt'), 'old')
    const local = chat_file(dir, { channel: 'Local', listener: 'A', id: 6 })
    const { engine, of } = engine_for(dir)
    engine.start()
    assert.equal(engine.sessions.size, 1)
    fs.writeFileSync(local, Buffer.concat([Buffer.from([0xff, 0xfe]), utf16(`﻿${stamp(7, 0)} EVE System > Channel changed to Local : Vard\r\n`)]))
    engine.poll()
    engine.stop()
    assert.deepEqual(of('system').map(e => e.to), ['Vard'])
})

// ---------------------------------------------------------------- parsers

test('file names: channel names with underscores, with and without character ID', () => {
    assert.deepEqual(parse_file_name('chat', 'FL33T_Capacitor_Chain_20261015_230119_95644892.txt').channel_name, 'FL33T_Capacitor_Chain')
    assert.equal(parse_file_name('chat', 'Local_20261015_230119.txt').character_id, null)
    assert.equal(parse_file_name('game', '20261015_230120_634915984.txt').character_id, 634915984)
    assert.equal(parse_file_name('game', 'notes.txt'), null)
})

test('Local system change parsing', () => {
    assert.equal(local_system_change('EVE System', 'Channel changed to Local : J123456'), 'J123456')
    assert.equal(local_system_change('Someone', 'Channel changed to Local : Fake'), null)
})

test('combat parser covers the common shapes', () => {
    assert.deepEqual(combat('20 from Imperial Maller - Grazes'), { type: 'damage', direction: 'in', amount: 20, other: 'Imperial Maller', weapon: null, quality: 'Grazes' })
    assert.equal(combat('224 remote armor repaired by Exequror [FLNT] [A-RAT] [Sashii Ohmiras] - Medium Remote Armor Repairer II').type, 'remote_repair')
    assert.deepEqual(combat('Warp disruption attempt from Renouncer Maller to Republic Rupture'), { type: 'warp_disruption', source: 'Renouncer Maller', target: 'Republic Rupture' })
    assert.equal(combat('Imperial Frigate misses you completely').direction, 'in')
    assert.equal(combat('Your Hammerhead II misses Imperial Frigate completely - Hammerhead II').direction, 'out')
    assert.equal(combat('something new').type, 'other')
    assert.equal(strip_markup('<b>a</b>&lt;b&gt;<br>c'), 'a<b>\nc')
})

test('a game log opened at character select (no listener) does not create a character', () => {
    const dir = logs_dir()
    fs.writeFileSync(path.join(dir, 'Gamelogs', `${day}_000001.txt`), '------------------------------------------------------------\r\n  Gamelog\r\n  Listener: \r\n  Session Started: x\r\n------------------------------------------------------------\r\n')
    const { engine, of } = engine_for(dir)
    engine.start()
    game_line(path.join(dir, 'Gamelogs', `${day}_000001.txt`), stamp(0, 1), 'notify', 'Connecting')
    engine.poll()
    engine.stop()
    assert.equal(engine.characters().length, 0)
    assert.equal(of('game')[0].character, null)
})
