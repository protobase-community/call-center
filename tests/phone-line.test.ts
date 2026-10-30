import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { setPin } from '../functions/_shared/support-pin'
import { startApp } from './app'
import { newSecret, signedHeaders } from './phone-line-signer'

// The phone line's signed function, functions/phone-line, on a database of its own: it reports calls and acts for a
// verified caller, and refuses an unsigned, stale or replayed request without changing anything.

let app: Awaited<ReturnType<typeof startApp>>
const secret = newSecret()

beforeAll(async () => {
  process.env.PHONE_LINE_SECRET = secret
  app = await startApp()
}, 60_000)

afterAll(async () => {
  await app?.close()
  delete process.env.PHONE_LINE_SECRET
})

const pin = '482915'
let rooms = 0
const nextRoom = () => `line-room-${++rooms}`

const send = (method: string, path: string, body?: unknown, headers?: Record<string, string>) => {
  const text = body === undefined ? '' : JSON.stringify(body)
  return app.send(`/api/functions/phone-line${path}`, {
    method,
    headers: { 'content-type': 'application/json', ...(headers ?? signedHeaders(secret, text)) },
    ...(method !== 'GET' && { body: text }),
  })
}

const createCall = async (room_name = nextRoom()) => {
  const response = await send('POST', '/calls', { room_name, caller_number: '+31 20 555 0101' })
  expect(response.status).toBe(201)
  return (await response.json()).id as number
}

const customerWithPin = async (name = 'Ama Mensah') => {
  const [customer] = await app.sql`insert into public.customers (name) values (${name}) returning id, customer_number`
  await setPin(app.db, { customer: customer!.id, pin })
  return { id: customer!.id as number, number: customer!.customer_number as string }
}

const verifiedCall = async () => {
  const customer = await customerWithPin()
  const call = await createCall()
  const response = await send('POST', `/calls/${call}/verify`, { customer_number: customer.number, pin })
  expect(await response.json()).toEqual({ result: 'verified' })
  return { call, customer }
}

const callOf = async (id: number) =>
  (await app.sql`select status, customer_id, ticket_id, waiting_since, ended_at, pin_failures from public.phone_calls where id = ${id}`)[0]!
const callsIn = async (room: string) => Number((await app.sql`select count(*) from public.phone_calls where room_name = ${room}`)[0]!.count)
const ticketCount = async () => Number((await app.sql`select count(*) from public.tickets`)[0]!.count)

describe('signed requests', () => {
  const refusedAlike = async (headers: (body: string) => Record<string, string>) => {
    const room = nextRoom()
    const body = { room_name: room }
    const response = await send('POST', '/calls', body, headers(JSON.stringify(body)))
    expect(response.status).toBe(401)
    expect(await callsIn(room)).toBe(0)
  }

  it('refuses a request without a signature and changes nothing', async () => {
    await refusedAlike(() => ({}))
  })

  it('refuses a request signed with another secret and changes nothing', async () => {
    await refusedAlike((body) => signedHeaders(newSecret(), body))
  })

  it('refuses a request whose timestamp is old, or ahead, and changes nothing', async () => {
    const now = Math.floor(Date.now() / 1000)
    await refusedAlike((body) => signedHeaders(secret, body, { seconds: now - 600 }))
    await refusedAlike((body) => signedHeaders(secret, body, { seconds: now + 600 }))
  })

  it('refuses a body changed after signing and changes nothing', async () => {
    await refusedAlike(() => signedHeaders(secret, JSON.stringify({ room_name: 'another-room' })))
  })

  it('takes a signed message once: sent again, at the same or another path, it is refused', async () => {
    const room = nextRoom()
    const body = { room_name: room }
    const headers = signedHeaders(secret, JSON.stringify(body))
    expect((await send('POST', '/calls', body, headers)).status).toBe(201)
    expect((await send('POST', '/calls', body, headers)).status).toBe(401)
    const [call] = await app.sql`select id from public.phone_calls where room_name = ${room}`
    expect((await send('POST', `/calls/${call!.id}/status`, body, headers)).status).toBe(401)
    expect((await callOf(call!.id)).status).toBe('incoming')
  })

  it('answers 404 for a path it does not serve', async () => {
    expect((await send('GET', '/calls')).status).toBe(404)
    expect((await send('GET', '/calls/1/tickets')).status).toBe(404)
  })
})

describe('reporting calls', () => {
  it('creates an incoming call once per room', async () => {
    const room = nextRoom()
    const first = await send('POST', '/calls', { room_name: room, caller_number: '+31 20 555 0101' })
    expect(first.status).toBe(201)
    const created = await first.json()
    expect(created).toMatchObject({ room_name: room, caller_number: '+31 20 555 0101', status: 'incoming' })

    const again = await send('POST', '/calls', { room_name: room, caller_number: '+31 20 555 0101' })
    expect(again.status).toBe(200)
    expect((await again.json()).id).toBe(created.id)
    expect(await callsIn(room)).toBe(1)
  })

  it('takes a call without a caller number, and refuses one without a room', async () => {
    expect((await send('POST', '/calls', { room_name: nextRoom() })).status).toBe(201)
    const response = await send('POST', '/calls', { caller_number: '+31 20 555 0101' })
    expect(response.status).toBe(400)
    expect((await response.json()).errors[0].field).toBe('room_name')
  })

  it('moves an incoming call to waiting, then ended, keeping when each happened', async () => {
    const call = await createCall()
    expect((await send('POST', `/calls/${call}/status`, { status: 'waiting' })).status).toBe(200)
    const waiting = await callOf(call)
    expect(waiting).toMatchObject({ status: 'waiting', ended_at: null })
    expect(waiting.waiting_since).toBeInstanceOf(Date)

    expect((await send('POST', `/calls/${call}/status`, { status: 'waiting' })).status).toBe(200)
    expect((await callOf(call)).waiting_since).toEqual(waiting.waiting_since)

    expect((await send('POST', `/calls/${call}/status`, { status: 'ended' })).status).toBe(200)
    const ended = await callOf(call)
    expect(ended.status).toBe('ended')
    expect(ended.ended_at).toBeInstanceOf(Date)
    expect((await send('POST', `/calls/${call}/status`, { status: 'ended' })).status).toBe(200)
    expect((await callOf(call)).ended_at).toEqual(ended.ended_at)
  })

  it('leaves active to staff, and moves no call out of ended', async () => {
    const call = await createCall()
    expect((await send('POST', `/calls/${call}/status`, { status: 'active' })).status).toBe(400)

    await app.sql`update public.phone_calls set status = 'active' where id = ${call}`
    expect((await send('POST', `/calls/${call}/status`, { status: 'waiting' })).status).toBe(409)
    expect((await send('POST', `/calls/${call}/status`, { status: 'ended' })).status).toBe(200)
    expect((await send('POST', `/calls/${call}/status`, { status: 'waiting' })).status).toBe(409)
    expect((await callOf(call)).status).toBe('ended')
  })

  it('answers 404 for a call that is not there', async () => {
    expect((await send('POST', '/calls/999999/status', { status: 'ended' })).status).toBe(404)
    expect((await send('POST', '/calls/abc/status', { status: 'ended' })).status).toBe(404)
    expect((await send('POST', '/calls/99999999999/status', { status: 'ended' })).status).toBe(404)
  })
})

describe('acting for a verified caller', () => {
  it('answers 404 for the customer and tickets before verification', async () => {
    const call = await createCall()
    const tickets = await ticketCount()
    expect((await send('GET', `/calls/${call}/customer`)).status).toBe(404)
    expect((await send('POST', `/calls/${call}/tickets`, { subject: 'Broken router' })).status).toBe(404)
    expect(await ticketCount()).toBe(tickets)
  })

  it('answers only not_verified on a wrong PIN, and 404 for the customer and tickets after it', async () => {
    const customer = await customerWithPin('Kofi Boateng')
    const call = await createCall()
    const response = await send('POST', `/calls/${call}/verify`, { customer_number: customer.number, pin: '000000' })
    expect(response.status).toBe(200)
    const text = await response.text()
    expect(JSON.parse(text)).toEqual({ result: 'not_verified', tries_left: 2 })
    expect(text).not.toContain('Kofi')

    expect((await send('GET', `/calls/${call}/customer`)).status).toBe(404)
    expect((await send('POST', `/calls/${call}/tickets`, { subject: 'Broken router' })).status).toBe(404)
    expect((await callOf(call)).customer_id).toBeNull()
  })

  it('answers locked once the call has no tries left, even for the right PIN', async () => {
    const customer = await customerWithPin()
    const call = await createCall()
    const answers = []
    for (const given of ['000000', '000001', '000002', pin]) {
      answers.push(await (await send('POST', `/calls/${call}/verify`, { customer_number: customer.number, pin: given })).json())
    }
    expect(answers.map((answer) => answer.result)).toEqual(['not_verified', 'not_verified', 'locked', 'locked'])
    expect((await callOf(call)).customer_id).toBeNull()
  })

  it('verifies the caller and keeps the call with that customer', async () => {
    const { call, customer } = await verifiedCall()
    expect((await callOf(call)).customer_id).toBe(customer.id)
    const other = await customerWithPin()
    const again = await send('POST', `/calls/${call}/verify`, { customer_number: other.number, pin })
    expect(again.status).toBe(409)
    expect((await callOf(call)).customer_id).toBe(customer.id)
  })

  it("gives the verified customer's name and tickets not solved", async () => {
    const { call, customer } = await verifiedCall()
    await app.sql`
      insert into public.tickets (customer_id, subject, status)
      values (${customer.id}, 'No dial tone', 'open'), (${customer.id}, 'Invoice question', 'pending'), (${customer.id}, 'Old issue', 'solved')`
    const response = await send('GET', `/calls/${call}/customer`)
    expect(response.status).toBe(200)
    const body = await response.json()
    expect(body.name).toBe('Ama Mensah')
    expect(body.tickets.map((ticket: { subject: string }) => ticket.subject).sort()).toEqual(['Invoice question', 'No dial tone'])
  })

  it('creates a ticket that belongs to the verified customer and the call, once per call', async () => {
    const { call, customer } = await verifiedCall()
    const response = await send('POST', `/calls/${call}/tickets`, { subject: 'Broken router', description: 'It blinks red.' })
    expect(response.status).toBe(201)
    const ticket = await response.json()
    expect(ticket).toMatchObject({ subject: 'Broken router', status: 'open', priority: null })

    const [stored] = await app.sql`select customer_id, description from public.tickets where id = ${ticket.id}`
    expect(stored).toEqual({ customer_id: customer.id, description: 'It blinks red.' })
    expect((await callOf(call)).ticket_id).toBe(ticket.id)

    const second = await send('POST', `/calls/${call}/tickets`, { subject: 'Another' })
    expect(second.status).toBe(409)
    expect((await second.json()).ticket).toBe(ticket.id)
  })

  it('refuses verify, customer and tickets once the call has ended, changing nothing', async () => {
    const { call } = await verifiedCall()
    expect((await send('POST', `/calls/${call}/status`, { status: 'ended' })).status).toBe(200)
    const tickets = await ticketCount()
    expect((await send('GET', `/calls/${call}/customer`)).status).toBe(409)
    expect((await send('POST', `/calls/${call}/tickets`, { subject: 'Broken router' })).status).toBe(409)
    expect(await ticketCount()).toBe(tickets)

    const customer = await customerWithPin()
    const unverified = await createCall()
    await send('POST', `/calls/${unverified}/status`, { status: 'ended' })
    expect((await send('POST', `/calls/${unverified}/verify`, { customer_number: customer.number, pin })).status).toBe(409)
    expect(await callOf(unverified)).toMatchObject({ customer_id: null, pin_failures: 0 })
  })
})
