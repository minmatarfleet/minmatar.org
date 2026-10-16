// Jumps from the pilot's system to each intel row, worked out on this PC from the gate graph
// (GET /api/intel/map, SDE data). The pilot's location never goes to the server (CCP rule 15).
const MAX_JUMPS = 30

class IntelMap {
    constructor(data = null) {
        this.set(data)
    }

    set(data) {
        this.systems = new Map()   // id -> name
        this.ids = new Map()       // lower-case name -> id
        this.edges = new Map()     // id -> [neighbour ids]
        this.distances = new Map() // origin id -> Map(id -> jumps), filled on demand
        for (const [id, name] of Object.entries((data && data.systems) || {})) {
            this.systems.set(Number(id), name)
            this.ids.set(String(name).toLowerCase(), Number(id))
        }
        for (const [id, neighbours] of Object.entries((data && data.edges) || {})) {
            this.edges.set(Number(id), neighbours.map(Number))
        }
    }

    get loaded() {
        return this.edges.size > 0
    }

    system_id(name) {
        return name ? this.ids.get(String(name).toLowerCase()) || null : null
    }

    // Breadth-first from the origin once, then every row is a lookup.
    distances_from(origin_id) {
        if (!origin_id || !this.edges.has(origin_id)) return null
        let found = this.distances.get(origin_id)
        if (found) return found
        found = new Map([[origin_id, 0]])
        let frontier = [origin_id]
        for (let depth = 1; depth <= MAX_JUMPS && frontier.length; depth++) {
            const next = []
            for (const id of frontier) {
                for (const neighbour of this.edges.get(id) || []) {
                    if (found.has(neighbour)) continue
                    found.set(neighbour, depth)
                    next.push(neighbour)
                }
            }
            frontier = next
        }
        this.distances.set(origin_id, found)
        return found
    }

    // null: we don't know (no origin, or a system outside the map).
    jumps(origin_name, system_id) {
        const distances = this.distances_from(this.system_id(origin_name))
        if (!distances || !system_id) return null
        const jumps = distances.get(Number(system_id))
        return jumps === undefined ? null : jumps
    }
}

// Rows the pilot asked to see: within range, or unknown distance (a ping outside the map is still worth seeing).
function within_range(item, range) {
    if (range == null || item.jumps == null) return true
    return item.jumps <= range
}

module.exports = { IntelMap, within_range, MAX_JUMPS }
