// Small JSON settings file in the app's user-data folder (window position, overlay mode).
const fs = require('fs')
const path = require('path')

class Settings {
    constructor(file, defaults) {
        this.file = file
        this.values = { ...defaults }
        try { Object.assign(this.values, JSON.parse(fs.readFileSync(file, 'utf8'))) } catch (e) {}
    }

    get(key) {
        return this.values[key]
    }

    set(key, value) {
        this.values[key] = value
        try {
            fs.mkdirSync(path.dirname(this.file), { recursive: true })
            fs.writeFileSync(this.file, JSON.stringify(this.values, null, 2))
        } catch (e) {}
    }
}

module.exports = { Settings }
