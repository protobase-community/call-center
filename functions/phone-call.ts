import { badRequest, defineFunction, forbidden, type FunctionRecords } from '@protobase/server'
import { callerMember, phoneCallParam } from '../config/phone_calls/call-address'

// Admits a member to the call on a phone call's record: staff as themselves, the phone line's account as the caller.
// Nobody joins a call that has ended, and a member is out within the minute once it ends. The first staff member to
// join answers the call: it becomes active, with rights of the function's own, since staff cannot write a call's status.

const staffRoles = ['agent', 'manager']

const refuseEnded = async (records: FunctionRecords, key: string) => {
  const { record } = await records.get('phone_calls', key)
  if (record.status === 'ended') throw forbidden('call-ended', `Phone call ${key} has ended`)
}

export default defineFunction({ roles: [...staffRoles, 'phone_line'] }, async (request, { session, records, db, calls, acceptWebSocket }) => {
  const key = new URL(request.url).searchParams.get(phoneCallParam)
  if (!key) throw badRequest('missing-phone-call', `The ${phoneCallParam} parameter names the phone call to join`)
  await refuseEnded(records, key)

  const staff = session.user.roles.some((role) => staffRoles.includes(role))
  const events = await calls.join({
    record: { resource: 'phone_calls', key },
    member: staff ? String(session.user.id) : callerMember,
    publish: ['microphone'],
    recheck: () => refuseEnded(records, key),
  })
  if (staff) {
    await db
      .updateTable('public.phone_calls')
      .set({ status: 'active', answered_at: new Date() })
      .where('id', '=', Number(key))
      .where('status', 'in', ['incoming', 'waiting'])
      .execute()
  }
  return acceptWebSocket(events)
})
