// The address of the socket that admits a member to the call on a phone call's record (functions/phone-call.ts).

/** The query parameter that names the phone call. */
export const phoneCallParam = 'phone_call'

/** The socket's path for one phone call. */
export const phoneCallSocketPath = (key: string | number) =>
  `/api/functions/phone-call?${new URLSearchParams({ [phoneCallParam]: String(key) })}`

/** The member the phone line's account joins as; staff join as their user id. */
export const callerMember = 'caller'
