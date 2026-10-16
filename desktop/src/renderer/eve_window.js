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
    }

    // Fade in/out on the main process's show/hide. The body starts hidden (class in the HTML).
    function follow_visibility(on_visibility) {
        on_visibility(visible => document.body.classList.toggle('is-hidden', !visible))
    }

    // Shared overlay-window behaviour: header buttons, click-through, and the resize grip.
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

        // Bottom-right grip resizes the window (transparent windows have no native resize border).
        const grip = document.getElementById('resize')
        grip.addEventListener('pointerdown', event => {
            grip.setPointerCapture(event.pointerId)
            send('resize:start', { x: event.screenX, y: event.screenY })
        })
        grip.addEventListener('pointermove', event => {
            if (grip.hasPointerCapture(event.pointerId)) send('resize:move', { x: event.screenX, y: event.screenY })
        })
        grip.addEventListener('pointerup', event => {
            grip.releasePointerCapture(event.pointerId)
            send('resize:end')
        })
    }

    const api = { background_alpha, apply, follow_visibility, wire_overlay }
    if (typeof module !== 'undefined' && module.exports) module.exports = api
    else root.eve_window = api
})(this)
