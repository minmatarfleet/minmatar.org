// Where the app talks to. Production by default; point at a local backend with
//   --api=http://localhost:8000  (or MINMATAR_API_URL)  and  --web=http://localhost:4321  (or MINMATAR_WEB_URL)
const DEFAULT_API_URL = 'https://api.minmatar.org'
const DEFAULT_WEB_URL = 'https://my.minmatar.org'

function arg_value(argv, name) {
    const prefix = `--${name}=`
    const found = argv.find(a => a.startsWith(prefix))
    return found ? found.slice(prefix.length) : undefined
}

function strip_slash(url) {
    return url.replace(/\/+$/, '')
}

function load_config(argv = process.argv, env = process.env) {
    return {
        api_url: strip_slash(arg_value(argv, 'api') || env.MINMATAR_API_URL || DEFAULT_API_URL),
        web_url: strip_slash(arg_value(argv, 'web') || env.MINMATAR_WEB_URL || DEFAULT_WEB_URL),
        // Window process names that count as an EVE client. Tests add "powershell" for a stand-in window.
        client_procs: arg_value(argv, 'client-procs') || 'exefile',
        refresh_ms: Number(arg_value(argv, 'refresh-ms')) || 60_000,
    }
}

module.exports = { load_config, DEFAULT_API_URL, DEFAULT_WEB_URL }
