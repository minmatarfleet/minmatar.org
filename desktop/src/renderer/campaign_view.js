// The Campaigns window's content as HTML: one row per system and the faces of the pilots active in the
// last hour. Pure functions of main's state (campaign, campaign_error, campaign_updated_at); campaigns.js
// wires events, the tooltip and the bar geometry. Shared by the window (global `campaign_view`) and the
// node tests (module.exports).
(function (root) {
    const node = typeof module !== 'undefined' && module.exports
    const { esc, portrait } = node ? require('./ui_helpers') : root.ui_helpers
    const { change_tone, change_text, bar, activity_text, flip_tone, row_title, PERIODS, SHORT_PERIODS, FLIPS, FLIP_WORDS } = node ? require('./campaign_format') : root.campaign_format

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

    function render_skeleton() {
        return '<div class="campaign-heading"><span class="skeleton skeleton--short"></span></div>' +
            Array.from({ length: 3 }, () => '<div class="system system--skeleton" aria-hidden="true"><span></span><span class="skeleton"></span><span class="skeleton"></span><span></span></div>').join('')
    }

    function render(state) {
        const campaign = state.campaign
        if (!campaign) {
            if (!state.campaign_updated_at && !state.campaign_error) return render_skeleton()
            return state.campaign_error ? '' : '<div class="eve-empty">No campaign is live right now.</div>'
        }
        const count = campaign.pilots.length
        return `<section class="campaign-group" aria-label="Systems">
            <div class="campaign-heading"><span>Systems</span><span class="eve-dim">Week ${campaign.week_index} of ${campaign.week_count}</span></div>
            ${campaign.systems.map(render_system).join('')}
        </section>
        <section class="campaign-group" aria-label="Active in the last hour">
            <div class="campaign-heading"><span>Active in the last hour</span><span class="eve-dim">${count} ${count === 1 ? 'pilot' : 'pilots'}</span></div>
            ${render_pilots(campaign)}
        </section>`
    }

    // Everything under the title bar: the error line (if any) above the systems and pilots.
    function content(state) {
        return (state.campaign_error ? `<p class="eve-error">${esc(state.campaign_error)}</p>` : '') + render(state)
    }

    const api = { content, render_system, render_pilots, STACK_FACES }
    if (node) module.exports = api
    else root.campaign_view = api
})(this)
