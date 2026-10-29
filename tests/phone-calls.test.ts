import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import * as config from '../config'
import { startApp } from './app'

// Phone calls through the app's API, on a database of their own with the project's migrations. The phone line writes
// calls straight into the database, as its own functions will; staff read them and pick the ticket a call is about.

let app: Awaited<ReturnType<typeof startApp>>

beforeAll(async () => {
  app = await startApp()
}, 60_000)

afterAll(async () => {
  await app?.close()
})

const recent = config.phoneCallsView.state.nav?.recent

const insertCall = async (room_name: string, status: string) => {
  const [call] = await app.sql`
    insert into public.phone_calls (room_name, caller_number, status) values (${room_name}, '+31 20 555 0101', ${status})
    returning id`
  return call!.id as number
}

const sidebarIds = async () => {
  const query = new URLSearchParams({ filter: recent!.filter!, order_by: recent!.orderBy!, page_size: String(recent!.limit) })
  const response = await app.request('agent', 'GET', `/phone_calls?${query}`)
  expect(response.status).toBe(200)
  return ((await response.json()).items as { id: number }[]).map((call) => call.id)
}

describe('the sidebar group of phone calls', () => {
  it('lists a call while it is incoming, waiting or active, and leaves it out once it has ended', async () => {
    expect(recent?.filter).toBe('status != "ended"')
    const id = await insertCall('call-sidebar', 'incoming')
    expect(await sidebarIds()).toContain(id)

    for (const status of ['waiting', 'active']) {
      await app.sql`update public.phone_calls set status = ${status} where id = ${id}`
      expect(await sidebarIds()).toContain(id)
    }

    await app.sql`update public.phone_calls set status = 'ended', ended_at = now() where id = ${id}`
    expect(await sidebarIds()).not.toContain(id)
  })
})

describe('a phone call', () => {
  it('may not have its customer or status set by an agent', async () => {
    const id = await insertCall('call-agent', 'active')
    const [customer] = await app.sql`insert into public.customers (name) values ('Suharti') returning id`

    for (const change of [{ customer_id: customer!.id }, { status: 'ended' }]) {
      const read = await app.request('agent', 'GET', `/phone_calls/${id}`)
      const response = await app.request('agent', 'PATCH', `/phone_calls/${id}`, change, { 'if-match': read.headers.get('etag')! })
      expect(response.status).toBe(400)
    }

    const read = await app.request('agent', 'GET', `/phone_calls/${id}`)
    expect(await read.json()).toMatchObject({ customer_id: null, status: 'active' })
  })

  it('takes the ticket an agent picks', async () => {
    const id = await insertCall('call-ticket', 'active')
    const [customer] = await app.sql`insert into public.customers (name) values ('Kwame Mensah') returning id`
    const [ticket] = await app.sql`insert into public.tickets (customer_id, subject, status) values (${customer!.id}, 'Refund', 'open') returning id`

    const read = await app.request('agent', 'GET', `/phone_calls/${id}`)
    const response = await app.request('agent', 'PATCH', `/phone_calls/${id}`, { ticket_id: ticket!.id }, { 'if-match': read.headers.get('etag')! })
    expect(response.status).toBe(200)
    expect(await response.json()).toMatchObject({ ticket_id: ticket!.id, status: 'active' })
  })

  it('may not be created or deleted by staff', async () => {
    const id = await insertCall('call-staff', 'incoming')
    for (const role of ['agent', 'manager']) {
      expect((await app.request(role, 'POST', '/phone_calls', { room_name: 'call-made-up', status: 'incoming' })).status).toBe(403)
      expect((await app.request(role, 'DELETE', `/phone_calls/${id}`)).status).toBe(403)
    }
  })
})

describe("the phone line's account", () => {
  it('reads phone calls, changes nothing through the API and sees no other resource', async () => {
    const id = await insertCall('call-line', 'incoming')
    const read = await app.request('phone_line', 'GET', `/phone_calls/${id}`)
    expect(read.status).toBe(200)

    const etag = { 'if-match': read.headers.get('etag')! }
    expect((await app.request('phone_line', 'PATCH', `/phone_calls/${id}`, { ticket_id: null }, etag)).status).toBe(403)
    expect((await app.request('phone_line', 'POST', '/phone_calls', { room_name: 'call-made-up', status: 'incoming' })).status).toBe(403)
    expect((await app.request('phone_line', 'DELETE', `/phone_calls/${id}`)).status).toBe(403)
    expect((await app.request('phone_line', 'GET', '/customers')).status).toBe(404)
  })
})
