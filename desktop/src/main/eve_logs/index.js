// EVE chat / game log engine. See engine.js for the event API.
const { EveLogEngine } = require('./engine')
const { Tail } = require('./tail')
const parse = require('./parse')
const files = require('./files')

module.exports = { EveLogEngine, Tail, parse, files }
