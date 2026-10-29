import { describe, expect, it } from 'vitest'
import { checkFilter, evaluateFilter, f, parseFilter, printFilter, resource, type ResourceModel } from '@protobase/schema'
import { customers, type Customer } from './customers'

// Checks, against the pinned release, that a first table like the README's customers takes data from anywhere: names,
// addresses, postal codes and phone numbers in every script, through the record validation, filters and search the API
// runs. Text fields need no pattern for names, postal codes or phone numbers: a regex such as /^[A-Za-z ]+$/ or
// /^\d{5}$/ refuses most of the world. Nothing here reaches a database.

const table = resource('customers')
  .table('public.customers')
  .fields({
    id: f.integer().readOnly().filterable().sortable().dbDefault(),
    name: f.text().min(1).max(200).filterable().sortable(),
    address: f.text().max(500),
    city: f.text().max(200).filterable(),
    postal_code: f.text().max(20).optional().filterable(),
    country: f.country().filterable(),
    phone: f.text().max(40).filterable(),
    currency: f.currency(),
    amount: f.decimal({ precision: 14, scale: 2 }),
    notes: f.text().optional(),
  })
  .primaryKey((r) => r.id)
  .search((r) => [r.name, r.city, r.phone.digitsEnd()])

const model = table.toModel()
const schema = table.recordSchema()
const record = (customer: Customer) => {
  const { word: _, ...fields } = customer
  return { id: 1, ...fields }
}

const filter = (text: string, resourceModel: ResourceModel = model) => {
  const parsed = parseFilter(text)
  if (!parsed.ok || !parsed.ast) throw new Error(`"${text}" does not parse: ${JSON.stringify(parsed.errors)}`)
  const checked = checkFilter(resourceModel, parsed.ast)
  if (!checked.ok) throw new Error(`"${text}" does not check: ${JSON.stringify(checked.errors)}`)
  return { printed: printFilter(parsed.ast), checked: checked.filter }
}
const finds = (text: string, customer: Customer) => evaluateFilter(filter(text).checked, record(customer), { search: model })
const quoted = (value: string) => JSON.stringify(value)
const lastDigits = (phone: string) => phone.replace(/\D/g, '').slice(-4)

describe.each(customers)('a customer in $country, $name', (customer) => {
  it('is a valid record', () => {
    expect(schema.safeParse(record(customer)).error?.issues).toBeUndefined()
  })

  it('is found by its exact name, through a filter that prints back as written', () => {
    const text = `name = ${quoted(customer.name)}`
    expect(filter(text).printed).toBe(text)
    expect(finds(text, customer)).toBe(true)
  })

  it('is found by a word of its name, whatever its case', () => {
    expect(finds(`search(${quoted(customer.word)})`, customer)).toBe(true)
  })

  it('is found by the last digits of its phone number', () => {
    expect(finds(`search(${quoted(lastDigits(customer.phone))})`, customer)).toBe(true)
  })
})

describe('text lengths', () => {
  it('count characters as a varchar(n) column does, so a name in emoji or rare CJK is not cut short', () => {
    const name = '𠮷野 👩🏽‍💻'
    const short = resource('people').table('people').fields({ id: f.integer(), name: f.text().max([...name].length) }).primaryKey((r) => r.id)
    expect(name.length).toBeGreaterThan([...name].length)
    expect(short.recordSchema().safeParse({ id: 1, name }).success).toBe(true)
  })
})

describe('codes', () => {
  it('take ISO 3166 countries and ISO 4217 currencies in capitals only', () => {
    const base = record(customers[0]!)
    expect(schema.safeParse({ ...base, country: 'jp' }).success).toBe(false)
    expect(schema.safeParse({ ...base, currency: 'yen' }).success).toBe(false)
  })
})

// Search that does not find what a person there would type yet. Each one passes while Protobase still misses it, so the
// day a release fixes it, its test fails and moves up into the checks above.
describe('known gaps in search', () => {
  const customer = (name: string, phone = '+90 212 252 61 40'): Customer => ({ ...customers[0]!, name, phone })

  it.fails('a Turkish dotted capital İ, which lower case writes as i plus a dot', () => {
    expect(finds('search("ilkay")', customer('İlkay Çelik'))).toBe(true)
  })

  it.fails('an accent typed as a separate mark (NFD) finds the same name written with a composed one (NFC)', () => {
    expect(finds(`search(${quoted('Zoë')})`, customer('Zoë Lambert'))).toBe(true)
  })

  it.fails('a phone number written in Arabic-Indic digits, as many people in Egypt and the Gulf write it', () => {
    expect(finds('search("4012")', customer('سارة المنصوري', '+٩٧١ ٤ ٣٩٨ ٤٠١٢'))).toBe(true)
  })
})
