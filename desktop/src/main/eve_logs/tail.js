// Incremental reader for a file another process keeps appending to.
//
// Windows notes that drive the design:
//  - EVE keeps each log open for the whole session. Directory change notifications and path-based
//    stat() can lag for open files, so we keep our own handle and fstat() it (the handle sees the
//    live end of file) and read from our last offset.
//  - Node opens with FILE_SHARE_READ|WRITE|DELETE, so holding the handle never blocks EVE.
//  - A read can end in the middle of a UTF-16 code unit or a UTF-8 sequence, and in the middle of a
//    line. Undecoded bytes and the unfinished line are carried to the next read.
const fs = require('fs')
const { StringDecoder } = require('string_decoder')

class Tail {
    constructor(file, { encoding = null } = {}) {
        this.file = file
        this.fd = null
        this.offset = 0
        this.encoding = encoding   // null = detect from the BOM on first read
        this.decoder = null
        this.partial = ''
        this.last_growth = Date.now()
    }

    open() {
        if (this.fd === null) this.fd = fs.openSync(this.file, 'r')
    }

    close() {
        if (this.fd !== null) {
            try { fs.closeSync(this.fd) } catch (e) {}
            this.fd = null
        }
    }

    // Complete new lines since the last call ([] if nothing new). Throws if the file is gone.
    read_lines() {
        this.open()
        const size = fs.fstatSync(this.fd).size
        if (size < this.offset) this.reset()             // truncated or replaced: start over
        if (size === this.offset) return []

        const buffer = Buffer.alloc(size - this.offset)
        const read = fs.readSync(this.fd, buffer, 0, buffer.length, this.offset)
        this.offset += read
        this.last_growth = Date.now()

        let bytes = buffer.subarray(0, read)
        if (!this.decoder) {
            if (!this.encoding) this.encoding = detect_encoding(bytes)
            if (this.encoding === 'utf16le' && bytes[0] === 0xff && bytes[1] === 0xfe) bytes = bytes.subarray(2)
            if (this.encoding === 'utf8' && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) bytes = bytes.subarray(3)
            this.decoder = new StringDecoder(this.encoding)
        }

        const text = this.partial + this.decoder.write(bytes)
        const lines = text.split(/\r\n|\n|\r/)
        this.partial = lines.pop()
        return lines.map(line => line.replace(/﻿/g, ''))   // EVE prefixes chat lines with a BOM
    }

    reset() {
        this.offset = 0
        this.decoder = null
        this.partial = ''
    }
}

function detect_encoding(bytes) {
    if (bytes[0] === 0xff && bytes[1] === 0xfe) return 'utf16le'
    if (bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) return 'utf8'
    // No BOM: UTF-16LE ASCII text has a zero in every odd byte.
    let zeros = 0
    const n = Math.min(bytes.length, 200)
    for (let i = 1; i < n; i += 2) if (bytes[i] === 0) zeros++
    return n > 1 && zeros > n / 4 ? 'utf16le' : 'utf8'
}

module.exports = { Tail, detect_encoding }
