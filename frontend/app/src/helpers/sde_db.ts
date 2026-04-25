import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';
import * as schema from '../models/sde/schema.ts';
import { migrate } from 'drizzle-orm/better-sqlite3/migrator';

const sqlite = new Database(
    './src/data/sde-3316380.sqlite'
);

export const sde_db = drizzle(sqlite, { schema });

// migrate(db, { migrationsFolder: './drizzle' });