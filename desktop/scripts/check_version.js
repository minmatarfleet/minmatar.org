// Release gate for the desktop app. Used by .github/workflows/desktop.yml.
//
//   node scripts/check_version.js pr <base_version> <released_tags...> <changed>
//       On pull requests. <changed> is "true" if app files changed.
//       Fails if the version is not semver, goes backwards, or was already released.
//       Version not bumped -> a notice only: merging won't release, which is fine until you're ready.
//
// Exit code 1 = fail the job. Output lines starting with "::" are GitHub Actions annotations.

const SEMVER = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?$/

function parse(version) {
    const m = SEMVER.exec(String(version || '').trim())
    if (!m) return null
    return { major: +m[1], minor: +m[2], patch: +m[3], pre: m[4] || null }
}

// -1 / 0 / 1. A pre-release sorts before its release (1.2.0-beta.1 < 1.2.0).
function compare(a, b) {
    const x = parse(a), y = parse(b)
    for (const k of ['major', 'minor', 'patch']) if (x[k] !== y[k]) return x[k] < y[k] ? -1 : 1
    if (x.pre === y.pre) return 0
    if (!x.pre) return 1
    if (!y.pre) return -1
    return x.pre < y.pre ? -1 : 1
}

function check_pr({ version, base_version, released, changed }) {
    const messages = []
    if (!parse(version)) return { ok: false, messages: [`::error file=desktop/package.json::version "${version}" is not semantic versioning (MAJOR.MINOR.PATCH)`] }
    if (released.includes(`v${version}`)) {
        if (version !== base_version) return { ok: false, messages: [`::error file=desktop/package.json::v${version} has already been released; pick the next version`] }
        if (changed) messages.push(`::notice file=desktop/package.json::Desktop app changed but version is still ${version}: merging will not publish a release. Bump the version when it's ready to ship.`)
        return { ok: true, messages }
    }
    if (base_version && parse(base_version) && compare(version, base_version) <= 0 && version !== base_version) {
        return { ok: false, messages: [`::error file=desktop/package.json::version ${version} must be greater than ${base_version} on main`] }
    }
    if (version !== base_version) messages.push(`::notice file=desktop/package.json::Merging will release desktop v${version} (was ${base_version || 'unreleased'}).`)
    else if (changed) messages.push(`::notice file=desktop/package.json::Version ${version} is not released yet: merging will publish it.`)
    return { ok: true, messages }
}

if (require.main === module) {
    const [mode, base_version, changed, ...released] = process.argv.slice(2)
    const version = require('../package.json').version
    if (mode !== 'pr') { console.error('usage: check_version.js pr <base_version> <changed> [released tags...]'); process.exit(2) }
    const result = check_pr({ version, base_version, released, changed: changed === 'true' })
    for (const m of result.messages) console.log(m)
    process.exit(result.ok ? 0 : 1)
}

module.exports = { parse, compare, check_pr }
