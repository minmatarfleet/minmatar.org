function escapeHtml(text: string): string {
    return text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
}

export function formatChronicleText(text: string): string {
    const escaped = escapeHtml(text)

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

    return `<strong class="chronicle-mark">${escapeHtml(trait)}</strong> — ${formatChronicleText(body)}`
}
