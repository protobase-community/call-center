import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { defineFunction, getRecordTool, listRecordsTool, readJson, type ToolContext } from '@protobase/server'
import { startApp } from './app'

// No role reads a support PIN's hash: not in a list, a record or a read of the MCP endpoint's tools. The MCP tools run
// here in a function of the test's own, as the caller and over the caller's records, which is what the endpoint gives
// them; the endpoint's OAuth sign-in is the framework's.

const roles = ['admin', 'manager', 'agent']

const mcpRead = defineFunction({ roles }, async (request, { session, records }) => {
  const { tool, args } = (await readJson(request)) as { tool: string; args: Record<string, unknown> }
  const run = tool === 'get_record' ? getRecordTool().run : listRecordsTool().run
  const context = { session, records, resources: () => Promise.reject(new Error('Not used with fields')), show: () => {} }
  return new Response(await run(args, context as unknown as ToolContext))
})

let app: Awaited<ReturnType<typeof startApp>>
let customer: number

beforeAll(async () => {
  app = await startApp({ functions: { 'mcp-read': mcpRead } })
  const [row] = await app.sql`insert into public.customers (name) values ('Kwame Asante') returning id`
  customer = row!.id
  expect((await app.invoke('agent', 'set-support-pin', { customer, pin: '482915' })).status).toBe(200)
  const [stored] = await app.sql`select support_pin_hash from public.customers where id = ${customer}`
  expect(stored!.support_pin_hash).toMatch(/^scrypt:/)
}, 60_000)

afterAll(async () => {
  await app?.close()
})

// The hash's field by name, or any stored hash's text.
const expectNoHash = (text: string) => {
  expect(text).not.toContain('support_pin_hash')
  expect(text).not.toContain('scrypt:')
}

describe.each(roles)('the support PIN hash, for %s', (role) => {
  it('is in no list of customers', async () => {
    const response = await app.request(role, 'GET', '/customers')
    expect(response.status).toBe(200)
    expectNoHash(await response.text())
  })

  it('is in no customer record', async () => {
    const response = await app.request(role, 'GET', `/customers/${customer}`)
    expect(response.status).toBe(200)
    expectNoHash(await response.text())
  })

  it('cannot be asked for by name', async () => {
    expect((await app.request(role, 'GET', '/customers?fields=support_pin_hash')).status).toBe(400)
    expect((await app.request(role, 'GET', `/customers/${customer}?fields=support_pin_hash`)).status).toBe(400)
    expect((await app.request(role, 'GET', '/customers?filter=support_pin_hash%3D%22x%22')).status).toBe(400)
  })

  it('is in no MCP read', async () => {
    for (const [tool, args] of [
      ['get_record', { resource: 'customers', key: String(customer) }],
      ['get_record', { resource: 'customers', key: String(customer), fields: ['*'] }],
      ['list_records', { resource: 'customers', fields: ['*'] }],
    ] as const) {
      const response = await app.invoke(role, 'mcp-read', { tool, args })
      expect(response.status).toBe(200)
      const text = await response.text()
      expect(text).toContain('Kwame Asante')
      expectNoHash(text)
    }
    const named = await app.invoke(role, 'mcp-read', { tool: 'get_record', args: { resource: 'customers', key: String(customer), fields: ['support_pin_hash'] } })
    expect(await named.json()).toEqual({ error: 'invalid-parameter', message: 'Unknown fields: support_pin_hash' })
  })
})
