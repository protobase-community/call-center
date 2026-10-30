import type { Kysely } from 'kysely'
import { HttpProblem, notFound } from '@protobase/server'

// The phone call a route acts on. `db` here has no access rules, so these checks are the only ones: the line acts only
// for a call that has not ended, and reaches a customer only once the call is verified.

const largestKey = 2 ** 31 - 1

/** The call's key from the path, a 404 when it is no key a call can have. */
export const callKey = (text: string) => {
  const key = Number(text)
  if (!Number.isSafeInteger(key) || key < 1 || key > largestKey) throw notFound(`There is no phone call ${text}`)
  return key
}

export const callEnded = (key: number) => new HttpProblem(409, 'call-ended', 'Conflict', `Phone call ${key} has ended`)

/**
 * The call, unless it is missing (404) or ended (409). Pass a transaction to lock its row until it commits, so the
 * call cannot end or change customer meanwhile.
 */
export const liveCall = async (db: Kysely<any>, key: number, { lock = false } = {}) => {
  let query = db.selectFrom('public.phone_calls').select(['id', 'status', 'customer_id', 'ticket_id']).where('id', '=', key)
  if (lock) query = query.forUpdate()
  const call = await query.executeTakeFirst()
  if (!call) throw notFound(`There is no phone call ${key}`)
  if (call.status === 'ended') throw callEnded(key)
  return call
}

/** The live call with its verified customer; a 404 while the call is not verified, as if the customer were not there. */
export const verifiedCall = async (db: Kysely<any>, key: number, options?: { lock?: boolean }) => {
  const call = await liveCall(db, key, options)
  if (call.customer_id === null) throw notFound(`Phone call ${key} has no verified customer`)
  return { ...call, customer_id: call.customer_id as number }
}
