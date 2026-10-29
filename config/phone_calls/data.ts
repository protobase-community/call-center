import { f, resource } from '@protobase/schema'

// The phone line writes a call's room, number, status and times, and the support PIN check its customer, each with
// rights of their own: through the API, staff only pick the ticket the call is about. Live, so the sidebar and the
// lists follow the line's changes.

/** public.phone_calls */
export const phoneCalls = resource('phone_calls')
  .table('public.phone_calls')
  .fields({
    id: f.integer().readOnly().filterable().sortable().dbDefault(),
    room_name: f.text().readOnly().filterable(),
    caller_number: f.text().optional().readOnly(),
    status: f.enum(['incoming', 'waiting', 'active', 'ended']).readOnly().filterable().sortable(),
    customer_id: f.relation('customers').optional().readOnly().filterable(),
    verified_at: f.timestamp().optional().readOnly(),
    ticket_id: f.relation('tickets').optional().filterable(),
    started_at: f.timestamp().readOnly().filterable().sortable().dbDefault(),
    waiting_since: f.timestamp().optional().readOnly(),
    answered_at: f.timestamp().optional().readOnly(),
    ended_at: f.timestamp().optional().readOnly(),
  })
  .primaryKey((r) => r.id)
  .live()
