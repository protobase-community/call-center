import { l, view } from '@protobase/schema'
import type { customers } from './data'

export const customersView = view<typeof customers>('customers')
  .names({ singular: 'Customer', plural: 'Customers' })
  .title((r) => r.name)
  .fields((r) => ({
    customer_number: r.customer_number.label('Customer number').format('code'),
    email: r.email.format('email'),
    phone: r.phone.format('phone'),
  }))
  .list((r) => ({ columns: [r.name, r.customer_number, r.email, r.phone], sort: [[r.name, 'asc']] }))
  .layout((r) => [
    l.section('Customer', [r.name, r.customer_number, r.email, r.phone]),
    l.related('Tickets', { resource: 'tickets', field: 'customer_id', sort: 'updated_at desc' }),
    l.related('Phone calls', { resource: 'phone_calls', field: 'customer_id', sort: 'started_at desc' }),
    l.sidebar([r.customer_number, r.phone]),
  ])
