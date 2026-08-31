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
 * Converts a number to a string with a suffix (k, M, B, T).
 * @param num The number to format
 * @param digits The number of decimal places to keep
 */ 
export function format_number(num: number, digits: number = 1): string {
    const lookup = [
        { value: 1, symbol: "" },
        { value: 1e3, symbol: "k" },
        { value: 1e6, symbol: "M" },
        { value: 1e9, symbol: "B" },
        { value: 1e12, symbol: "T" },
        { value: 1e15, symbol: "P" },
        { value: 1e18, symbol: "E" }
    ];

    const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;
    const item = lookup.slice().reverse().find((item) => {
        return num >= item.value;
    });

    return item 
        ? (num / item.value).toFixed(digits).replace(rx, "$1") + item.symbol 
        : "0";
}

export function format_isk(isk: number): string {
    const abs = Math.abs(isk)
    if (abs >= 1_000_000_000_000)
        return `${(isk / 1_000_000_000_000).toFixed(2)}T`
    if (abs >= 1_000_000_000)
        return `${(isk / 1_000_000_000).toFixed(1)}B`
    if (abs >= 1_000_000)
        return `${(isk / 1_000_000).toFixed(0)}M`
    if (abs >= 1_000)
        return `${(isk / 1_000).toFixed(0)}K`
    return isk.toFixed(0)
}

export function format_volume_m3(volume: number): string {
    if (!Number.isFinite(volume))
        return '0'
    return format_number(volume)
}

export function format_hours(hours: number): string {
    if (!Number.isFinite(hours))
        return '0'
    const rounded = Math.round(hours * 10) / 10
    if (Number.isInteger(rounded))
        return String(rounded)
    return rounded.toFixed(1)
}