import { randomBytes } from 'node:crypto'
import { readdir } from 'node:fs/promises'
import { Kysely, PostgresDialect } from 'kysely'
import pg from 'pg'
import { configExports, createAdmin, type FunctionSource } from '@protobase/server'
import * as config from '../config'
import { roles } from '../config/roles'
import { applyMigrations } from '../db/apply-migrations'
import { connect, databaseUrl } from '../db/connection'

// The app's API over a database of its own on the Postgres of DATABASE_URL: created with the project's migrations
// applied, and dropped again by `close`. A request signs in as the role its `x-role` header names; `sql` and `db` write
// to the database directly, as the phone line does. It serves the project's functions, as `protobase build` finds them
// in functions/, and those a test adds, without WebSockets, so a function that admits its caller to a call answers 426
// once it has, and LiveKit is only named, never reached.

const functionsDirectory = new URL('../functions/', import.meta.url)

// `functions/<name>.ts` or `functions/<name>/index.ts`, leaving out shared code (`_`), dotfiles and tests.
const projectFunctions = async () => {
  const found = (await readdir(functionsDirectory, { withFileTypes: true }))
    .filter((entry) => !/^[_.]/.test(entry.name) && (entry.isDirectory() || (entry.name.endsWith('.ts') && !/\.(test|spec|d)\.ts$/.test(entry.name))))
    .map((entry) => (entry.isDirectory() ? [entry.name, `${entry.name}/index.ts`] : [entry.name.slice(0, -'.ts'.length), entry.name]))
  const entries = await Promise.all(
    found.map(async ([name, file]) => [name, (await import(new URL(file!, functionsDirectory).href)).default as FunctionSource]),
  )
  return Object.fromEntries(entries) as Record<string, FunctionSource>
}

const databaseOf = (name: string) => {
  const url = new URL(databaseUrl)
  url.pathname = `/${name}`
  return url.toString()
}

export const startApp = async ({ functions = {} }: { functions?: Record<string, FunctionSource> } = {}) => {
  const name = `test_${randomBytes(6).toString('hex')}`
  const server = connect({ max: 1 })
  await server.unsafe(`create database ${name}`)

  const sql = connect({ max: 1, database: name })
  await applyMigrations(sql)

  const pool = new pg.Pool({ connectionString: databaseOf(name) })
  const db = new Kysely<any>({ dialect: new PostgresDialect({ pool }) })
  const { resources, views } = configExports(config)
  const admin = createAdmin({
    resources,
    views,
    db,
    functions: { ...(await projectFunctions()), ...functions },
    authenticate: (request) => {
      const role = request.headers.get('x-role')
      if (!role) throw new Error('Every request in these tests names its role')
      return { user: { id: `${role}-1`, roles: [role] }, tenant: 1 }
    },
    calls: { backend: { kind: 'livekit', url: 'ws://127.0.0.1:7880', apiKey: 'devkey', apiSecret: 'secret' } },
    options: { roles },
  })

  const call = (role: string, method: string, path: string, body?: unknown, headers: Record<string, string> = {}) =>
    admin.request(path, {
      method,
      headers: { 'x-role': role, 'content-type': 'application/json', ...headers },
      ...(body !== undefined && { body: JSON.stringify(body) }),
    })
  const request = (role: string, method: string, path: string, body?: unknown, headers: Record<string, string> = {}) =>
    call(role, method, `/api/v1${path}`, body, headers)
  /** Calls a function of the app, as `client.invoke` does: a POST of `body` as JSON. */
  const invoke = (role: string, name: string, body: unknown) => call(role, 'POST', `/api/functions/${name}`, body)
  /** A GET of the app's function at `path`, such as `/api/functions/phone-call?phone_call=1`. */
  const open = (role: string, path: string) => call(role, 'GET', path)

  const close = async () => {
    await db.destroy()
    await sql.end()
    await server.unsafe(`drop database ${name} with (force)`)
    await server.end()
  }

  return { request, invoke, open, sql, db, close }
}
