import { escape_html } from '@helpers/string'

export function formatChronicleText(text: string): string {
    const escaped = escape_html(text)

    return escaped.replace(/\*\*(.+?)\*\*/g, '<strong class="chronicle-mark">$1</strong>')
}

export function formatChronicleDescription(text: string): string {
    const separator = ' — '
    const separator_index = text.indexOf(separator)

    if (separator_index === -1) {
        return formatChronicleText(text)
    }

    const trait = text.slice(0, separator_index)
    const body = text.slice(separator_index + separator.length)

    return `<strong class="chronicle-mark">${escape_html(trait)}</strong> — ${formatChronicleText(body)}`
}
