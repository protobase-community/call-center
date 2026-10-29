import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import type postgres from 'postgres'

// Applies the migrations not applied yet, the app's and the auth schema's alike, in file name order and in one
// transaction: when one fails, none is applied and the database stays as the running version expects it. A statement
// Postgres runs only outside a transaction, such as `create index concurrently`, does not belong in these files.

const directory = fileURLToPath(new URL('./migrations/', import.meta.url))
// Any constant shared by every run: two runs at once take turns.
const lockKey = 7_311_946_202

/** Applies the pending migrations and answers their file names. */
export const applyMigrations = async (sql: postgres.Sql) => {
  const files = (await readdir(directory)).filter((file) => file.endsWith('.sql')).sort()
  return sql.begin(async (tx) => {
    await tx`select pg_advisory_xact_lock(${lockKey})`
    await tx`create table if not exists public.schema_migrations (name text primary key, applied_at timestamptz not null default now())`
    const done = new Set((await tx`select name from public.schema_migrations`).map((row) => row.name))
    const pending = files.filter((file) => !done.has(file))
    for (const file of pending) {
      await tx.unsafe(await readFile(directory + file, 'utf8'))
      await tx`insert into public.schema_migrations (name) values (${file})`
    }
    return pending
  })
}
