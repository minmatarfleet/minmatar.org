// drizzle.config.ts
import 'dotenv/config';
import type { Config } from 'drizzle-kit';

export default {
    dialect: "sqlite",
    schema: "./src/models/main/schema.ts",
    out: './src/models/migrations/',
    driver: 'better-sqlite',
} as Config;