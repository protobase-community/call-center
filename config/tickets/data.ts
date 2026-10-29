import { f, resource } from '@protobase/schema'

/** public.tickets, with comments for the staff's notes. */
export const tickets = resource('tickets')
  .table('public.tickets')
  .fields({
    id: f.integer().readOnly().filterable().sortable().dbDefault(),
    customer_id: f.relation('customers').filterable().sortable(),
    subject: f.text().min(1).max(200),
    description: f.text().optional(),
    status: f.enum(['open', 'pending', 'solved']).default('open').filterable().sortable(),
    priority: f.enum(['low', 'normal', 'high', 'urgent']).optional().filterable().sortable(),
    created_at: f.timestamp().readOnly().filterable().sortable().dbDefault(),
    updated_at: f.timestamp().readOnly().filterable().sortable().dbDefault(),
  })
  .primaryKey((r) => r.id)
  .search((r) => [r.subject])
  .comments()
