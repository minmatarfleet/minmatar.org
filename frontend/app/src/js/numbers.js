const number_name = (val, locale) => {
    if (val == '')
        return;

    val = val.replace(/,/g, '');

    if (val < 1000)
        return '';

    return '≈ '+Intl.NumberFormat(
        locale,
        {
            notation: "compact",       
            compactDisplay: "long",
            maximumFractionDigits: 1
        }
    ).format(val);
}