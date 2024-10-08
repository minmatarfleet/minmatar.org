// HOW TO UPDATE SDE LITE
// - Download for sqlite-latest.sqlite.bz2 file at https://www.fuzzwork.co.uk/dump/
// - Extract the file into ./src/data/ folder and name it to sqlite-latest.sqlite
// - Use "introspectsde" script to generate the schema file
// - Create/Update the ./src/types.ts replacing the elements on the
//   import statement for those in the schema file and update
//   the export statement according the new imports
// - Upload the db into the production folder and merge the PR "at the same time"

import type { Config } from 'drizzle-kit';

export default {
    dialect: 'sqlite',
    schema: "./src/models/sde/schema.ts",
    out: "./src/models/sde/migrations/",
    driver: "better-sqlite",
    dbCredentials: {
        url: "file:./src/data/sqlite-latest-2024-09-20.sqlite",
    },
    verbose: true,
    strict: true,
} as Config;