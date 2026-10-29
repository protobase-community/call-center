import { defineRoles } from '@protobase/schema'

/** Agents work customers and their tickets; managers do too, and may delete them. */
export const roles = defineRoles<'customers' | 'tickets'>({
  admin: ['*'],
  agent: ['customers.read', 'customers.create', 'customers.update', 'tickets.read', 'tickets.create', 'tickets.update'],
  manager: [
    'customers.read',
    'customers.create',
    'customers.update',
    'customers.delete',
    'tickets.read',
    'tickets.create',
    'tickets.update',
    'tickets.delete',
  ],
})
