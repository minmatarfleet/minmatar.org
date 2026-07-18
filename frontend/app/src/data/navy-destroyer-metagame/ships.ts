import type { ShipGuide } from './types'

export const catalystGuide: ShipGuide = {
    id: 'catalyst',
    name: 'Catalyst Navy Issue',
    shortName: 'CatNI',
    faction: 'Gallente',
    shipId: 73796,
    tagline: 'The warzone’s most flexible destroyer: blaster brawler and 10MN rail kiter in one hull.',
    bonuses: [
        { label: 'Small Hybrid Turret damage', value: '10%' },
        { label: 'Armor Repairer amount', value: '7.5%' },
        { label: 'Armor Plate mass penalty', value: '15% reduction' },
    ],
    roleBonus: '50% bonus to Small Hybrid Turret optimal range and falloff',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'High raw DPS, strong bulkhead-rig synergy, and two archetypes that cover each other’s weaknesses. The brawler plays like a Federation Navy Comet with a better slot layout: double web and scram for range control. The kiter is an overpropped 10MN rail platform that stat-checks many matchups if you accept slower plexing.',
            ],
        },
        {
            id: 'blaster',
            title: 'Blaster brawl',
            paragraphs: [
                'Primary fit: plate + web + scram (example fit below). Plate brings buffer EHP but loses to cap warfare.',
                'Up close the blaster CatNI wins most scram fights if you land scram and web on entry. It loses to anything that can kite or scram-kite you (AC Thrasher is the classic example).',
            ],
            bullets: [
                'Refit — SAAR Web Scram: swap plate for SAAR + nos. Faster and more flexible, thinner buffer. Same role; pick for cap fights and active-tank preference.',
                'Optional pocket upgrades (not separate fits): plate + SAAR with cap inject and small neut, fewer bulkheads for more damage, or Ion blasters.',
            ],
        },
        {
            id: 'rail',
            title: '10MN rail kiter',
            paragraphs: [
                'Primary fit: overpropped 10MN with 150 mm gauss (example fit below). Overprop lets you slide safely against scrams. Best for pilots who care more about kills than plex efficiency.',
                'Web-kite at 10-15 km and watch capacitor. Snake and Genos implants pay for themselves here.',
            ],
            bullets: [
                'Refit — 10mn 125mm: T2 125 mm rails + disruptor. Harder to catch, lower raw DPS. Same kite role; use when you want tracking and escape over alpha.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Blasters',
            fitContext: 'Ignoring kiting fits. Brawler vs brawler lines.',
            entries: [
                { opponent: 'Coercer Navy brawl pulse', load: 'Void', verdict: 'favoured', advice: 'Approach, F1, orbit 500. Good fight.' },
                { opponent: 'Coercer Navy brawl double neut', load: 'Void', verdict: 'unfavoured', advice: 'Double-neut Coercer DPS is awful, but the cap wall is real. With a nos you might steal it, but most likely you lose.' },
                { opponent: 'AC TFI with web', load: 'Void', verdict: 'skill', advice: 'With high ground, hug the beacon and land scram + web: you win. On a slide, or if they establish scram-kite range, you are probably dead.' },
                { opponent: 'AC TFI without web', load: 'Void', verdict: 'favoured', advice: 'Approach, F1, orbit 500.' },
                { opponent: 'Cormorant Navy dual MASB', load: 'Null', verdict: 'unfavoured', advice: 'Straight stat check: you lose if they rep well. Scram-kite with Null; if they swap to Null, ram back in on a Void reload.' },
                { opponent: 'Cormorant Navy buffer', load: 'Null', verdict: 'favoured', advice: 'Stat check in your favour. Scram-kite with Null.' },
                { opponent: 'Blaster CatNI mirror', load: 'Null', verdict: 'skill', advice: 'Scram-kite: they likely have Void loaded. Force a reload, or bait Null and ram on Void.' },
                { opponent: '10MN rail CatNI', load: 'Void', verdict: 'even', advice: 'Approach, F1, heat prop. If it turns bad, burn opposite: they struggle to keep point.' },
            ],
        },
        {
            title: '10MN rail',
            fitContext: 'Web-kiter at 10-15 km.',
            entries: [
                { opponent: 'Coercer Navy brawl pulse', verdict: 'favoured', advice: 'Stay out of Conflag and neut range; hold Antimatter range. Stat-check win: they cannot hold you, so leave anytime.' },
                { opponent: 'Coercer Navy double neut', verdict: 'favoured', advice: 'Get out of neut range immediately.' },
                { opponent: 'Beam / locus pulse Coercer', verdict: 'unfavoured', advice: 'Very bad. Punching a beam Coercer at 20 km gets you deleted.' },
                { opponent: 'AC TFI with web', verdict: 'skill', advice: 'Heat AB and pray they are mediocre: otherwise you get munched. With high ground, make them crawl into Hail range as long as possible.' },
                { opponent: 'AC TFI without web', verdict: 'favoured', advice: 'Range control vs a close-range weapon: you are fine.' },
                { opponent: '5MN arty TFI', verdict: 'favoured', advice: 'Stat-check win, but you will not hold them: agility gap.' },
                { opponent: '1MN dual-web arty TFI', verdict: 'bail', advice: 'Align out and warp.' },
                { opponent: 'Blaster CatNI', verdict: 'unfavoured', advice: 'They run you down. Heat prop and pray; with high ground, make them crawl to you first.' },
                { opponent: '10MN rail CatNI mirror', load: 'Antimatter', verdict: 'even', advice: 'Neither holds the other well. Ram with Antimatter: heat, skills, and drugs decide it.' },
                { opponent: 'Dual MASB Corm', verdict: 'favoured', advice: 'Range control: easy win.' },
                { opponent: 'Buffer Corm', verdict: 'favoured', advice: 'Same as blaster CatNI but easier: slower, less EHP.' },
            ],
        },
    ],
}

export const coercerGuide: ShipGuide = {
    id: 'coercer',
    name: 'Coercer Navy Issue',
    shortName: 'CoercerNI',
    faction: 'Amarr',
    shipId: 73789,
    tagline: 'Peak laser DPS and neut pressure: held back by two mids and slow speed.',
    bonuses: [
        { label: 'Ship armor hitpoints', value: '7.5%' },
        { label: 'Small Energy Turret damage', value: '7.5%' },
        { label: 'Small Energy Turret activation cost', value: '10% reduction' },
        { label: 'Energy Neutralizer activation cost', value: '10% reduction' },
        { label: 'Energy Neutralizer strength', value: '10%' },
    ],
    roleBonus: '50% bonus to Small Energy Turret optimal range and falloff',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Massive tank bonus, best-in-class small lasers, and a huge neut bonus: almost the peak destroyer. Two mids, second-slowest speed in class (Cormorant is slower), and an armor-bonus hull mean you usually lose range control in brawls. You win blaster fights with neuts and kiters with Scorch projection.',
            ],
        },
        {
            id: 'dual-neut',
            title: 'Dual-neut brawl',
            paragraphs: [
                'Primary fit: dual neuts + MWD (example fit below). Double neut trades a gun for cap warfare: with hull bonus, two neuts drain like three unbonused smalls and cap out most destroyers in a couple of heated cycles.',
            ],
            bullets: [
                'Do not cap yourself: turn off one neut after 2-3 heated cycles.',
                'Neut range is short: hug at 2-3 km. If they escape neut range and you are on Scorch, you are probably losing the DPS race.',
                'Refit — Dual Neuts No Prop: drop prop for web + locus. Scorch reaches point range; kiters slide on you freely. Use when you expect a straight brawl, not a chase.',
            ],
        },
        {
            id: 'brawl-variants',
            title: 'Pulse scram brawl',
            paragraphs: [
                'Primary fit: MWD scram brawl with a full pulse rack (example fit below). Pure DPS without the neut trump card: Scorch projection still helps vs kiters at point, but blaster brawlers can win the straight fight.',
                'Keep at least one neut on any Coercer brawl you invent yourself: otherwise an AB + web frigate orbits you to death.',
            ],
            bullets: [
                'Refit — AB Scram Brawl: afterburner instead of MWD for tighter range control and no MWD sig bloom. Same brawl role.',
            ],
        },
        {
            id: 'kiting',
            title: 'Kiting (beam primary)',
            paragraphs: [
                'Primary fit: beam kiter with tracking enhancer (example fit below). Better at kiting ranges despite tracking. X-Ray (~20 km), Gamma (~17 km), Multifreq (~13 km) DPS bands. CPU-tight: storyline point, Geno pod, rolled heatsinks, event boosters all help.',
            ],
            bullets: [
                'Refit — Locus Pulse: pulse guns + locus rigs. Do not punch into a plex to brawl: sit inside and delete entrants at point range.',
                'Refit — Web Beams: dual web, no point/scram. Hold 8-9 km off the beacon for tracking. Meme build: if they get under your guns you are in trouble.',
            ],
        },
        {
            id: 'upgrades',
            title: 'Upgrades',
            paragraphs: [
                'Genos / Amulets are the easy win. Mutaplasmids on meta neuts are cheap; spare PG (and CPU on the no-prop fit) helps good rolls.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Dual neuts',
            fitContext: 'Ignoring kiting fits.',
            entries: [
                { opponent: 'Coercer Navy brawl', verdict: 'favoured', advice: 'Heat neuts: win the cap war.' },
                { opponent: 'AC TFI (web or not)', verdict: 'skill', advice: 'Heat neuts to stay in range; watch the DPS race; warp if losing.' },
                { opponent: 'Cormorant Navy (MASB or buffer)', verdict: 'favoured', advice: 'Easy: they cannot fight neuts.' },
                { opponent: 'Blaster CatNI', verdict: 'favoured', advice: 'Stay in neut range even through a nos.' },
                { opponent: '10MN rail CatNI', verdict: 'unfavoured', advice: 'Hard. MWD in for optimal neut range; cap management is everything.' },
            ],
        },
        {
            title: 'Regular brawl',
            fitContext: 'Pulse brawler: not the dual-neut line.',
            entries: [
                { opponent: 'Coercer Navy brawl', load: 'Conflag', verdict: 'even', advice: 'Ram, heat, let the dice roll.' },
                { opponent: 'Coercer Navy dual neuts', verdict: 'unfavoured', advice: 'Probably losing: counterneut, align out; cap pressure makes tackle slip.' },
                { opponent: 'AC TFI shield, no web', verdict: 'favoured', advice: 'Easy stat check.' },
                { opponent: 'AC TFI armor + web', verdict: 'even', advice: 'Coinflip on fit. Orbit = Multifrequency; range = Conflag + heat.' },
                { opponent: 'Arty TFI (outside scram)', load: 'Scorch', verdict: 'even', advice: 'You can often force them out with Scorch: keep moving, make them turn risky to hold point.' },
                { opponent: 'Cormorant dual MASB', load: 'Conflag', verdict: 'unfavoured', advice: 'Lose if they reach blaster range. Start at edge of Conflag range.' },
                { opponent: 'Cormorant buffer', load: 'Conflag', verdict: 'unfavoured', advice: 'Paper win possible; close orbit = toast. Start away from beacon.' },
                { opponent: 'Blaster CatNI', verdict: 'unfavoured', advice: 'Straight stat check: you lose.' },
                { opponent: '10MN rail CatNI', verdict: 'unfavoured', advice: 'Never hold in Conflag; Scorch vs Antimatter DPS race, and they leave whenever they want.' },
            ],
        },
        {
            title: 'Kiting',
            fitContext: 'Beam, pulse, or locus: with high ground.',
            entries: [
                { opponent: 'All brawl fits', verdict: 'favoured', advice: 'Kite them: do not get caught; heat prop correctly. Swap ammo as needed.' },
                { opponent: 'All kiting fits', verdict: 'favoured', advice: 'Nothing matches your DPS/EHP at point range with high ground.' },
                { opponent: 'Self (punching into plex)', verdict: 'unfavoured', advice: 'If you get bored and slide in, expect to die when someone scrams you correctly.' },
            ],
        },
    ],
}

export const thrasherGuide: ShipGuide = {
    id: 'thrasher',
    name: 'Thrasher Fleet Issue',
    shortName: 'TFI',
    faction: 'Minmatar',
    shipId: 73794,
    tagline: 'Bad on paper, popular in the cockpit: speed, alpha, and sig bloom for manual pilots.',
    bonuses: [
        { label: 'Small Projectile Turret damage', value: '5%' },
        { label: 'Small Projectile Turret rate of fire', value: '5%' },
        { label: 'Microwarpdrive signature radius penalty', value: '15% reduction' },
    ],
    roleBonus: '50% bonus to Small Projectile Turret optimal range and falloff',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Worst navy destroyer on paper in many 1v1 charts: most loved in the cockpit anyway. Minmatar roleplay, 280 mm alpha dopamine, or MWD sig-reduction for manual piloting: pick your poison. Excellent for punching up and down; underwhelming in pure destroyer mirrors.',
            ],
        },
        {
            id: '280-kite',
            title: '280 mm artillery kiter',
            paragraphs: [
                'Primary fit: Arty TFI (example fit below). The default TFI. 280s are hard to fit but projection wins kiting matchups. You lose to 10MN rail CatNI and beam/pulse CoercerNI on chart: but you are MUCH faster. Disengage losing fights; slide on brawlers with a reasonable (not guaranteed) scram escape.',
            ],
            bullets: [
                'PG problem: 3 lows + 2 mids + compact MWD needs 0.9 PG you do not have: ACR rig or overdrive/nano in lows.',
                'TD instead of web helps vs CoercerNI and CatNI (Genos + Pyfa). Sig bonus helps orbit + web.',
                'Refit — 280mm ACR: meta MWD/gyro/rig polish on the same kite frame. Prefer this once you are comfortable with 280s.',
                'Refit — 280 Overdrive: simpler/faster entry 280. More speed, less alpha than ACR.',
                'Refit — 280 Double Web: AB + dual web meme. Punches kiters who assume you are a 5MN kite; no point means they can warp.',
            ],
        },
        {
            id: 'ac-brawl',
            title: 'Autocannon brawl',
            paragraphs: [
                'Primary fit: armor AC TFI (example fit below). Scram-kite vs blaster-heavy hulls; open by kiting, commit to brawl range only when ready.',
            ],
            bullets: [
                'Refit — Shield ACs: MSE + neut instead of plate/rocket. More speed and buffer mobility; loses some EHP and range control vs CatNI/CormNI. AB + web frigates hurt unless the neut lands.',
            ],
        },
    ],
    matchups: [
        {
            title: '5MN 280 mm',
            fitContext: 'Hull-tank artillery kiter.',
            entries: [
                { opponent: '10MN CatNI', load: 'Fusion', verdict: 'unfavoured', advice: 'Stat-check loss: they outrun your tracking abuse and out-EHP/out-DPS you. Dip when it is over.' },
                { opponent: 'Pulse / beam kiting CoercerNI', load: 'Fusion', verdict: 'unfavoured', advice: 'Web + transversal is your only shot. Punching a setup kiter: heat away and leave.' },
                { opponent: 'Brawling CoercerNI', load: 'Fusion', verdict: 'skill', advice: 'Focused pulse: orbit at point edge: they usually force you out. Dual light: dead past 17 km: keep moving.' },
                { opponent: 'CormNI', load: 'EMP', verdict: 'favoured', advice: 'Little they can do sliding in. Even scrammed, 280 alpha + web often kills active tank.' },
                { opponent: '280 mm TFI mirror', load: 'Plasma', verdict: 'even', advice: 'Heat everything: hit quality decides it.' },
            ],
        },
        {
            title: 'Shield ACs',
            fitContext: 'Excluding kiting fits.',
            entries: [
                { opponent: 'General 1v1', verdict: 'unfavoured', advice: 'Terrible solo fit: heat, F1, pray. High ground: Barrage-kite CatNI/CormNI, then Hail commit (never kite a CoercerNI). Reliable win: other TFIs: ammo coinflip.' },
            ],
        },
        {
            title: 'Armour ACs',
            fitContext: 'Excluding kiting fits.',
            entries: [
                { opponent: 'Blaster CatNI', load: 'Hail', verdict: 'skill', advice: 'Stressful: they close to Void. Scram around 8 km; on slide start 10 km out and burn as lock lands.' },
                { opponent: '10MN CatNI', load: 'Hail', verdict: 'unfavoured', advice: 'Far from beacon vs 10MN = unwinnable (same speed, web both, they out-DPS outside Hail). Intel says 10MN: hug beacon, preload Hail, heat MWD cycle 2 (cycle 1 they are slower). Far start vs 10MN: leave.' },
                { opponent: 'CoercerNI', load: 'Hail', verdict: 'even', advice: 'Keep ~1500 m. Coinflip on their tank spec (exp/kin vs not).' },
                { opponent: 'CormNI brawl', verdict: 'unfavoured', advice: 'No range control, cannot scram-kite their optimal bonus, cannot Hail through shield: avoid.' },
                { opponent: 'AC TFI mirror', load: 'Hail', verdict: 'even', advice: 'Sad coinflip without scout. Hail covers armor; shield opponents kill you anyway (extra gyro + 15% Hail). No web on them: align, heat web, pray scram drops before you pop.' },
            ],
        },
    ],
}

export const cormorantGuide: ShipGuide = {
    id: 'cormorant',
    name: 'Cormorant Navy Issue',
    shortName: 'CormNI',
    faction: 'Caldari',
    shipId: 73795,
    tagline: 'Slow and narrow: but at brawl range it stat-checks most of the class.',
    bonuses: [
        { label: 'Small Hybrid Turret damage', value: '5%' },
        { label: 'Small Hybrid Turret optimal range', value: '10%' },
        { label: 'Shield Booster amount', value: '10%' },
    ],
    roleBonus: '50% bonus to Small Hybrid Turret optimal range and falloff',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Opposite of the TFI: often the most disliked navy destroyer. Too slow to kite at point; built for sniping in theory. Regular Cormorant is cheaper (~20M) for pure snipe. Shield-booster bonus is slot-inefficient: one MASB is not enough tank; MSB needs cap inject and eats mids.',
                'Redeeming quality: brawl range. Tank + damage stack high; optimal bonus resists scram-kite. AB over MWD for range control and double-MASb fitting room.',
            ],
        },
        {
            id: 'dual-masb',
            title: 'Dual MASB brawl',
            paragraphs: [
                'Primary fit: dual MASB neutrons (example fit below). Standard blue pill (or improved) + hardshell. MG-Crystal pod is cost-effective; skip abyssals: tight fit, MASBs are hard to roll.',
            ],
            bullets: [
                'Refit — Dual MASB Ions: same burst-shield brawl with ions for slightly more reach. Pick neutrons or ions to taste; not a different role.',
            ],
        },
        {
            id: 'buffer',
            title: 'Buffer surprise',
            paragraphs: [
                'Ignore active-tank bonus; single MSE. Worse CatNI on paper: you play the surprise MWD + web angle. Snake pod + speed drug scrams kiters who thought you were slow. Lose brawl supremacy vs dual MASB lines; bling MSE required: do not cheap out.',
            ],
        },
        {
            id: '10mn-bling',
            title: '10MN / 75 mm bling',
            paragraphs: [
                'Anomaly on paper, strong in practice: 10MN + scram + active tank + 75 mm rails. Antimatter close, Iridium for kiters. Stat-check at scram; range control vs 5MN/web brawlers.',
            ],
            bullets: [
                'Terrible agility: 10MN range control is hard; easy to overshoot.',
                '100M+ ISK mostly Pithum C-type MSB.',
                'Blue pill, improved blue pill, hardshell, crystal pod: face-tanks most destroyers 1v1; blobbed once recognized.',
            ],
        },
    ],
    matchups: [
        {
            title: 'Dual MASB',
            fitContext: 'AB + double MASB brawler.',
            entries: [
                { opponent: 'CoercerNI dual neuts', verdict: 'unfavoured', advice: 'Neuted out: you die.' },
                { opponent: 'CoercerNI brawl', load: 'Void', verdict: 'favoured', advice: 'Close ASAP: you win. They kite: leave. High ground: easy.' },
                { opponent: 'CormNI dual MASB mirror', load: 'Null', verdict: 'even', advice: 'Scram-kite; hope they have Void loaded.' },
                { opponent: 'CormNI buffer', verdict: 'favoured', advice: 'Easier than MASB mirror.' },
                { opponent: 'Blaster CatNI', load: 'Void', verdict: 'favoured', advice: 'Hug them: stat check.' },
                { opponent: '10MN CatNI', verdict: 'unfavoured', advice: 'They kite you to death.' },
                { opponent: 'TFI ACs', load: 'Void', verdict: 'favoured', advice: 'Stat check.' },
                { opponent: 'TFI 1MN dual-web arty', verdict: 'bail', advice: 'Align out and warp.' },
                { opponent: 'TFI 5MN arty', load: 'Void', verdict: 'skill', advice: 'Win if you scram: watch reps, arty alpha hurts.' },
            ],
        },
        {
            title: 'Buffer',
            fitContext: 'MSE + MWD surprise brawler.',
            entries: [
                { opponent: 'CoercerNI dual neuts', verdict: 'unfavoured', advice: 'Neuted out: you die.' },
                { opponent: 'CoercerNI brawl', load: 'Void', verdict: 'favoured', advice: 'Close ASAP: you win.' },
                { opponent: 'CormNI dual MASB', verdict: 'unfavoured', advice: 'Stat check: you lose.' },
                { opponent: 'CormNI buffer mirror', load: 'Null', verdict: 'even', advice: 'Scram-kite.' },
                { opponent: 'Blaster CatNI', load: 'Null', verdict: 'unfavoured', advice: 'Better CatNI (faster, more EHP). Trick win: Null scram-kite, Void ram on their Null reload.' },
                { opponent: '10MN CatNI', verdict: 'even', advice: 'Can run them down: close, depends on start range.' },
                { opponent: 'TFI ACs', load: 'Void', verdict: 'favoured', advice: 'Hug them: easy win.' },
                { opponent: 'TFI 1MN dual-web', verdict: 'bail', advice: 'Align out and warp.' },
            ],
        },
        {
            title: '10MN 75 mm',
            fitContext: 'Pithum MSB + cap booster bling line.',
            entries: [
                { opponent: 'CoercerNI dual neuts', verdict: 'skill', advice: 'Leave neut range fast: heat AB, heat cap inject, ease off reps (-1 gun hurts their DPS). Manual orbit ~8 km once clear.' },
                { opponent: 'CoercerNI brawl', verdict: 'even', advice: 'Manual orbit at scram edge: spicy vs best DPS type into you.' },
                { opponent: 'CoercerNI beam / pulse kite', verdict: 'unfavoured', advice: 'Dead unless heavily blinged (crystal pod): trans-match beam DPS wins.' },
                { opponent: '5MN arty TFI', verdict: 'favoured', advice: 'Perfect hits needed to break tank: pepper with Thorium/Iridium; they leave without scram.' },
                { opponent: 'AC TFI', load: 'Antimatter', verdict: 'favoured', advice: 'Scram range: nothing they can do.' },
                { opponent: 'CormNI brawl', verdict: 'favoured', advice: 'Scram-kite: you have range control.' },
                { opponent: '10MN CatNI', verdict: 'favoured', advice: 'Cannot break your tank: cannot hold them either.' },
                { opponent: 'Blaster CatNI', load: 'Antimatter', verdict: 'favoured', advice: 'Scram range: easy win.' },
            ],
        },
    ],
}

export const talwarGuide: ShipGuide = {
    id: 'talwar',
    name: 'Talwar Fleet Issue',
    shortName: 'TalFI',
    faction: 'Minmatar',
    shipId: 91858,
    tagline: 'Brand-new rocket brawler: scram-range burst with 10MN range control, still finding its place in the metagame.',
    bonuses: [
        { label: 'Light Missile and Rocket rate of fire', value: '7.5%' },
        { label: 'Shield Operation amount', value: '7.5%' },
        { label: 'Light Missile and Rocket explosion velocity', value: '7.5%' },
    ],
    roleBonus: '50% bonus to Light Missile and Rocket max velocity',
    sections: [
        {
            id: 'overview',
            title: 'Overview',
            paragraphs: [
                'Released with Cradle of War (YC 128), the Talwar Fleet Issue is the newest hull in the navy destroyer lineup. Solo meta is still being defined: pilots are experimenting, and most matchup charts below are early reads rather than settled wisdom.',
                'The standout solo line so far is a 10MN afterburner rocket brawler. Five launchers, MASB burst tank, and scram range control let you stat-check many classic MWD + scram + web destroyers. It is harder to fly than the numbers suggest because 10MN range control takes practice.',
                'Light-missile fleet fits exist but early reports are poor: the hull wants to be up close with rockets, not orbiting at missile falloff in a gang.',
            ],
        },
        {
            id: '10mn-rocket',
            title: '10MN rocket brawl',
            paragraphs: [
                'Dato Koppla\'s line: Navy MAPC, BCS, DC in lows; 10MN AB, scram, MASB, and multispec hardener in mids; five rocket launchers with Scourge Rage. Bay loading accelerator and shield resist rigs push alpha.',
                'Strengths: beats most autocannon TFIs, blaster Catalyst Navy Issues, and Cormorant Navy brawlers if you land scram and manage the 10MN slide. Coercer Navy Issues with projection are awkward: their DPS at range is scary, but only two mids means you can usually bail if the fight turns.',
                'Weaknesses: beam and locus-pulse Coercer kiters, 10MN rail CatNIs, and artillery TFIs are still open questions. Cap and MASB timing matter; overheating the AB wrong leaves you scrammed at the wrong range.',
            ],
        },
    ],
    matchups: [
        {
            title: '10MN rocket',
            fitContext: 'Early solo meta. Ratings marked ? are still being tested.',
            entries: [
                { opponent: 'AC TFI with web', load: 'Scourge Rage', verdict: 'favoured', advice: 'Classic MWD + scram + web dessie line: you win most of these if you control the 10MN slide.' },
                { opponent: 'AC TFI without web', load: 'Scourge Rage', verdict: 'favoured', advice: 'Easier than the web variant: less range control against you once scram lands.' },
                { opponent: 'Blaster CatNI', load: 'Scourge Rage', verdict: 'favoured', advice: 'Another MWD brawler you can stat-check at scram range with good AB heat.' },
                { opponent: 'Cormorant Navy dual MASB', load: 'Scourge Rage', verdict: 'favoured', advice: 'Win the scram brawl if you keep them from establishing optimal blaster range on the slide.' },
                { opponent: 'Cormorant Navy buffer', load: 'Scourge Rage', verdict: 'favoured', advice: 'Same story as the MASB line: commit once scram is up.' },
                { opponent: 'Coercer Navy brawl pulse', load: 'Scourge Rage', verdict: 'skill', advice: 'Tough when they have Scorch projection, but only two mids: heat AB and leave if neut/scram pressure goes wrong.' },
                { opponent: 'Coercer Navy beam / locus kite', load: 'Scourge Rage', verdict: 'unfavoured', advice: 'Projection hurts. Two mids means you can usually disengage; do not punch into a setup kiter.' },
                { opponent: 'Coercer Navy dual neut', verdict: 'unknown', advice: 'Cap pressure vs burst tank is untested. Treat as ? until more fights land.' },
                { opponent: '10MN rail CatNI', verdict: 'unknown', advice: 'Both want range control with 10MN. No settled read yet.' },
                { opponent: '280 mm TFI kiter', verdict: 'unknown', advice: 'Alpha and web vs your AB and scram. Still collecting data.' },
                { opponent: 'TalFI mirror', verdict: 'unknown', advice: 'Too new for a reliable mirror line.' },
            ],
        },
    ],
}

export const shipGuides = [catalystGuide, coercerGuide, thrasherGuide, cormorantGuide, talwarGuide]
