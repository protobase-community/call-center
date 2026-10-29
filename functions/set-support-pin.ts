import { defineFunction } from '@protobase/server'
import { invalidField, readBody, recordId, text } from './_shared/read-body'
import { isPin, setPin } from './_shared/support-pin'

// POST /api/functions/set-support-pin { "customer": 7, "pin": "482915" }: staff set the PIN a customer verifies their
// calls with. Only its hash is stored, and the answer does not repeat it.
export default defineFunction({ roles: ['agent', 'manager'] }, async (request, { records, db }) => {
  const body = await readBody(request)
  const customer = recordId(body, 'customer')
  const pin = text(body, 'pin')
  if (!isPin(pin)) throw invalidField('pin', 'A support PIN is six digits')
  // A customer the caller may not read is not there, as in the REST API.
  await records.get('customers', customer)
  await setPin(db, { customer, pin })
  return Response.json({ customer })
})
