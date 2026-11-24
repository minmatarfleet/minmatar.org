// Copies of the inline globals src/components/partials/FooterScripts.astro
// defines (`x-data="edge_fade()"`, `neocom_clock()`, `play_sound()` /
// `launch_confetti()`). Storybook can't render that Astro partial, so the
// preview loads these (as a classic script, from .storybook/preview-head.html); testing/rust/site_globals.test.ts fails when
// they drift from the originals.

// --- from FooterScripts.astro ---
    window.__footer_confetti_canvas = window.__footer_confetti_canvas
        || document.getElementById("confetti-canvas");

    (async () => {
        const canvas = window.__footer_confetti_canvas;
        if (!canvas || typeof confetti === 'undefined')
            return;
        canvas.confetti = canvas.confetti || (await confetti.create(canvas, { resize: true }));
    })();

    function play_sound(filepath) {
        let sound = new Audio(filepath);
        // Rejects when the browser blocks autoplay (MINMATAR-FRONTEND-EM).
        sound.play().catch(() => {});

        sound.onended = function() {
            this.currentSrc = null;
            this.src = "";
            this.srcObject = null;
            this.remove();
        };
    }

    function launch_confetti(images) {
        const canvas = window.__footer_confetti_canvas;
        if (!canvas || !canvas.confetti)
            return;

        const sounds = [
            "1162202323502780416.ogg",
            "1162206878210723910.ogg",
            "1162207169584832512.ogg",
            "1162372932845179060.ogg",
            "1180238591381737482.ogg",
            "1185658748757356675.ogg",
            "1189627562859704340.ogg",
            "1189629201519755265.ogg",
            "1193306194295668886.ogg",
            "wow.mp3"
        ]
        
        const sound_filename = sounds[Math.floor(Math.random() * sounds.length)]
        play_sound(`/sounds/${sound_filename}`)
        
        canvas.confetti({
            startVelocity: 100,
            particleCount: 100,
            spread: 150,
            origin: { y: 0.9 },
            scalar: 5,
            shapes: ["image"],
            shapeOptions: {
                image: images,
            },
        })
    }

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
