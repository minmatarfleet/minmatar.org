// Window background opacity from EVE's Settings > Windows transparency value (0..1, EVE default 1.0).
// Only the background follows it; text and icons stay fully opaque, as in the client.
// Shared by the windows (global `eve_window`) and the node tests (module.exports).
(function (root) {
    const NATIVE_TINT = 0x40 / 0xff   // alpha of the native glass tint (eve_clients.js GLASS_TINT)
    const GLASS_RANGE = [0.2, 0.92]   // combined background darkness over the live blur at 0 and 1
    const SOLID_RANGE = [0.55, 0.96]  // background alpha when there is no glass to blur through

    const lerp = (range, t) => range[0] + (range[1] - range[0]) * t
    const clamp = t => Math.min(1, Math.max(0, Number.isFinite(t) ? t : 1))

    // Alpha for the CSS layer that sits on top of the native tint.
    function background_alpha(transparency, glass) {
        const t = clamp(transparency)
        if (!glass) return lerp(SOLID_RANGE, t)
        const target = lerp(GLASS_RANGE, t)
        return Math.max(0, 1 - (1 - target) / (1 - NATIVE_TINT))
    }

    function apply(state) {
        const glass = !!state.glass
        document.body.classList.toggle('glass', glass)
        const transparency = state.eve_window ? state.eve_window.transparency : 1
        document.documentElement.style.setProperty('--eve-window-alpha', background_alpha(transparency, glass).toFixed(3))
        // The pin button: pinned windows can't be dragged or resized (eve-window.css).
        if (typeof state.locked === 'boolean') {
            document.body.classList.toggle('is-locked', state.locked)
            const lock = document.getElementById('lock')
            if (lock) {
                lock.setAttribute('aria-pressed', String(state.locked))
                lock.title = state.locked ? 'Pinned in place. Click to move and resize' : 'Click to pin in place'
            }
        }
    }

    // The update prompt, the same in every overlay window: restart once the installer build has downloaded
    // the update, or a link to the release when the build can't update itself (portable). null: nothing to say.
    function update_prompt(update) {
        const u = update || {}
        if (u.status === 'ready') return { label: 'Restart to update', title: `v${u.version} is downloaded. Restart the app to install it`, command: 'update:install' }
        if (u.status === 'available') return { label: `v${u.version} available`, title: 'Open the release page to download it', command: 'update:download' }
        return null
    }

    // Draws update_prompt on a footer button (hidden when there is nothing to say); wire_update sends its command.
    function show_update(button, update) {
        const prompt = update_prompt(update)
        button.hidden = !prompt
        if (!prompt) return
        button.textContent = prompt.label
        button.title = prompt.title
        button.dataset.updateCommand = prompt.command
    }

    function wire_update(button, send) {
        button.addEventListener('click', () => { if (button.dataset.updateCommand) send(button.dataset.updateCommand) })
    }

    // Fade in/out on the main process's show/hide. The body starts hidden (class in the HTML).
    function follow_visibility(on_visibility) {
        on_visibility(visible => document.body.classList.toggle('is-hidden', !visible))
    }

    // Shared overlay-window behaviour: header buttons, click-through, and moving/resizing.
    function wire_overlay(send) {
        document.querySelectorAll('[data-command]').forEach(button => {
            button.addEventListener('click', () => send(button.dataset.command))
        })

        // Overlay mode is click-through except over [data-interactive]: tell main when the cursor is over one.
        let interactive = false
        document.addEventListener('mousemove', event => {
            const over = !!event.target.closest('[data-interactive]')
            if (over !== interactive) {
                interactive = over
                send('mouse:interactive', over)
            }
        })
        document.addEventListener('mouseleave', () => {
            if (interactive) { interactive = false; send('mouse:interactive', false) }
        })

        wire_drag(send)
    }

    // Unpinned windows move by the header and resize from the bottom-right grip, both driven from here with
    // pointer capture. The header can't be a native drag region (-webkit-app-region): Chromium treats it as
    // window frame, so the page sees the cursor leave as it reaches the header, main turns click-through back
    // on, and the press lands on EVE. Transparent windows have no native resize border either.
    function wire_drag(send) {
        const handle = (el, kind, accepts) => {
            el.addEventListener('pointerdown', event => {
                if (event.button !== 0 || document.body.classList.contains('is-locked') || !accepts(event)) return
                el.setPointerCapture(event.pointerId)
                send('drag:start', { kind, point: { x: event.screenX, y: event.screenY } })
            })
            el.addEventListener('pointermove', event => {
                if (el.hasPointerCapture(event.pointerId)) send('drag:move', { x: event.screenX, y: event.screenY })
            })
            const end = event => {
                if (!el.hasPointerCapture(event.pointerId)) return
                el.releasePointerCapture(event.pointerId)
                send('drag:end')
            }
            el.addEventListener('pointerup', end)
            el.addEventListener('pointercancel', end)
        }
        handle(document.querySelector('.eve-window__header'), 'move', event => !event.target.closest('button'))
        handle(document.getElementById('resize'), 'resize', () => true)
    }

    const api = { background_alpha, apply, follow_visibility, wire_overlay, wire_drag, update_prompt, show_update, wire_update }
    if (typeof module !== 'undefined' && module.exports) module.exports = api
    else root.eve_window = api
})(this)
