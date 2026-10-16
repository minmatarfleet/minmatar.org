const { test } = require('node:test')
const assert = require('node:assert/strict')
const { EventEmitter } = require('events')
const { Updater } = require('../src/main/updater')

function fake_auto_updater() {
    const fake = new EventEmitter()
    fake.checks = 0
    fake.installed = null
    fake.checkForUpdates = async () => { fake.checks++ }
    fake.quitAndInstall = (silent, relaunch) => { fake.installed = { silent, relaunch } }
    return fake
}

function make(portable) {
    if (portable) process.env.PORTABLE_EXECUTABLE_DIR = 'C:\\x'
    else delete process.env.PORTABLE_EXECUTABLE_DIR
    const updater = new Updater({ app: { isPackaged: true }, diag: () => {} })
    const auto = fake_auto_updater()
    updater.start({ auto_updater: auto })
    updater.stop()
    return { updater, auto }
}

test('installed app: downloads in the background, then installs on request', () => {
    const { updater, auto } = make(false)
    assert.equal(auto.checks, 1)
    assert.equal(auto.autoDownload, true)
    assert.equal(auto.autoInstallOnAppQuit, true)
    auto.emit('update-available', { version: '0.4.0' })
    assert.deepEqual([updater.state.status, updater.state.version], ['downloading', '0.4.0'])
    auto.emit('download-progress', { percent: 41.6 })
    assert.equal(updater.state.percent, 42)
    updater.install()
    assert.equal(auto.installed, null)                       // not downloaded yet: nothing to install
    auto.emit('update-downloaded', { version: '0.4.0' })
    updater.install()
    assert.deepEqual(auto.installed, { silent: true, relaunch: true })
})

test('portable exe: only reports the new version, never downloads', () => {
    const { updater, auto } = make(true)
    assert.equal(auto.autoDownload, false)
    assert.equal(auto.autoInstallOnAppQuit, false)
    auto.emit('update-available', { version: '0.4.0' })
    assert.equal(updater.state.status, 'available')
    delete process.env.PORTABLE_EXECUTABLE_DIR
})

test('errors (offline, no release yet) are silent', () => {
    const { updater, auto } = make(false)
    auto.emit('error', new Error('net::ERR_INTERNET_DISCONNECTED'))
    assert.equal(updater.state.status, 'idle')
})
