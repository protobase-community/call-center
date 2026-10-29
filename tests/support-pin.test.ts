import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { verifyCaller } from '../functions/_shared/support-pin'
import { startApp } from './app'

// A caller's support PIN through the app's functions, on a database of its own with the project's migrations: staff set
// it, and a phone call is linked to the customer only when the customer number and the PIN match.

let app: Awaited<ReturnType<typeof startApp>>

beforeAll(async () => {
  app = await startApp()
}, 60_000)

afterAll(async () => {
  await app?.close()
})

const pin = '482915'
const wrongPin = '482916'
let rooms = 0

const insertCustomer = async () => {
  const [customer] = await app.sql`insert into public.customers (name) values ('Ama Mensah') returning id, customer_number`
  return { id: customer!.id as number, number: customer!.customer_number as string }
}

const customerWithPin = async () => {
  const customer = await insertCustomer()
  const response = await app.invoke('agent', 'set-support-pin', { customer: customer.id, pin })
  expect(response.status).toBe(200)
  return customer
}

const insertCall = async () => {
  rooms += 1
  const [call] = await app.sql`insert into public.phone_calls (room_name, status) values (${`call-pin-${rooms}`}, 'active') returning id`
  return call!.id as number
}

const verify = async (phoneCall: number, customerNumber: string, given: string) => {
  const response = await app.invoke('agent', 'verify-caller', { phone_call: phoneCall, customer_number: customerNumber, pin: given })
  expect(response.status).toBe(200)
  return response.json()
}

const callOf = async (id: number) => (await app.sql`select customer_id, verified_at, pin_failures from public.phone_calls where id = ${id}`)[0]!
const customerOf = async (id: number) =>
  (await app.sql`select support_pin_hash, pin_failures, pin_failures_since, pin_locked_at from public.customers where id = ${id}`)[0]!

describe('setting a support PIN', () => {
  it('keeps only a salted hash and does not answer the PIN', async () => {
    const customer = await insertCustomer()
    for (const role of ['agent', 'manager']) {
      const response = await app.invoke(role, 'set-support-pin', { customer: customer.id, pin })
      expect(response.status).toBe(200)
      expect(await response.text()).not.toContain(pin)
    }
    const { support_pin_hash } = await customerOf(customer.id)
    expect(support_pin_hash).toMatch(/^scrypt:/)
    expect(support_pin_hash).not.toContain(pin)
  })

  it('takes six digits only, naming the PIN input', async () => {
    const customer = await insertCustomer()
    for (const given of ['12345', '1234567', '12345a']) {
      const response = await app.invoke('agent', 'set-support-pin', { customer: customer.id, pin: given })
      expect(response.status).toBe(400)
      expect((await response.json()).errors).toEqual([{ field: 'pin', message: 'A support PIN is six digits' }])
    }
    expect((await customerOf(customer.id)).support_pin_hash).toBeNull()
  })

  it('cannot be written as a field of the customer', async () => {
    const customer = await insertCustomer()
    const read = await app.request('manager', 'GET', `/customers/${customer.id}`)
    const response = await app.request('manager', 'PATCH', `/customers/${customer.id}`, { support_pin_hash: 'scrypt:a:b' }, { 'if-match': read.headers.get('etag')! })
    expect(response.status).toBe(400)
    expect((await customerOf(customer.id)).support_pin_hash).toBeNull()
  })
})

describe('verifying a caller', () => {
  it('leaves the call without a customer on a wrong PIN and links it on the right one', async () => {
    const customer = await customerWithPin()
    const call = await insertCall()

    expect(await verify(call, customer.number, wrongPin)).toEqual({ verified: false, triesLeft: 2 })
    expect(await callOf(call)).toMatchObject({ customer_id: null, verified_at: null, pin_failures: 1 })
    expect((await customerOf(customer.id)).pin_failures).toBe(1)

    expect(await verify(call, customer.number, pin)).toEqual({ verified: true, customerId: customer.id })
    expect(await callOf(call)).toMatchObject({ customer_id: customer.id, verified_at: expect.any(Date) })
    expect(await customerOf(customer.id)).toMatchObject({ pin_failures: 0, pin_failures_since: null })
  })

  it('answers an unknown customer number as it answers a wrong PIN', async () => {
    const customer = await customerWithPin()
    const unknown = await verify(await insertCall(), '999999999', pin)
    const wrong = await verify(await insertCall(), customer.number, wrongPin)
    expect(unknown).toEqual(wrong)
  })

  it('answers a customer without a PIN as it answers a wrong PIN', async () => {
    const customer = await insertCustomer()
    expect(await verify(await insertCall(), customer.number, '000000')).toEqual({ verified: false, triesLeft: 2 })
  })

  it('refuses the fourth try on a call, even with the right PIN', async () => {
    const customer = await customerWithPin()
    const call = await insertCall()
    for (const triesLeft of [2, 1, 0]) expect(await verify(call, customer.number, wrongPin)).toEqual({ verified: false, triesLeft })
    expect(await verify(call, customer.number, pin)).toEqual({ verified: false, triesLeft: 0 })
    expect(await callOf(call)).toMatchObject({ customer_id: null, pin_failures: 3 })
  })

  it('locks the customer on the fifth wrong PIN within 24 hours, across calls, until a manager unlocks it', async () => {
    const customer = await customerWithPin()
    const first = await insertCall()
    const second = await insertCall()
    for (let i = 0; i < 3; i++) await verify(first, customer.number, wrongPin)
    for (let i = 0; i < 2; i++) await verify(second, customer.number, wrongPin)
    expect((await customerOf(customer.id)).pin_locked_at).toEqual(expect.any(Date))

    // The sixth try, from a new call with the right PIN.
    const third = await insertCall()
    expect(await verify(third, customer.number, pin)).toEqual({ verified: false, triesLeft: 2 })
    expect((await callOf(third)).customer_id).toBeNull()

    expect((await app.invoke('agent', 'unlock-support-pin', { customer: customer.id })).status).toBe(403)
    expect((await app.invoke('manager', 'unlock-support-pin', { customer: customer.id })).status).toBe(200)
    expect(await customerOf(customer.id)).toMatchObject({ pin_failures: 0, pin_failures_since: null, pin_locked_at: null })
    expect(await verify(third, customer.number, pin)).toEqual({ verified: true, customerId: customer.id })
  })

  it('no longer counts wrong PINs older than 24 hours toward the lock', async () => {
    const customer = await customerWithPin()
    await app.sql`update public.customers set pin_failures = 4, pin_failures_since = now() - interval '25 hours' where id = ${customer.id}`
    await verify(await insertCall(), customer.number, wrongPin)
    expect(await customerOf(customer.id)).toMatchObject({ pin_failures: 1, pin_locked_at: null })

    await app.sql`update public.customers set pin_failures = 4, pin_failures_since = now() - interval '23 hours' where id = ${customer.id}`
    await verify(await insertCall(), customer.number, wrongPin)
    expect(await customerOf(customer.id)).toMatchObject({ pin_failures: 5, pin_locked_at: expect.any(Date) })
  })

  it('counts tries made at once one after another', async () => {
    const customer = await customerWithPin()
    const call = await insertCall()
    const answers = await Promise.all(
      Array.from({ length: 5 }, () => verifyCaller(app.db, { phoneCall: call, customerNumber: customer.number, pin: wrongPin })),
    )
    expect(answers.map((answer) => (answer.verified ? -1 : answer.triesLeft)).sort()).toEqual([0, 0, 0, 1, 2])
    expect((await callOf(call)).pin_failures).toBe(3)
    expect((await customerOf(customer.id)).pin_failures).toBe(3)
  })

  it('is open to agents and managers only, on a call they may read', async () => {
    const customer = await customerWithPin()
    const call = await insertCall()
    const body = { phone_call: call, customer_number: customer.number, pin }
    expect((await app.invoke('admin', 'verify-caller', body)).status).toBe(403)
    expect((await app.invoke('agent', 'verify-caller', { ...body, phone_call: call + 1000 })).status).toBe(404)
    expect((await app.invoke('manager', 'verify-caller', body)).status).toBe(200)
  })
})
