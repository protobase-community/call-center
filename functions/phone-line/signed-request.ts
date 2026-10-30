import { sql, type Kysely } from 'kysely'
import { HttpProblem, requireEnv, verifyStandardWebhook } from '@protobase/server'

// A request of the phone line: signed as Standard Webhooks sign theirs, with PHONE_LINE_SECRET (`whsec_` and base64),
// and fresh, its timestamp within five minutes of now. The signature covers the webhook-id, the timestamp and the body,
// not the method or path, so each message is taken once: a webhook-id seen before is refused, and the line signs every
// request, a retry too, with a new one. Ids are kept only as long as their timestamps could pass.

const toleranceSeconds = 300
const kept = sql`interval '10 minutes'`

/** The body of a request the phone line signed and has not sent before; a 401 problem otherwise, with nothing changed. */
export const signedBody = async (db: Kysely<any>, request: Request) => {
  const body = await verifyStandardWebhook(request, { secret: requireEnv('PHONE_LINE_SECRET'), toleranceSeconds })
  const id = request.headers.get('webhook-id')!
  if (id.length > 200) throw new HttpProblem(401, 'invalid-signature', 'Unauthorized', 'The webhook-id is longer than 200 characters')

  await db.deleteFrom('public.phone_line_messages').where('received_at', '<', sql<Date>`now() - ${kept}`).execute()
  const claimed = await db.insertInto('public.phone_line_messages').values({ id }).onConflict((oc) => oc.column('id').doNothing()).returning('id').executeTakeFirst()
  if (!claimed) throw new HttpProblem(401, 'replayed-message', 'Unauthorized', 'This webhook-id was sent before')
  return body
}
