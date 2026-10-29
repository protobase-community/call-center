import { randomBytes, scrypt, timingSafeEqual } from 'node:crypto'
import { promisify } from 'node:util'
import { sql, type Kysely } from 'kysely'

// A caller's support PIN: staff set it, and a phone call is linked to the customer only when the customer number and
// the PIN match. Only an scrypt hash with a salt of its own is stored; the PIN itself is never stored, logged or
// answered. These functions write with the database's own rights, so callers check who may use them first.

/** Wrong PINs one call may give before its verification is over. */
export const callTries = 3
/** Wrong PINs a customer's number may be given within `customerWindow` before the PIN locks until a manager unlocks it. */
export const customerTries = 5
const customerWindow = sql`interval '24 hours'`

const scryptAsync = promisify(scrypt) as (pin: string, salt: Buffer, length: number) => Promise<Buffer>
const saltLength = 16
const hashLength = 32

/** Six digits, as a caller keys them on the phone. */
export const isPin = (pin: unknown): pin is string => typeof pin === 'string' && /^[0-9]{6}$/.test(pin)

/** The stored form of a PIN: `scrypt:<salt>:<hash>`, both base64, with a new random salt each time. */
export const hashPin = async (pin: string) => {
  const salt = randomBytes(saltLength)
  const hash = await scryptAsync(pin, salt, hashLength)
  return `scrypt:${salt.toString('base64')}:${hash.toString('base64')}`
}

/** Whether `pin` is the one `stored` was made from, compared in constant time. */
export const pinMatches = async (pin: string, stored: string) => {
  const [scheme, salt, hash] = stored.split(':')
  if (scheme !== 'scrypt' || !salt || !hash) throw new Error('Not a support PIN hash')
  const expected = Buffer.from(hash, 'base64')
  const actual = await scryptAsync(pin, Buffer.from(salt, 'base64'), expected.length)
  return timingSafeEqual(actual, expected)
}

// Checked in place of a hash when the customer number is unknown or has no PIN, so that answer takes as long as a wrong
// PIN: no PIN matches it but by a chance of 2^-256.
const decoyHash = 'scrypt:5TPIari2zI6QiZ23UG98LQ==:TzMQAoNiAaoCTATCWZVevRhCj15JGGBJ9UKJRVC6lSo='

/** Sets a customer's support PIN, replacing the one they had. */
export const setPin = async (db: Kysely<any>, { customer, pin }: { customer: number; pin: string }) => {
  if (!isPin(pin)) throw new Error('A support PIN is six digits')
  const support_pin_hash = await hashPin(pin)
  await db.updateTable('public.customers').set({ support_pin_hash, pin_set_at: sql`now()` }).where('id', '=', customer).execute()
}

/** Lets a customer's PIN be tried again: clears their wrong PINs and the lock. */
export const unlockPin = async (db: Kysely<any>, customer: number) => {
  await db
    .updateTable('public.customers')
    .set({ pin_failures: 0, pin_failures_since: null, pin_locked_at: null })
    .where('id', '=', customer)
    .execute()
}

/**
 * The same answer for an unknown customer number, a customer without a PIN, a locked PIN and a wrong PIN, so a caller
 * learns only how many tries the call has left.
 */
export type Verification = { verified: true; customerId: number } | { verified: false; triesLeft: number }

/**
 * Links `phoneCall` to the customer of `customerNumber` when `pin` is theirs and neither the call nor the customer is
 * locked; counts a wrong PIN on both otherwise. One transaction, with both rows locked, so tries on the same call or
 * customer at once are counted one after another.
 */
export const verifyCaller = (
  db: Kysely<any>,
  { phoneCall, customerNumber, pin }: { phoneCall: number; customerNumber: string; pin: string },
): Promise<Verification> =>
  db.transaction().execute(async (trx) => {
    const call = await trx
      .selectFrom('public.phone_calls')
      .select(['id', 'pin_failures'])
      .where('id', '=', phoneCall)
      .forUpdate()
      .executeTakeFirst()
    if (!call) throw new Error(`No phone call ${phoneCall}`)
    if (call.pin_failures >= callTries) return { verified: false, triesLeft: 0 }

    const customer = await trx
      .selectFrom('public.customers')
      .select(['id', 'support_pin_hash', 'pin_locked_at'])
      .where('customer_number', '=', customerNumber)
      .forUpdate()
      .executeTakeFirst()
    const matches = await pinMatches(pin, customer?.support_pin_hash ?? decoyHash)

    if (customer && customer.support_pin_hash && matches && !customer.pin_locked_at) {
      await trx.updateTable('public.phone_calls').set({ customer_id: customer.id, verified_at: sql`now()` }).where('id', '=', call.id).execute()
      await trx.updateTable('public.customers').set({ pin_failures: 0, pin_failures_since: null }).where('id', '=', customer.id).execute()
      return { verified: true, customerId: customer.id }
    }

    const failures = call.pin_failures + 1
    await trx.updateTable('public.phone_calls').set({ pin_failures: failures }).where('id', '=', call.id).execute()
    if (customer && !customer.pin_locked_at) await countCustomerFailure(trx, customer.id)
    return { verified: false, triesLeft: callTries - failures }
  })

// A wrong PIN on a customer: the count starts over when its first failure is older than the window, and reaching
// `customerTries` locks the PIN. Every expression reads the row as it was before the update.
const countCustomerFailure = async (trx: Kysely<any>, customer: number) => {
  const recent = sql<boolean>`pin_failures_since > now() - ${customerWindow}`
  const { pin_failures } = await trx
    .updateTable('public.customers')
    .set({
      pin_failures: sql`case when ${recent} then pin_failures + 1 else 1 end`,
      pin_failures_since: sql`case when ${recent} then pin_failures_since else now() end`,
    })
    .where('id', '=', customer)
    .returning('pin_failures')
    .executeTakeFirstOrThrow()
  if (pin_failures < customerTries) return
  await trx.updateTable('public.customers').set({ pin_locked_at: sql`now()` }).where('id', '=', customer).execute()
}
