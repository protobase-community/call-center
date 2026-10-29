import { randomBytes } from 'node:crypto'
import { Kysely, PostgresDialect } from 'kysely'
import pg from 'pg'
import { configExports, createAdmin } from '@protobase/server'
import * as config from '../config'
import { roles } from '../config/roles'
import { applyMigrations } from '../db/apply-migrations'
import { connect, databaseUrl } from '../db/connection'
import phoneCall from '../functions/phone-call'

// The app's API over a database of its own on the Postgres of DATABASE_URL: created with the project's migrations
// applied, and dropped again by `close`. A request signs in as the role its `x-role` header names; `sql` writes to the
// database directly, as the phone line does. The functions are served too, without WebSockets, so a function that
// admits its caller to a call answers 426 once it has, and LiveKit is only named, never reached.

const databaseOf = (name: string) => {
  const url = new URL(databaseUrl)
  url.pathname = `/${name}`
  return url.toString()
}

export const startApp = async () => {
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
    authenticate: (request) => {
      const role = request.headers.get('x-role')
      if (!role) throw new Error('Every request in these tests names its role')
      return { user: { id: `${role}-1`, roles: [role] }, tenant: 1 }
    },
    functions: { 'phone-call': phoneCall },
    calls: { backend: { kind: 'livekit', url: 'ws://127.0.0.1:7880', apiKey: 'devkey', apiSecret: 'secret' } },
    options: { roles },
  })

  const send = (role: string, method: string, url: string, body?: unknown, headers: Record<string, string> = {}) =>
    admin.request(url, {
      method,
      headers: { 'x-role': role, 'content-type': 'application/json', ...headers },
      ...(body !== undefined && { body: JSON.stringify(body) }),
    })
  const request = (role: string, method: string, path: string, body?: unknown, headers: Record<string, string> = {}) =>
    send(role, method, `/api/v1${path}`, body, headers)
  /** A request to the app's function at `path`, such as `/api/functions/phone-call?phone_call=1`. */
  const invoke = (role: string, path: string) => send(role, 'GET', path)

  const close = async () => {
    await db.destroy()
    await sql.end()
    await server.unsafe(`drop database ${name} with (force)`)
    await server.end()
  }

  return { request, invoke, sql, close }
}
