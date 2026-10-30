import type { Kysely } from 'kysely'
import { HttpProblem } from '@protobase/server'
import { text } from '../_shared/read-body'
import { verifyCaller } from '../_shared/support-pin'
import { liveCall } from './call-of'

/**
 * POST /calls/<id>/verify { customer_number, pin }: the customer number and PIN the caller said, checked by the support
 * PIN module. The answer says only `verified`, `not_verified` with the tries the call has left, or `locked` once it has
 * none: never who the customer is, and the same for an unknown number, a wrong PIN and a locked customer. A call stays
 * with the customer it was verified as (409).
 */
export const verify = async (db: Kysely<any>, key: number, body: Record<string, unknown>) => {
  const customerNumber = text(body, 'customer_number')
  const pin = text(body, 'pin')
  const call = await liveCall(db, key)
  if (call.customer_id !== null) throw new HttpProblem(409, 'call-verified', 'Conflict', `Phone call ${key} is verified already`)

  const verification = await verifyCaller(db, { phoneCall: key, customerNumber, pin })
  if (verification.verified) return Response.json({ result: 'verified' })
  if (verification.triesLeft === 0) return Response.json({ result: 'locked' })
  return Response.json({ result: 'not_verified', tries_left: verification.triesLeft })
}
