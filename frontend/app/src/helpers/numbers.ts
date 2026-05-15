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