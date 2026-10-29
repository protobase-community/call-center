import { defineFunction } from '@protobase/server'
import { readBody, recordId } from './_shared/read-body'
import { unlockPin } from './_shared/support-pin'

// POST /api/functions/unlock-support-pin { "customer": 7 }: a manager lets a customer's PIN be tried again after it
// locked on wrong PINs.
export default defineFunction({ roles: ['manager'] }, async (request, { records, db }) => {
  const customer = recordId(await readBody(request), 'customer')
  // A customer the caller may not read is not there, as in the REST API.
  await records.get('customers', customer)
  await unlockPin(db, customer)
  return Response.json({ customer })
})
