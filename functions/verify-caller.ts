import { defineFunction } from '@protobase/server'
import { readBody, recordId, text } from './_shared/read-body'
import { verifyCaller } from './_shared/support-pin'

// POST /api/functions/verify-caller { "phone_call": 3, "customer_number": "100001", "pin": "482915" }: staff check the
// customer number and PIN a caller says. The answer is the module's: the customer on a match, otherwise only the tries
// the call has left, whatever was wrong.
export default defineFunction({ roles: ['agent', 'manager'] }, async (request, { records, db }) => {
  const body = await readBody(request)
  const phoneCall = recordId(body, 'phone_call')
  const customerNumber = text(body, 'customer_number')
  const pin = text(body, 'pin')
  // A call the caller may not read is not there, as in the REST API.
  await records.get('phone_calls', phoneCall)
  return Response.json(await verifyCaller(db, { phoneCall, customerNumber, pin }))
})
