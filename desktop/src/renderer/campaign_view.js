// The Campaigns window's content as HTML: one row per system and the faces of the pilots active in the
// last hour. Pure functions of main's state (campaign, campaign_error, campaign_updated_at); campaigns.js
// wires events, the tooltip and the bar geometry. Shared by the window (global `campaign_view`) and the
// node tests (module.exports).
(function (root) {
    const node = typeof module !== 'undefined' && module.exports
    const { esc, portrait } = node ? require('./ui_helpers') : root.ui_helpers
    const { eve_time, clock } = node ? require('./fleet_format') : root.fleet_format
    const { compact_number, change_tone, change_text, bar, activity_text, flip_tone, row_title, PERIODS, SHORT_PERIODS, FLIPS, FLIP_WORDS } = node ? require('./campaign_format') : root.campaign_format

    const STACK_FACES = 5   // faces shown before "+N" when the window is narrow (campaigns.css)
    const HOLDERS = { minmatar: 'Held by Minmatar', amarr: 'Held by Amarr' }
    const ARROWS = {
        up: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 2l5 8H1z"/></svg>',
        down: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M6 10l5-8H1z"/></svg>',
        steady: '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M1.5 6h9"/></svg>',
        none: '',
    }
    const CHANGE_WORDS = { up: 'gaining', down: 'losing', steady: 'steady', none: 'no reading yet' }

    function render_change(system, tone) {
        if (system.flipped) return `${ARROWS[tone]}${FLIPS[system.flipped]}`
        if (system.change == null) return ''
        const period = SHORT_PERIODS[system.change_period] || ''
        return `${ARROWS[tone]}${change_text(system.change)}<span class="change__period">${period}</span>`
    }

    function render_system(system) {
        const tone = flip_tone(system.flipped) || change_tone(system.change)
        const geometry = bar(system.progress, system.flipped ? null : system.change)
        const holder = system.holder
            ? `<img class="system__holder" src="../assets/${system.holder}.svg" alt="${HOLDERS[system.holder]}" title="${HOLDERS[system.holder]}">`
            : '<span class="system__holder"></span>'
        const move = system.flipped ? FLIP_WORDS[system.flipped].toLowerCase()
            : system.change == null ? CHANGE_WORDS.none
            : `${CHANGE_WORDS[tone]} ${change_text(system.change)} ${PERIODS[system.change_period] || ''}`.trim()
        const label = `${system.name}, ${system.objective}, ${move}`
        return `<div class="system" role="link" tabindex="0" data-interactive data-open title="${esc(row_title(system))}" aria-label="${esc(label)}">
        ${holder}
        <span class="system__names"><span class="system__name">${esc(system.name)}</span><span class="system__objective">${esc(system.objective)}</span></span>
        <span class="meter" aria-hidden="true">
            <span class="meter__fill" data-left="0" data-width="${geometry.fill}"></span>
            <span class="meter__delta meter__delta--${tone}" data-left="${geometry.delta_from}" data-width="${geometry.delta_width}"></span>
        </span>
        <span class="change change--${tone}" aria-hidden="true">${render_change(system, tone)}</span>
    </div>`
    }

    function render_pilots(campaign) {
        const pilots = campaign.pilots
        if (!pilots.length) return '<p class="pilots-empty">Nobody has flown this campaign in the last hour.</p>'
        const faces = pilots.map((pilot, i) =>
            `<button class="pilot" data-interactive data-pilot="${i}" aria-label="${esc(`${pilot.name}: ${activity_text(pilot)}`)}">
            <img src="${portrait(pilot.character_id)}" alt="">
        </button>`).join('')
        const more = pilots.length - STACK_FACES
        return `<div class="pilots">${faces}
        <span class="pilots__more" ${more > 0 ? '' : 'hidden'} aria-hidden="true">+${Math.max(0, more)}</span>
        <span class="pilots__label">${pilots.length} active in the last hour</span>
    </div>`
    }

    // The campaign the window shows: the one picked in the switcher, else the one the legacy payload is about,
    // else the first. Null on an older backend (no list), so the window keeps today's look.
    function selected_campaign(campaign, slug) {
        const list = (campaign && campaign.campaigns) || []
        return list.find(entry => entry.slug === slug) || list.find(entry => entry.slug === campaign.slug) || list[0] || null
    }

    // Weekly rows belong to the legacy `campaign` payload, so they show only for that campaign (and only
    // when its weekly progress is on); anything else gets Totals + Next timers.
    function shows_weekly(campaign, entry) {
        return !entry || (entry.slug === campaign.slug && entry.weekly_progress && campaign.systems.length > 0)
    }

    function render_switcher(campaign, entry) {
        if (campaign.campaigns.length < 2) return ''
        const buttons = campaign.campaigns.map(item => {
            const on = item.slug === entry.slug
            const status = item.status && item.status !== 'active' ? ` <span class="eve-dim">&middot; ${esc(item.status)}</span>` : ''
            return `<button class="switch${on ? ' is-on' : ''}" data-interactive data-campaign="${esc(item.slug)}" aria-pressed="${on}">${esc(item.name)}${status}</button>`
        }).join('')
        return `<nav class="switcher" aria-label="Campaigns">${buttons}</nav>`
    }

    const TOTALS = [['structures_destroyed', 'Structures'], ['isk_destroyed', 'ISK destroyed'], ['ships_killed', 'Ships']]

    function render_totals(entry) {
        if (!entry.totals) return ''
        const cells = TOTALS.map(([key, label]) =>
            `<div class="total"><span class="total__value">${compact_number(entry.totals[key])}</span><span class="total__label">${label}</span></div>`).join('')
        return `<section class="campaign-group" aria-label="Totals">
            <div class="campaign-heading"><span>Totals</span></div>
            <div class="totals">${cells}</div>
        </section>`
    }

    const CHEVRON = '<svg viewBox="0 0 8 12" aria-hidden="true"><path d="M2 1.5l4.5 4.5L2 10.5"/></svg>'

    // Three chevrons (shield, armor, hull), filled up to the stage this timer starts; red when it is the kill timer.
    function render_stage(timer) {
        const word = timer.final ? 'Final timer: the structure dies' : timer.stage === 3 ? 'Hull timer' : 'Armor timer: a hull timer follows'
        const chevrons = [1, 2, 3].map(n => `<span class="stage__step${n <= timer.stage ? ' is-on' : ''}">${CHEVRON}</span>`).join('')
        return `<span class="stage${timer.final ? ' stage--final' : ''}" title="${esc(word)}" aria-label="${esc(word)}">${chevrons}</span>`
    }

    function render_timer(timer, now = new Date()) {
        const day = new Date(timer.at).toUTCString().slice(0, 3)
        return `<div class="timer" role="listitem">
        ${render_stage(timer)}
        <span class="timer__names"><span class="timer__name">${esc(timer.name)}</span><span class="timer__where">${esc([timer.type_name, timer.system].filter(Boolean).join(' \u00b7 '))}</span></span>
        <span class="timer__clock" data-at="${esc(timer.at)}">${clock(timer.at, now).text}</span>
        <span class="timer__when">${day} ${eve_time(timer.at)}</span>
    </div>`
    }

    function render_timers(entry, now) {
        const rows = entry.next_timers.length
            ? entry.next_timers.map(timer => render_timer(timer, now)).join('')
            : '<div class="eve-empty">No timers are running.</div>'
        return `<section class="campaign-group" aria-label="Next timers">
            <div class="campaign-heading"><span>Next timers</span><span class="eve-dim">EVE time</span></div>
            <div role="list">${rows}</div>
        </section>`
    }

    function render_skeleton() {
        return '<div class="campaign-heading"><span class="skeleton skeleton--short"></span></div>' +
            Array.from({ length: 3 }, () => '<div class="system system--skeleton" aria-hidden="true"><span></span><span class="skeleton"></span><span class="skeleton"></span><span></span></div>').join('')
    }

    function render(state, slug, now = new Date()) {
        const campaign = state.campaign
        if (!campaign) {
            if (!state.campaign_updated_at && !state.campaign_error) return render_skeleton()
            return state.campaign_error ? '' : '<div class="eve-empty">No campaign is live right now.</div>'
        }
        const entry = selected_campaign(campaign, slug)
        const switcher = entry ? render_switcher(campaign, entry) : ''
        if (!shows_weekly(campaign, entry)) return switcher + render_totals(entry) + render_timers(entry, now)
        const count = campaign.pilots.length
        return switcher + `<section class="campaign-group" aria-label="Systems">
            <div class="campaign-heading"><span>Systems</span><span class="eve-dim">Week ${campaign.week_index} of ${campaign.week_count}</span></div>
            ${campaign.systems.map(render_system).join('')}
        </section>
        <section class="campaign-group" aria-label="Active in the last hour">
            <div class="campaign-heading"><span>Active in the last hour</span><span class="eve-dim">${count} ${count === 1 ? 'pilot' : 'pilots'}</span></div>
            ${render_pilots(campaign)}
        </section>`
    }

    // Everything under the title bar: the error line (if any) above the systems and pilots.
    function content(state, slug, now) {
        return (state.campaign_error ? `<p class="eve-error">${esc(state.campaign_error)}</p>` : '') + render(state, slug, now)
    }

    const api = { selected_campaign, shows_weekly, render_timer, content, render_system, render_pilots, STACK_FACES }
    if (node) module.exports = api
    else root.campaign_view = api
})(this)
