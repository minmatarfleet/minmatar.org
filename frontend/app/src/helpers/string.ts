export const remove_space = (text:string):string => {
    return text.replaceAll(" ", "_")
}

export const query_string = (params):URLSearchParams => {
    return new URLSearchParams(params)
}