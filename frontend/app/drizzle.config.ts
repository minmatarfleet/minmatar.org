// drizzle.config.ts
import 'dotenv/config';
import type { Config } from 'drizzle-kit';

export default {
    schema: './src/models/schema.ts',
    out: './src/models/',
    driver: 'better-sqlite',
    dbCredentials: {
        url: './src/data/sqlite-latest.sqlite'
    }
} as Config;