// Copies of the inline globals src/components/partials/FooterScripts.astro
// defines for Alpine (`x-data="edge_fade()"`, `neocom_clock()`). Storybook
// can't render that Astro partial, so the preview loads these instead;
// testing/rust/site_globals.test.ts fails when they drift from the originals.

// --- from FooterScripts.astro ---
    function neocom_clock() {
        return {
            time: new Date(),
            init() {
                setInterval(() => {
                    this.time = new Date()
                }, 1000)
            },
            getTime() {
                let hour = this.time.getUTCHours()
                let minute = this.time.getUTCMinutes()

                return `${hour < 10 ? '0' : ''}${hour}:${minute < 10 ? '0' : ''}${minute}`
            },
        }
    }

// --- from FooterScripts.astro ---
    // Must live in FooterScripts: ClientRouter inits x-data before page-local scripts run.
    if (!window.edge_fade) {
        window.edge_fade = function () {
            return {
                init() {
                    const el = this.$el;
                    const update = () => {
                        el.classList.toggle('fade-start', el.scrollLeft > 0);
                        el.classList.toggle('fade-end', el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
                    };
                    update();
                    el._xfade_ro = new ResizeObserver(update);
                    el._xfade_ro.observe(el);
                    if (el.firstElementChild) el._xfade_ro.observe(el.firstElementChild);
                    el.addEventListener('scroll', update, { passive: true });
                },
            };
        };
    }
