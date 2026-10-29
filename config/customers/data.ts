import { f, resource } from '@protobase/schema'

// Names, email addresses and phone numbers are plain text, as people write them anywhere: a pattern refuses most of the
// world. The phone number is for display; a caller is never identified by it.

/** public.customers */
export const customers = resource('customers')
  .table('public.customers')
  .fields({
    id: f.integer().readOnly().filterable().sortable().dbDefault(),
    name: f.text().min(1).max(200).filterable().sortable(),
    customer_number: f.text().regex(/^[0-9]{1,20}$/, 'Use digits only, as a caller keys them on the phone').filterable().sortable().dbDefault(),
    email: f.text().max(320).optional().filterable(),
    phone: f.text().max(40).optional(),
    created_at: f.timestamp().readOnly().filterable().sortable().dbDefault(),
  })
  .primaryKey((r) => r.id)
  .search((r) => [r.name, r.customer_number, r.email, r.phone.digitsEnd()])
