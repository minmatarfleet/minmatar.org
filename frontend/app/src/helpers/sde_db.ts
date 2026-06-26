import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import { existsSync, statSync } from 'node:fs';
import * as schema from '../models/sde/schema.ts';
import { migrate } from 'drizzle-orm/better-sqlite3/migrator';

const SDE_CANDIDATES = [
    './src/data/sde-3409592.sqlite',
    './src/data/sde-3316380.sqlite',
] as const;

function resolveSdePath(): string {
    for (const path of SDE_CANDIDATES) {
        try {
            if (existsSync(path) && statSync(path).size > 0) return path;
        } catch {
            continue;
        }
    }
    return SDE_CANDIDATES[0];
}

const sqlite = new Database(
    resolveSdePath()
);

export const sde_db = drizzle(sqlite, { schema });

// migrate(db, { migrationsFolder: './drizzle' });