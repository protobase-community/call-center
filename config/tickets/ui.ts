import { l, view } from '@protobase/schema'
import type { tickets } from './data'

const statusLabels = { open: 'Open', pending: 'Pending', solved: 'Solved' }
const priorityLabels = { low: 'Low', normal: 'Normal', high: 'High', urgent: 'Urgent' }

export const ticketsView = view<typeof tickets>('tickets')
  .names({ singular: 'Ticket', plural: 'Tickets' })
  .title((r) => r.subject)
  .fields((r) => ({
    customer_id: r.customer_id.label('Customer'),
    description: r.description.multiline(),
    status: r.status.format('badge').valueLabels(statusLabels),
    priority: r.priority.format('badge').valueLabels(priorityLabels),
    updated_at: r.updated_at.label('Updated').format('relative'),
  }))
  .list((r) => ({ columns: [r.subject, r.customer_id, r.status, r.priority, r.updated_at], sort: [[r.updated_at, 'desc']] }))
  .filters((r, w) => [w.facets(r.status), w.facets(r.priority), w.dateRange(r.created_at, { presets: ['7d', '30d', 'month'] })])
  .layout((r) => [
    l.section('Ticket', [r.customer_id, r.subject, r.description]),
    l.section('Handling', [r.status, r.priority]),
    l.sidebar([r.status, r.priority, r.customer_id]),
    l.comments('Notes'),
  ])
