export function cacheFn(fn) {
    var cache = {};

    return function(...arg) {
        var args = arguments
        var key = [].slice.call(args).join('')

        if(cache[key]) {
            console.log(`Cache hit: ${key}`)
            return cache[key]
        } else {
            cache[key] = fn.apply(this, args)
            return cache[key]
        }
    }
}