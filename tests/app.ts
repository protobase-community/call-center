import { randomBytes } from 'node:crypto'
import { Kysely, PostgresDialect } from 'kysely'
import pg from 'pg'
import { configExports, createAdmin } from '@protobase/server'
import * as config from '../config'
import { roles } from '../config/roles'
import { applyMigrations } from '../db/apply-migrations'
import { connect, databaseUrl } from '../db/connection'

// The app's API over a database of its own on the Postgres of DATABASE_URL: created with the project's migrations
// applied, and dropped again by `close`. A request signs in as the role its `x-role` header names.

const databaseOf = (name: string) => {
  const url = new URL(databaseUrl)
  url.pathname = `/${name}`
  return url.toString()
}

export const startApp = async () => {
  const name = `test_${randomBytes(6).toString('hex')}`
  const server = connect({ max: 1 })
  await server.unsafe(`create database ${name}`)

  const migrations = connect({ max: 1, database: name })
  await applyMigrations(migrations)
  await migrations.end()

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
    options: { roles },
  })

  const request = (role: string, method: string, path: string, body?: unknown, headers: Record<string, string> = {}) =>
    admin.request(`/api/v1${path}`, {
      method,
      headers: { 'x-role': role, 'content-type': 'application/json', ...headers },
      ...(body !== undefined && { body: JSON.stringify(body) }),
    })

  const close = async () => {
    await db.destroy()
    await server.unsafe(`drop database ${name} with (force)`)
    await server.end()
  }

  return { request, close }
}
