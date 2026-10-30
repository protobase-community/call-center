import type { Kysely } from 'kysely'
import { HttpProblem } from '@protobase/server'
import { boundedText, optionalText } from './body'
import { verifiedCall } from './call-of'

/**
 * POST /calls/<id>/tickets { subject, description }: an open ticket for the call's verified customer, which becomes the
 * ticket the call is about. A call is about one ticket: a second is a 409 naming the first. The call's row stays locked
 * until both are written, so it cannot end or take another ticket meanwhile.
 */
export const createTicket = async (db: Kysely<any>, key: number, body: Record<string, unknown>) => {
  const subject = boundedText(body, 'subject', 1, 200)
  const description = optionalText(body, 'description', 10_000)
  return db.transaction().execute(async (trx) => {
    const call = await verifiedCall(trx, key, { lock: true })
    if (call.ticket_id !== null) {
      throw new HttpProblem(409, 'call-has-ticket', 'Conflict', `Phone call ${key} is about ticket ${call.ticket_id}`, { ticket: call.ticket_id })
    }
    const ticket = await trx
      .insertInto('public.tickets')
      .values({ customer_id: call.customer_id, subject, description, status: 'open' })
      .returning(['id', 'subject', 'status', 'priority', 'created_at'])
      .executeTakeFirstOrThrow()
    await trx.updateTable('public.phone_calls').set({ ticket_id: ticket.id }).where('id', '=', key).execute()
    return Response.json(ticket, { status: 201 })
  })
}
