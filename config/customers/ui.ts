import { l, view } from '@protobase/schema'
import type { customers } from './data'

// Setting and unlocking a PIN run functions of the app (protobase.ui.tsx): only they write the PIN's hash and counts.
const pinHelp = 'Six digits, which the customer keys or says when they call'

export const customersView = view<typeof customers>('customers')
  .names({ singular: 'Customer', plural: 'Customers' })
  .title((r) => r.name)
  .fields((r) => ({
    customer_number: r.customer_number.label('Customer number').format('code'),
    email: r.email.format('email'),
    phone: r.phone.format('phone'),
    pin_set_at: r.pin_set_at.label('PIN set').format('relative'),
    pin_failures: r.pin_failures.label('Wrong PINs').help('Wrong PINs within 24 hours of the first; five lock the PIN'),
    pin_failures_since: r.pin_failures_since.label('First wrong PIN').format('relative'),
    pin_locked_at: r.pin_locked_at.label('PIN locked').format('relative').help('A manager unlocks it'),
  }))
  .list((r) => ({ columns: [r.name, r.customer_number, r.email, r.phone], sort: [[r.name, 'asc']] }))
  .layout((r) => [
    l.section('Customer', [r.name, r.customer_number, r.email, r.phone]),
    l.section('Support PIN', [r.pin_set_at, r.pin_locked_at, r.pin_failures, r.pin_failures_since]),
    l.related('Tickets', { resource: 'tickets', field: 'customer_id', sort: 'updated_at desc' }),
    l.related('Phone calls', { resource: 'phone_calls', field: 'customer_id', sort: 'started_at desc' }),
    l.sidebar([r.customer_number, r.phone]),
  ])
  .actions((a) => [
    a.action('setSupportPin', { label: 'Set support PIN', icon: 'key', inputs: (i) => [i.text('pin', { label: 'Support PIN', help: pinHelp, max: 6 })] }),
  ])

/** Managers also unlock a PIN that wrong PINs locked. */
export const managerCustomersView = customersView.forRoles(['manager']).actions((a) => [
  a.action('setSupportPin', { label: 'Set support PIN', icon: 'key', inputs: (i) => [i.text('pin', { label: 'Support PIN', help: pinHelp, max: 6 })] }),
  a.action('unlockSupportPin', {
    label: 'Unlock support PIN',
    icon: 'door-open',
    confirm: 'Let callers try this customer’s PIN again?',
  }),
])
