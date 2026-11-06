/** Helpers for the author/moderator partials that post plain HTML forms. */

export interface ManageFlashState {
    kind: 'success' | 'error'
    message: string
}

export const form_text = (form: FormData, key: string): string => String(form.get(key) ?? '').trim()

export const form_flag = (form: FormData, key: string): boolean => form.get(key) === 'on'

export const form_lines = (form: FormData, key: string): string[] =>
    form_text(form, key)
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)

export const form_int = (form: FormData, key: string): number | null => {
    const value = parseInt(form_text(form, key))
    return Number.isNaN(value) ? null : value
}

/** The backend's `detail` for a refused write, or the fallback. */
export const error_text = (error: unknown, fallback: string): string =>
    error instanceof Error && error.message ? error.message : fallback

/** `Gunnery 5` lines to skill rows; lines that do not end in a level 1-5 are returned as `invalid`. */
export function parse_skill_lines(lines: string[]): { skills: { name: string; level: number }[]; invalid: string[] } {
    const skills: { name: string; level: number }[] = []
    const invalid: string[] = []
    for (const line of lines) {
        const match = line.match(/^(.+?)\s+([1-5])$/)
        if (match) skills.push({ name: match[1], level: parseInt(match[2]) })
        else invalid.push(line)
    }
    return { skills, invalid }
}
