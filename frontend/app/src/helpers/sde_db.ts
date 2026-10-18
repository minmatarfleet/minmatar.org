import { drizzle, type BetterSQLite3Database } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import * as schema from '../models/sde/schema.ts';
import { resolve_sde_path } from '@helpers/sde_path.mjs';

type SdeDatabase = BetterSQLite3Database<typeof schema>;

let opened: SdeDatabase | null = null;

/**
 * Open the SDE snapshot on first use. The path comes from sde_path.mjs (the
 * pinned build, or SDE_PATH); a missing file throws a clear error instead of
 * silently creating an empty database.
 */
export function open_sde_db(): SdeDatabase {
    if (!opened) {
        const { path } = resolve_sde_path();
        opened = drizzle(new Database(path, { fileMustExist: true }), { schema });
    }
    return opened;
}

/** The SDE database. Opened lazily, so importing a helper does not need the file. */
export const sde_db: SdeDatabase = new Proxy({} as SdeDatabase, {
    get(_target, property) {
        const db = open_sde_db();
        const value = Reflect.get(db, property, db);
        return typeof value === 'function' ? value.bind(db) : value;
    },
});
