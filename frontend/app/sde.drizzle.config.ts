// HOW TO UPDATE SDE LITE
// - Download for sqlite-latest.sqlite.bz2 file at https://www.fuzzwork.co.uk/dump/
// - Extract the file into ./src/data/ folder and name it to sqlite-latest.sqlite
// - Use "introspectsde" script to generate the schema file
// - Create/Update the ./src/sde/types.ts replacing the elements on the
//   import statement for those in the schema file in migration folder and update
//   the export statement according the new imports
// - Upload the db into the production folder and merge the PR "at the same time"

import type { Config } from 'drizzle-kit';

export default {
    dialect: 'sqlite',
    schema: "./src/models/sde/schema.ts",
    out: "./src/models/sde/migrations/",
    dbCredentials: {
        url: "file:./src/data/sqlite-latest-3316380.sqlite",
    },
    verbose: true,
    strict: true,
} as Config;