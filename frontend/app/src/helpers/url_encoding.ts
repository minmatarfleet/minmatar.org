// A standard Base62 alphabet (0-9, a-z, A-Z)
const CHARSET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';

function to_base62(bigint) {
    let str = '';
    while (bigint > 0n) {
        str = CHARSET[Number(bigint % 62n)] + str;
        bigint /= 62n;
    }
    return str || '0';
}

function from_base62(str) {
    return str.split('').reduce((acc, char) => 
        acc * 62n + BigInt(CHARSET.indexOf(char)), 0n);
}

/**
 * ENCODE
 * Packs 3 IDs into a Base62 string.
 * Allocation: 24 bits each = 72 bits total.
 */
export function encode_query(order_id, item_id, assign_id) {
    const packed = (BigInt(order_id) << 48n) | 
                   (BigInt(item_id) << 24n) | 
                   BigInt(assign_id);
    return to_base62(packed);
}

/**
 * DECODE
 * Unpacks the Base62 string back into the original 3 IDs.
 */
export function decode_query(q) {
    const unpacked = from_base62(q);
    return {
        order_id: Number((unpacked >> 48n) & 0xFFFFFFn),
        item_id: Number((unpacked >> 24n) & 0xFFFFFFn),
        assignment_id: Number(unpacked & 0xFFFFFFn)
    };
}