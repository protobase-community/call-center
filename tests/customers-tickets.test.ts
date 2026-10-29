import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { startApp } from './app'
import { customers } from './customers'

// Customers and tickets through the app's API, on a database of their own with the project's migrations: an agent
// keeps customers from anywhere as they are written and works their tickets.

let app: Awaited<ReturnType<typeof startApp>>

beforeAll(async () => {
  app = await startApp()
}, 60_000)

afterAll(async () => {
  await app?.close()
})

const createCustomer = async (role: string, fields: Record<string, unknown>) => {
  const response = await app.request(role, 'POST', '/customers', fields)
  expect(response.status).toBe(201)
  return (await response.json()) as { id: number; customer_number: string }
}

describe.each(customers)('a customer in $country', (customer) => {
  it('is kept with its name, email address and phone number as written', async () => {
    const { name, email, phone } = customer
    const created = await createCustomer('agent', { name, email, phone })
    const read = await app.request('agent', 'GET', `/customers/${created.id}`)
    expect(await read.json()).toMatchObject({ name, email, phone, customer_number: expect.stringMatching(/^[0-9]+$/) })
  })
})

describe('a ticket', () => {
  it('is created for a customer and updated by an agent', async () => {
    const customer = await createCustomer('agent', { name: customers[0]!.name })
    expect(customer).toMatchObject({ email: null, phone: null })

    const created = await app.request('agent', 'POST', '/tickets', { customer_id: customer.id, subject: 'Parcel not delivered' })
    expect(created.status).toBe(201)
    const ticket = await created.json()
    expect(ticket).toMatchObject({ customer_id: customer.id, status: 'open', priority: null, description: null })

    const updated = await app.request(
      'agent',
      'PATCH',
      `/tickets/${ticket.id}`,
      { status: 'pending', priority: 'high' },
      { 'if-match': created.headers.get('etag')! },
    )
    expect(updated.status).toBe(200)
    expect(await updated.json()).toMatchObject({ status: 'pending', priority: 'high' })

    const listed = await app.request('agent', 'GET', `/tickets?filter=${encodeURIComponent(`customer_id = ${customer.id}`)}`)
    expect((await listed.json()).items).toMatchObject([{ id: ticket.id, status: 'pending' }])
  })

  it('may not be deleted by an agent, and may by a manager', async () => {
    const customer = await createCustomer('manager', { name: customers[1]!.name })
    const ticket = await (await app.request('manager', 'POST', '/tickets', { customer_id: customer.id, subject: 'Wrong invoice' })).json()
    expect((await app.request('agent', 'DELETE', `/tickets/${ticket.id}`)).status).toBe(403)
    expect((await app.request('manager', 'DELETE', `/tickets/${ticket.id}`)).status).toBe(204)
  })

  it('takes only the statuses it has', async () => {
    const customer = await createCustomer('agent', { name: customers[2]!.name })
    const response = await app.request('agent', 'POST', '/tickets', { customer_id: customer.id, subject: 'Refund', status: 'closed' })
    expect(response.status).toBe(400)
  })
})
