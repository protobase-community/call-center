import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { phoneCallSocketPath } from '../config/phone_calls/call-address'
import { startApp } from './app'

// Joining the call on a phone call's record through functions/phone-call.ts, on a database of its own. The test app
// serves no WebSockets, so a caller the function admits gets 426 once it has, and one it refuses its problem.

let app: Awaited<ReturnType<typeof startApp>>

beforeAll(async () => {
  app = await startApp()
}, 60_000)

afterAll(async () => {
  await app?.close()
})

const admitted = 426

const insertCall = async (room_name: string, status: string) => {
  const [call] = await app.sql`
    insert into public.phone_calls (room_name, caller_number, status) values (${room_name}, '+31 20 555 0101', ${status})
    returning id`
  return call!.id as number
}

const readCall = async (id: number) => {
  const [call] = await app.sql`select status, answered_at from public.phone_calls where id = ${id}`
  return call!
}

describe('joining a phone call', () => {
  it('admits an agent, a manager and the phone line, and refuses anyone else', async () => {
    const id = await insertCall('call-roles', 'incoming')
    for (const role of ['agent', 'manager', 'phone_line']) {
      expect((await app.open(role, phoneCallSocketPath(id))).status).toBe(admitted)
    }
    for (const role of ['admin', 'customer']) {
      const response = await app.open(role, phoneCallSocketPath(id))
      expect(response.status).toBe(403)
      expect(await response.json()).toMatchObject({ type: expect.stringContaining('function-forbidden') })
    }
  })

  it('is refused once the call has ended', async () => {
    const id = await insertCall('call-ended', 'ended')
    for (const role of ['agent', 'phone_line']) {
      const response = await app.open(role, phoneCallSocketPath(id))
      expect(response.status).toBe(403)
      expect(await response.json()).toMatchObject({ type: expect.stringContaining('call-ended') })
    }
  })

  it('makes the call active when the first staff member joins, and not when the phone line does', async () => {
    const id = await insertCall('call-answered', 'waiting')
    expect((await app.open('phone_line', phoneCallSocketPath(id))).status).toBe(admitted)
    expect(await readCall(id)).toMatchObject({ status: 'waiting', answered_at: null })

    expect((await app.open('agent', phoneCallSocketPath(id))).status).toBe(admitted)
    const answered = await readCall(id)
    expect(answered).toMatchObject({ status: 'active', answered_at: expect.any(Date) })

    expect((await app.open('manager', phoneCallSocketPath(id))).status).toBe(admitted)
    expect(await readCall(id)).toEqual(answered)
  })
})
