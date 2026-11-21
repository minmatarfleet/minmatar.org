// Browser stand-in for node:crypto in the preview bundle (src/helpers/gates.ts
// imports createHash at module scope; it only runs on the render server).
const server_only = () => {
    throw new Error('node:crypto is only available on the render server')
}

export const createHash = server_only
export const randomUUID = () => globalThis.crypto.randomUUID()
export default { createHash, randomUUID }
