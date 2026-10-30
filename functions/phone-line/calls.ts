import { sql, type Kysely } from 'kysely'
import { HttpProblem, notFound } from '@protobase/server'
import { invalidField } from '../_shared/read-body'
import { boundedText, optionalText } from './body'
import { callEnded } from './call-of'

// A phone call as the line reports it: created incoming when the call comes in, then waiting in the queue, then ended.
// Staff joining makes it active (functions/phone-call.ts), never the line.

const answered = ['id', 'room_name', 'caller_number', 'status', 'started_at', 'waiting_since', 'ended_at'] as const

/** POST /calls { room_name, caller_number }: 201 with the new call, or 200 with the call the room already has. */
export const createCall = async (db: Kysely<any>, body: Record<string, unknown>) => {
  const room_name = boundedText(body, 'room_name', 1, 200)
  const caller_number = optionalText(body, 'caller_number', 40)
  const created = await db
    .insertInto('public.phone_calls')
    .values({ room_name, caller_number, status: 'incoming' })
    .onConflict((oc) => oc.column('room_name').doNothing())
    .returning(answered)
    .executeTakeFirst()
  if (created) return Response.json(created, { status: 201 })

  const existing = await db.selectFrom('public.phone_calls').select(answered).where('room_name', '=', room_name).executeTakeFirstOrThrow()
  return Response.json(existing)
}

/**
 * POST /calls/<id>/status { status }: `waiting` once the caller is in the queue, from incoming; `ended` once the call is
 * over, from any status. Each is idempotent and keeps the time it first happened. An ended call changes no more (409).
 */
export const setCallStatus = async (db: Kysely<any>, key: number, body: Record<string, unknown>) => {
  const status = body.status
  if (status !== 'waiting' && status !== 'ended') throw invalidField('status', 'Give waiting or ended')

  const update =
    status === 'waiting'
      ? db
          .updateTable('public.phone_calls')
          .set({ status, waiting_since: sql`coalesce(waiting_since, now())` })
          .where('status', 'in', ['incoming', 'waiting'])
      : db.updateTable('public.phone_calls').set({ status, ended_at: sql`coalesce(ended_at, now())` })
  const call = await update.where('id', '=', key).returning(answered).executeTakeFirst()
  if (call) return Response.json(call)

  const current = await db.selectFrom('public.phone_calls').select('status').where('id', '=', key).executeTakeFirst()
  if (!current) throw notFound(`There is no phone call ${key}`)
  if (current.status === 'ended') throw callEnded(key)
  throw new HttpProblem(409, 'call-answered', 'Conflict', `Phone call ${key} is ${current.status}: only an incoming call starts waiting`)
}
