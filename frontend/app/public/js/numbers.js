window.number_name = window.number_name || function number_name(val, locale) {
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

window.isPowerOf10 = window.isPowerOf10 || function isPowerOf10(n) {
    return Math.log10(n) % 1 === 0;
};

function is_approxixmation(shorten_number, val) {
    return !window.isPowerOf10( val/parseFloat(shorten_number.split(' ')[0]) );
}

var number_name = window.number_name;
var isPowerOf10 = window.isPowerOf10;
