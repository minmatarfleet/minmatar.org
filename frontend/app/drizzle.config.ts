// drizzle.config.ts
import 'dotenv/config';
import type { Config } from 'drizzle-kit';

const TURSO_DATABASE_URL = process.env.TURSO_DATABASE_URL
const TURSO_AUTH_TOKEN = process.env.TURSO_AUTH_TOKEN

if (TURSO_DATABASE_URL === undefined)
    throw new Error(`Please define enviroment variable TURSO_DATABASE_URL`)

if (TURSO_AUTH_TOKEN === undefined)
    throw new Error(`Please define enviroment variable TURSO_AUTH_TOKEN`)

export default {
    dialect: 'sqlite',
    schema: "./src/models/main/schema.ts",
    out: './src/models/migrations/',
    dbCredentials: {
        url: TURSO_DATABASE_URL!,
        authToken: TURSO_AUTH_TOKEN!,
    },
    driver: 'turso',
    verbose: true,
    strict: true,
} as Config;