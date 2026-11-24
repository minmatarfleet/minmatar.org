# Restore runbook

Step-by-step restore of the MariaDB databases to a point in time, and of the Plane Postgres database from a nightly dump. Read [backups.md](backups.md) first for how the backups are made.

**Never restore over production directly.** Every restore goes to an isolated instance first. Only validated, exported data is loaded into production, deliberately, by someone who knows what it replaces.

## Placeholders

| Placeholder | Meaning |
| --- | --- |
| `<BUCKET>` | The backup bucket |
| `<ENDPOINT>` | The object storage endpoint |
| `<RESTORE_KEY_ID>`, `<RESTORE_KEY>` | The offline, read-only restore credential |
| `<PRIVATE_KEY_FILE>` | The offline age private key file |
| `<DUMP_PATH>` | The object path of the nightly dump to restore (the last one before `<TARGET_TIME>`) |
| `<BINLOG_PATH>` | The object path prefix of the shipped binary logs |
| `<TARGET_TIME>` | The moment to restore to, as `YYYY-MM-DD HH:MM:SS` in the database server's time zone |
| `<WORK>` | A scratch directory on an encrypted disk of the restore machine |

## Before you start

- Use a machine you control that is **not** the production server, with MariaDB and Postgres client/server binaries of the same major versions as production, `age`, `zstd` (or the compressor the manifest lists) and an S3-compatible client.
- Make sure `<WORK>` has room for the decompressed dump plus the restored datadir.
- Write down `<TARGET_TIME>` and why. For "undo a bad statement", the target is the statement itself; the binary log gives its exact position (see the variant below).
- Keep the private key file on removable or encrypted storage. Do not copy it into `<WORK>`.

## 1. Download

Configure the S3 client with the restore credential for this shell only:

```bash
export AWS_ACCESS_KEY_ID=<RESTORE_KEY_ID> AWS_SECRET_ACCESS_KEY=<RESTORE_KEY>
```

```bash
mkdir -p <WORK>/download && cd <WORK>/download
```

```bash
aws s3 cp --recursive --endpoint-url <ENDPOINT> s3://<BUCKET>/<DUMP_PATH>/ dump/
```

```bash
aws s3 cp --recursive --endpoint-url <ENDPOINT> s3://<BUCKET>/<BINLOG_PATH>/ binlogs/
```

Download every binary-log file from the one named in the dump header (step 4) up to and past `<TARGET_TIME>`. When in doubt, download more; extra files are harmless.

## 2. Decrypt and decompress

```bash
for f in dump/*.age binlogs/*.age; do age -d -i <PRIVATE_KEY_FILE> -o "${f%.age}" "$f"; done
```

```bash
for f in dump/*.zst binlogs/*.zst; do zstd -d --rm "$f"; done
```

## 3. Verify the manifest

Each upload has a checksum manifest. Check every file against it before using any of them:

```bash
cd <WORK>/download/dump && sha256sum -c <MANIFEST_FILE>
```

Do the same for the binary logs. Stop and investigate any mismatch; do not restore from a file that fails.

## 4. Start an isolated MariaDB

The side instance uses its own datadir, reads no config files, and listens on a local socket only:

```bash
mkdir -p <WORK>/mysql && mariadb-install-db --no-defaults --datadir=<WORK>/mysql/data --auth-root-authentication-method=normal
```

```bash
mariadbd --no-defaults --datadir=<WORK>/mysql/data --socket=<WORK>/mysql/mysqld.sock --skip-networking --skip-log-bin &
```

`root` on this instance has no password; that is safe only because it has no network listener. Every client command below passes `--socket=<WORK>/mysql/mysqld.sock` (and `-u root`), so nothing can reach production by accident.

## 5. Load the dump

```bash
mariadb -u root --socket=<WORK>/mysql/mysqld.sock < <WORK>/download/dump/<DUMP_FILE>.sql
```

## 6. Read the binary-log position from the dump header

```bash
head -n 50 <WORK>/download/dump/<DUMP_FILE>.sql | grep -E "CHANGE (MASTER|REPLICATION SOURCE) TO"
```

This gives the start file and position, e.g. `MASTER_LOG_FILE='<BINLOG_FILE>', MASTER_LOG_POS=<START_POS>`.

## 7. Replay binary logs to the target

Pass the start file first and every later file after it, in order. `--start-position` applies to the first file. Set `TZ` to the database server's time zone so `--stop-datetime` means what you think:

```bash
cd <WORK>/download/binlogs && TZ=<SERVER_TZ> mariadb-binlog --start-position=<START_POS> --stop-datetime="<TARGET_TIME>" <BINLOG_FILE> <LATER_BINLOG_FILES...> | mariadb -u root --socket=<WORK>/mysql/mysqld.sock
```

To stop just before a specific event instead of a time, replace `--stop-datetime` with `--stop-position=<STOP_POS>`, where the stop position is in the last file you pass (see the variant below).

## 8. Validate

Work through the checklist at the end of this page before exporting anything.

## 9. Export what is needed

Export only the databases or tables you need from the side instance:

```bash
mariadb-dump -u root --socket=<WORK>/mysql/mysqld.sock --single-transaction <DATABASE> <TABLE...> > <WORK>/export.sql
```

Review the export, agree with the team how it is applied (replace a table, or insert missing rows), take a fresh backup of what it will replace, then apply it to production.

## 10. Clean up

When the export has been applied and checked:

```bash
mariadb-admin -u root --socket=<WORK>/mysql/mysqld.sock shutdown
```

```bash
shred -u <WORK>/download/dump/* <WORK>/download/binlogs/* <WORK>/export.sql 2>/dev/null; rm -rf <WORK>
```

Unset the restore credential (`unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY`), close the shell, and return the private key to offline storage. No decrypted data may remain on the restore machine.

## Variant: recover a dropped table (or undo a bad statement)

1. Do steps 1 to 6 with the last nightly dump before the bad statement.
2. Find the statement in the binary logs. For a `DROP` or other DDL:

   ```bash
   mariadb-binlog <BINLOG_FILES...> | grep -n -i -B 20 "DROP TABLE"
   ```

   For a bad `UPDATE` or `DELETE` (row-based logging), decode the rows:

   ```bash
   mariadb-binlog -v --base64-output=decode-rows <BINLOG_FILES...> | less
   ```

   Note the file that holds the statement and the `# at <STOP_POS>` line that starts its event (for a transaction, the `BEGIN` before it).
3. Replay up to, and not including, that event: step 7 with `--stop-position=<STOP_POS>`, passing the files up to and including the one that holds it.
4. Validate, then export only the affected tables (step 9) and restore them into production.
5. Optional, for DML only: `mariadb-binlog --flashback --start-position=<POS> --stop-position=<POS> <BINLOG_FILE>` produces statements that undo the logged row changes. Apply them to the side instance first and compare before using them anywhere else.

## Plane Postgres

Plane restores to a nightly dump; there is no point-in-time replay. After steps 1 to 3, start an isolated Postgres with its own data directory, listening on a local socket only:

```bash
initdb -D <WORK>/pg/data && pg_ctl -D <WORK>/pg/data -o "-c listen_addresses='' -k <WORK>/pg" start
```

```bash
createdb -h <WORK>/pg <PLANE_DB> && pg_restore -h <WORK>/pg -d <PLANE_DB> --no-owner <WORK>/download/dump/<PLANE_DUMP_FILE>
```

(Use `psql -h <WORK>/pg -d <PLANE_DB> -f ...` instead if the dump is plain SQL.) Validate, export what is needed with `pg_dump`, then stop it with `pg_ctl -D <WORK>/pg/data stop` and clean up as in step 10.

## Validation checklist

- [ ] Every downloaded file passed the manifest check.
- [ ] The list of databases and tables on the side instance matches production (or the dump, for anything dropped since): `SHOW DATABASES;` and `SHOW TABLES;` per database.
- [ ] Row counts of the tables you care about are plausible for `<TARGET_TIME>`, compared with production now and with what you expect changed since.
- [ ] No rows are newer than `<TARGET_TIME>`: for tables with a created/updated timestamp, `SELECT MAX(<timestamp_column>) FROM <TABLE>;` is at or before it.
- [ ] For the bad-statement variant: the dropped table exists, or the changed rows hold their old values, and the rows just before the statement are present.
- [ ] Spot-check a few recent records you can identify (a known fleet, order or user) against what they were at `<TARGET_TIME>`.
- [ ] The application's migration state on the side instance matches the code version you will load the data into.
