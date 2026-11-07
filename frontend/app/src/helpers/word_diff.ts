/**
 * A word diff for showing what changed between two texts, rendered on the
 * server (the Reddit approvals screen). Tokens are words and the whitespace
 * between them, so joining the parts of one side gives that text back.
 */

export type WordDiffKind = 'same' | 'add' | 'del'

export interface WordDiffPart {
    kind: WordDiffKind
    text: string
}

/** Past this many token pairs the LCS table is too big; show a whole replace instead. */
const MAX_CELLS = 4_000_000

function tokens(text: string): string[] {
    return text.match(/\s+|[^\s]+/g) ?? []
}

function push(parts: WordDiffPart[], kind: WordDiffKind, text: string) {
    if (!text) return
    const last = parts[parts.length - 1]
    if (last && last.kind === kind) last.text += text
    else parts.push({ kind, text })
}

/**
 * The parts that turn `before` into `after`: `same` text, `del` (only in
 * before) and `add` (only in after), in reading order.
 */
export function word_diff(before: string, after: string): WordDiffPart[] {
    const a = tokens(before ?? '')
    const b = tokens(after ?? '')

    // Trim the common start and end so the table covers only the changed middle.
    let start = 0
    while (start < a.length && start < b.length && a[start] === b[start]) start++
    let end_a = a.length
    let end_b = b.length
    while (end_a > start && end_b > start && a[end_a - 1] === b[end_b - 1]) {
        end_a--
        end_b--
    }

    const parts: WordDiffPart[] = []
    push(parts, 'same', a.slice(0, start).join(''))

    const mid_a = a.slice(start, end_a)
    const mid_b = b.slice(start, end_b)
    const n = mid_a.length
    const m = mid_b.length

    if (n === 0 || m === 0 || n * m > MAX_CELLS) {
        push(parts, 'del', mid_a.join(''))
        push(parts, 'add', mid_b.join(''))
    } else {
        // lcs[i][j]: longest common subsequence of mid_a[i..] and mid_b[j..].
        const width = m + 1
        const lcs = new Uint32Array((n + 1) * width)
        for (let i = n - 1; i >= 0; i--) {
            for (let j = m - 1; j >= 0; j--) {
                lcs[i * width + j] = mid_a[i] === mid_b[j]
                    ? lcs[(i + 1) * width + j + 1] + 1
                    : Math.max(lcs[(i + 1) * width + j], lcs[i * width + j + 1])
            }
        }
        let i = 0
        let j = 0
        while (i < n && j < m) {
            if (mid_a[i] === mid_b[j]) {
                push(parts, 'same', mid_a[i])
                i++
                j++
            } else if (lcs[(i + 1) * width + j] >= lcs[i * width + j + 1]) {
                push(parts, 'del', mid_a[i++])
            } else {
                push(parts, 'add', mid_b[j++])
            }
        }
        push(parts, 'del', mid_a.slice(i).join(''))
        push(parts, 'add', mid_b.slice(j).join(''))
    }

    push(parts, 'same', a.slice(end_a).join(''))
    return absorb_whitespace(parts)
}

/**
 * A lone space kept as `same` between two changes reads as noise
 * ("(now with cake)" split into three marks); fold it into the change.
 */
function absorb_whitespace(parts: WordDiffPart[]): WordDiffPart[] {
    const out: WordDiffPart[] = []
    parts.forEach((part, index) => {
        const prev = parts[index - 1]
        const next = parts[index + 1]
        if (
            part.kind === 'same' && /^[ \t]+$/.test(part.text)
            && prev && next && prev.kind !== 'same' && next.kind !== 'same'
        ) {
            // Belongs to both sides: emit as del + add so each side keeps it.
            push(out, 'del', part.text)
            push(out, 'add', part.text)
            return
        }
        push(out, part.kind, part.text)
    })
    return regroup(out)
}

/** Put every run of changes as all deletions, then all additions. */
function regroup(parts: WordDiffPart[]): WordDiffPart[] {
    const out: WordDiffPart[] = []
    let dels = ''
    let adds = ''
    const flush = () => {
        push(out, 'del', dels)
        push(out, 'add', adds)
        dels = ''
        adds = ''
    }
    for (const part of parts) {
        if (part.kind === 'del') dels += part.text
        else if (part.kind === 'add') adds += part.text
        else {
            flush()
            push(out, 'same', part.text)
        }
    }
    flush()
    return out
}

/** True when the two texts differ at all. */
export function has_changes(parts: WordDiffPart[]): boolean {
    return parts.some((part) => part.kind !== 'same')
}
