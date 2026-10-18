import { ISK_COMPACT_ARCHIVE, format_compact } from '@helpers/numbers'

/** ISK for campaign retrospectives: 1.25T, 2.3B, 12M, 450K. */
export function formatIsk(isk: number): string {
    return format_compact(isk, ISK_COMPACT_ARCHIVE)
}
