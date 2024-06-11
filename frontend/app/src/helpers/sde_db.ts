import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import * as schema from '../models/sde/schema.ts';
import { migrate } from 'drizzle-orm/better-sqlite3/migrator';

const sqlite = new Database(
    './src/data/sqlite-latest.sqlite'
);

export const sde_db = drizzle(sqlite, { schema });

// migrate(db, { migrationsFolder: './drizzle' });