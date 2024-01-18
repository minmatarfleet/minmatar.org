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