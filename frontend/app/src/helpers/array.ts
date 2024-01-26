export const tokenize = (array:any[], key:string) => {
    const result = {};
    for (var i in array) {
        var item = array[i];

        /*if (
            item.effectID != 11 &&
            item.effectID != 12 &&
            item.effectID != 13 &&
            item.effectID != 2663 &&
            item.effectID != 3772 &&
            item.effectID != 6306
        )
            continue*/

        result[item[key]] = item;
    }

    return result;
}

export const group_by = (list:any[], key:any) => {
    let result = {};

    list.forEach((item:any) => {
        if (!result[item[key]])
            result[item[key]] = []

        result[item[key]].push(item)
    })

    return result
}

export const semantic_list = (locale = 'en-US', list:string[]):string => {
    return new Intl.ListFormat(locale, {
        style: 'long',
        type: 'conjunction',
    }).format(list)
}