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

export const unique = (list:any[], key:any) => {
    return [...new Set(list.map(item => item[key]))]
}

export const unique_values = (list:any[]) => {
    return [...new Set(list)];
}

export const get_unique_by_key = (array, key) => {
    const unique_objects = array.reduce((acc, current) => {
        if (!acc.find(item => item[key] === current[key]))
            acc.push(current);

        return acc;
    }, []);

    return unique_objects;
}

export const semantic_list = (locale = 'en-US', list:string[]):string => {
    return new Intl.ListFormat(locale, {
        style: 'long',
        type: 'conjunction',
    }).format(list)
}

export const paginate = (array:any[], offset:number, length:number) => {
    return array.slice((offset - 1) * length, offset * length)
}