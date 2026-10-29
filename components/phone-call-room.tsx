import { CallMark, RecordCall, useLayoutRecord, useSignedInUser } from '@protobase/ui'
import { callerMember, phoneCallSocketPath } from '../config/phone_calls/call-address'

/**
 * The call on a phone call's record page, behind `PhoneCallRoom` in config/phone_calls/ui.ts: Join while the call goes
 * on, and the call itself once the page joins it at the record's standard `?call=join` address.
 */
export const PhoneCallRoom = () => {
  const { key, record } = useLayoutRecord()!
  const user = useSignedInUser()
  if (record.status === 'ended') return null

  const nameOf = (member: string) => {
    if (member === callerMember) return 'Caller'
    if (member === user?.id) return user.name ?? 'You'
    return 'Staff member'
  }
  return (
    <div className="flex flex-col gap-3">
      <CallMark resource="phone_calls" recordKey={key} />
      <RecordCall resource="phone_calls" recordKey={key} url={phoneCallSocketPath(key)} nameOf={nameOf} />
    </div>
  )
}
