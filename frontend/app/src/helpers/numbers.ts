export const number_name = (val: number, locale:string) => {
    if (val < 1000)
        return '';

    const shorten_number:string = Intl.NumberFormat(
        locale,
        {
            notation: "compact",       
            compactDisplay: "long",
            maximumFractionDigits: 1
        }
    ).format(val)
    
    return `${is_approxixmation(shorten_number, val) ? '≈ ' : ''}${shorten_number}`;
}

function is_approxixmation(shorten_number:string, val:number):boolean {
    // Multiplying by 10 to remove floating point error
    return ( (10*val)%(10*parseFloat(shorten_number.split(' ')[0])) != 0 );
}

export const number_thousand_separator = (val: number, locale:string = 'en-US') => {
    return val.toLocaleString(locale, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    })
}

/**
 * Parse volume or similar numeric input with optional k/m/b shorthand.
 * e.g. "60k" -> 60000, "1.5m" -> 1500000, "50,000" -> 50000
 */
export function parseVolumeInput(value: string | null | undefined): number {
    const s = String(value ?? '').trim().toLowerCase().replace(/,/g, '')
    if (!s) return NaN
    const kMatch = s.match(/^([\d.]+)\s*k$/)
    if (kMatch) return Math.round(parseFloat(kMatch[1]) * 1_000)
    const mMatch = s.match(/^([\d.]+)\s*m$/)
    if (mMatch) return Math.round(parseFloat(mMatch[1]) * 1_000_000)
    const bMatch = s.match(/^([\d.]+)\s*b$/)
    if (bMatch) return Math.round(parseFloat(bMatch[1]) * 1_000_000_000)
    const n = parseFloat(s)
    return isNaN(n) ? NaN : Math.round(n)
}