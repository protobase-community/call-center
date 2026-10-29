import { defineRoles } from '@protobase/schema'

/**
 * Agents work customers and their tickets; managers do too, and may delete them. Both follow the phone calls and pick
 * the ticket a call is about; only the phone line and the support PIN check write the rest of a call. The phone line's
 * account only reads the calls, to join the call on one as its caller (functions/phone-call.ts).
 */
export const roles = defineRoles<'customers' | 'tickets' | 'phone_calls'>({
  admin: ['*'],
  agent: [
    'customers.read',
    'customers.create',
    'customers.update',
    'tickets.read',
    'tickets.create',
    'tickets.update',
    'phone_calls.read',
    'phone_calls.update',
  ],
  manager: [
    'customers.read',
    'customers.create',
    'customers.update',
    'customers.delete',
    'tickets.read',
    'tickets.create',
    'tickets.update',
    'tickets.delete',
    'phone_calls.read',
    'phone_calls.update',
  ],
  phone_line: ['phone_calls.read'],
})
