// Reads rust/display.env (KEY='value' lines) and sets each in process.env.
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export function load_display_env(env = process.env) {
    const path = resolve(dirname(fileURLToPath(import.meta.url)), 'display.env')
    const values = {}
    for (const line of readFileSync(path, 'utf8').split('\n')) {
        const match = /^([A-Z_]+)=(['"]?)(.*)\2$/.exec(line.trim())
        if (match)
            values[match[1]] = env[match[1]] = match[3]
    }
    return values
}
