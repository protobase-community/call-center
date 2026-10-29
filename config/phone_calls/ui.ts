import { l, view } from '@protobase/schema'
import type { phoneCalls } from './data'

const statusLabels = { incoming: 'Incoming', waiting: 'Waiting', active: 'Active', ended: 'Ended' }

export const phoneCallsView = view<typeof phoneCalls>('phone_calls')
  .names({ singular: 'Phone call', plural: 'Phone calls' })
  .title((r) => r.caller_number)
  .fields((r) => ({
    room_name: r.room_name.label('Room').format('code'),
    caller_number: r.caller_number.label('Caller').format('phone'),
    status: r.status.format('badge').valueLabels(statusLabels),
    customer_id: r.customer_id.label('Customer'),
    verified_at: r.verified_at.label('Verified').format('relative'),
    ticket_id: r.ticket_id.label('Ticket'),
    started_at: r.started_at.label('Started').format('relative'),
    waiting_since: r.waiting_since.label('Waiting since').format('relative'),
    answered_at: r.answered_at.label('Answered').format('relative'),
    ended_at: r.ended_at.label('Ended').format('relative'),
  }))
  .list((r) => ({ columns: [r.caller_number, r.status, r.customer_id, r.ticket_id, r.started_at], sort: [[r.started_at, 'desc']] }))
  .filters((r, w) => [w.facets(r.status), w.dateRange(r.started_at, { presets: ['7d', '30d', 'month'] })])
  .nav({
    recent: {
      status: 'status',
      tones: { incoming: 'info', waiting: 'warning', active: 'success' },
      pulse: ['incoming', 'waiting'],
      filter: 'status != "ended"',
      orderBy: 'started_at desc',
      limit: 20,
    },
  })
  .layout((r) => [
    l.section('Call', [r.caller_number, r.status, r.customer_id, r.verified_at, r.ticket_id]),
    l.section('Times', [r.started_at, r.waiting_since, r.answered_at, r.ended_at]),
    l.sidebar([r.status, r.customer_id, r.ticket_id, r.room_name]),
  ])
