const { send, on_state, on_visibility } = window.minmatar
const sneak = document.getElementById('sneak')

window.eve_window.follow_visibility(on_visibility)
on_state(() => {})

sneak.addEventListener('click', () => send('settings:open'))

// The window is click-through except Sneak himself.
sneak.addEventListener('mouseenter', () => send('mouse:interactive', true))
sneak.addEventListener('mouseleave', () => send('mouse:interactive', false))

// Every few minutes he ducks behind the badge and pops back up. Rare on purpose.
function schedule_peek() {
    setTimeout(() => {
        sneak.classList.remove('is-peeking')
        void sneak.offsetWidth
        sneak.classList.add('is-peeking')
        schedule_peek()
    }, 120_000 + Math.random() * 180_000)
}
schedule_peek()
