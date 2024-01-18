const number_name = (val, locale) => {
    if (val == '')
        return;

    val = val.replace(/,/g, '');

    if (val < 1000)
        return '';

    const shorten_number = Intl.NumberFormat(
        locale,
        {
            notation: "compact",       
            compactDisplay: "long",
            maximumFractionDigits: 1
        }
    ).format(val)
    
    return `${is_approxixmation(shorten_number, val) ? '≈ ' : ''}${shorten_number}`;
}

const isPowerOf10 = n => Math.log10(n) % 1 === 0;

function is_approxixmation(shorten_number, val) {
    return !isPowerOf10( val/parseFloat(shorten_number.split(' ')[0]) );
}