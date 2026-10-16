// Auto-update from GitHub Releases (electron-updater).
//
// CI publishes each version to a GitHub release tagged v<version> with the installer, its .blockmap and
// latest.yml. The installed app asks GitHub for the latest release, downloads a newer installer in the
// background (only the changed blocks when it can), and installs it on the next quit or on "Restart to update".
//
// The portable .exe can't replace itself; it only reports that a new version exists and links to the release.
const { EventEmitter } = require('events')

const CHECK_EVERY_MS = 4 * 3_600_000
const RELEASES_URL = 'https://github.com/minmatarfleet/minmatar.org/releases/latest'

class Updater extends EventEmitter {
    constructor({ app, diag }) {
        super()
        this.app = app
        this.diag = diag
        this.portable = !!process.env.PORTABLE_EXECUTABLE_DIR
        this.state = { status: 'idle', version: null, percent: null, portable: this.portable }
    }

    get enabled() {
        return this.app.isPackaged && process.platform === 'win32'
    }

    start({ auto_updater = null } = {}) {
        if (!this.enabled && !auto_updater) return this
        const autoUpdater = auto_updater || require('electron-updater').autoUpdater
        this.auto = autoUpdater
        autoUpdater.autoDownload = !this.portable
        autoUpdater.autoInstallOnAppQuit = !this.portable
        autoUpdater.logger = {
            info: m => this.diag({ t: 'updater', level: 'info', message: String(m) }),
            warn: m => this.diag({ t: 'updater', level: 'warn', message: String(m) }),
            error: m => this.diag({ t: 'updater', level: 'error', message: String(m) }),
            debug: () => {},
        }
        autoUpdater.on('update-available', info => this.set({ status: this.portable ? 'available' : 'downloading', version: info.version, percent: 0 }))
        autoUpdater.on('download-progress', p => this.set({ percent: Math.round(p.percent) }))
        autoUpdater.on('update-downloaded', info => this.set({ status: 'ready', version: info.version, percent: 100 }))
        autoUpdater.on('update-not-available', () => this.set({ status: 'current' }))
        // Offline, rate-limited or no release yet: stay quiet and try again on the next check.
        autoUpdater.on('error', err => { this.diag({ t: 'updater-error', message: err.message }); this.set({ status: 'idle' }) })

        this.check()
        this.timer = setInterval(() => this.check(), CHECK_EVERY_MS)
        return this
    }

    stop() { clearInterval(this.timer) }

    check() {
        if (!this.auto || this.state.status === 'ready') return
        this.auto.checkForUpdates().catch(() => {})
    }

    // Close the app and run the downloaded installer silently, then relaunch.
    install() {
        if (this.state.status === 'ready') this.auto.quitAndInstall(true, true)
    }

    set(patch) {
        this.state = { ...this.state, ...patch }
        this.emit('change', this.state)
    }
}

module.exports = { Updater, RELEASES_URL }
