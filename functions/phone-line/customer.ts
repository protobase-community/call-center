import type { Kysely } from 'kysely'
import { verifiedCall } from './call-of'

/** GET /calls/<id>/customer: the verified customer's name and their tickets not solved yet, newest first. */
export const customer = async (db: Kysely<any>, key: number) => {
  const call = await verifiedCall(db, key)
  const { name } = await db.selectFrom('public.customers').select('name').where('id', '=', call.customer_id).executeTakeFirstOrThrow()
  const tickets = await db
    .selectFrom('public.tickets')
    .select(['id', 'subject', 'status', 'priority', 'created_at'])
    .where('customer_id', '=', call.customer_id)
    .where('status', '!=', 'solved')
    .orderBy('created_at', 'desc')
    .orderBy('id', 'desc')
    .execute()
  return Response.json({ name, tickets })
}
