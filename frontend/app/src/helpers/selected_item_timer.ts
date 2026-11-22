/**
 * Reads a timer out of the text copied from EVE's Selected Item window:
 *
 *     Amamake - Cylinder Must Remain Unharmed
 *     8.6 AU
 *     Anchoring until 2026.11.22 00:41:49
 *
 * Skyhooks and customs offices copy as `Name (Location) [Owner]` instead of
 * `System - Name`. Anything we cannot read comes back empty, so the pilot
 * fills it in by hand on the Check step.
 */

export interface SelectedItemTimer {
    system_name:        string;
    name:               string;
    /** anchoring | unanchoring, or '' when the client says Reinforced (armor or hull: the pilot picks). */
    state:              string;
    /** YYYY-MM-DD in EVE time. */
    date:               string;
    /** HH:MM:SS in EVE time. */
    time:               string;
    corporation_name:   string;
    structure_type:     string;
}

const STATE_WORDS: Record<string, string> = {
    anchoring: 'anchoring',
    unanchoring: 'unanchoring',
    reinforced: '',
}

// The location of a planet or moon is the system, then a roman numeral and maybe a moon.
const PLANET_SUFFIX = / [IVXLC]+( - Moon \d+)?$/

const TYPE_HINTS: [RegExp, string][] = [
    [/^Orbital Skyhook\b/i, 'orbital_skyhook'],
    [/^(Customs Office|Player-Owned Customs Office)\b/i, 'player_owned_customs_office'],
    [/^Mercenary Den\b/i, 'mercenary_den'],
]

export const parse_selected_item_timer = (text: string): SelectedItemTimer => {
    const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
    const parsed: SelectedItemTimer = { system_name: '', name: '', state: '', date: '', time: '', corporation_name: '', structure_type: '' }
    if (lines.length === 0) return parsed

    const first = lines[0]
    const bracketed = first.match(/^(.+?) \((.+)\) \[(.+)\]$/)
    if (bracketed) {
        const [, name, location, owner] = bracketed
        parsed.name = `${name} (${location})`
        parsed.system_name = location.replace(PLANET_SUFFIX, '')
        parsed.corporation_name = owner
        parsed.structure_type = TYPE_HINTS.find(([pattern]) => pattern.test(name))?.[1] ?? ''
    } else {
        const dash = first.indexOf(' - ')
        if (dash > 0) {
            parsed.system_name = first.slice(0, dash)
            parsed.name = first.slice(dash + 3)
        } else {
            parsed.name = first
        }
    }

    for (const line of lines.slice(1)) {
        const timer = line.match(/^(\w+) until (\d{4})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2})(?::(\d{2}))?/i)
        if (!timer) continue
        const [, word, year, month, day, hour, minute, second] = timer
        parsed.state = STATE_WORDS[word.toLowerCase()] ?? ''
        parsed.date = `${year}-${month}-${day}`
        parsed.time = `${hour}:${minute}:${second ?? '00'}`
        break
    }

    return parsed
}

/** The ISO instant for a date and time in EVE time (UTC), or null when either is missing or invalid. */
export const eve_time_iso = (date: string, time: string): string | null => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}(:\d{2})?$/.test(time)) return null
    const instant = new Date(`${date}T${time.length === 5 ? `${time}:00` : time}Z`)
    return Number.isNaN(instant.getTime()) ? null : instant.toISOString()
}
