import { defineFunction, notFound } from '@protobase/server'
import type { Kysely } from 'kysely'
import { parseBody } from './body'
import { callKey } from './call-of'
import { createCall, setCallStatus } from './calls'
import { customer } from './customer'
import { signedBody } from './signed-request'
import { createTicket } from './tickets'
import { verify } from './verify'

// /api/functions/phone-line/...: the phone line reports its calls and acts for a verified caller. Public, as no account
// signs in: every request is signed with PHONE_LINE_SECRET instead (./signed-request.ts), checked before anything else.
// Answers are JSON; refusals are problems, 404 for a call or customer the line cannot reach.

type Route = {
  method: string
  path: RegExp
  run: (db: Kysely<any>, match: { key: () => number; body: () => Record<string, unknown> }) => Promise<Response>
}

const routes: Route[] = [
  { method: 'POST', path: /^\/calls$/, run: (db, { body }) => createCall(db, body()) },
  { method: 'POST', path: /^\/calls\/([^/]+)\/status$/, run: (db, { key, body }) => setCallStatus(db, key(), body()) },
  { method: 'POST', path: /^\/calls\/([^/]+)\/verify$/, run: (db, { key, body }) => verify(db, key(), body()) },
  { method: 'GET', path: /^\/calls\/([^/]+)\/customer$/, run: (db, { key }) => customer(db, key()) },
  { method: 'POST', path: /^\/calls\/([^/]+)\/tickets$/, run: (db, { key, body }) => createTicket(db, key(), body()) },
]

export default defineFunction({ public: true }, async (request, { db }) => {
  const text = await signedBody(db, request)
  const { pathname } = new URL(request.url)
  for (const route of routes) {
    const match = route.method === request.method ? route.path.exec(pathname) : null
    if (!match) continue
    return route.run(db, { key: () => callKey(match[1]!), body: () => parseBody(text) })
  }
  throw notFound(`There is no ${request.method} ${pathname} on the phone line`)
})
