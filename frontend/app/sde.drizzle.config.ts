// HOW TO UPDATE THE SDE: see docs/frontend-sde.md.
// - Put the new sde-<build>.sqlite in ./src/data/ and bump SDE_BUILD in
//   ./src/helpers/sde_path.mjs (the one place the build number lives)
// - Run the "introspectsde" script to regenerate ./src/models/sde/schema.ts
//   if the tables changed
// - Copy the file to every host's frontend/app/src/data/ before deploying

import type { Config } from 'drizzle-kit';
import { resolve_sde_path } from './src/helpers/sde_path.mjs';

export default {
    dialect: 'sqlite',
    schema: "./src/models/sde/schema.ts",
    out: "./src/models/sde/migrations/",
    dbCredentials: {
        url: `file:${resolve_sde_path().path}`,
    },
    verbose: true,
    strict: true,
} as Config;
