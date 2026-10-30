import { badRequest, readJson } from '@protobase/server'

// The JSON object a function's request carries, and its values checked one by one: a refusal names the field, so an
// action's dialog shows it under the input of that name.

/** A 400 problem about one field of the body. */
export const invalidField = (field: string, message: string) => badRequest('invalid-body', message, { errors: [{ field, message }] })

/** The body as an object, refused unless it is one. */
export const objectOf = (body: unknown) => {
  if (typeof body !== 'object' || body === null || Array.isArray(body)) throw badRequest('invalid-body', 'Send a JSON object')
  return body as Record<string, unknown>
}

export const readBody = async (request: Request) => objectOf(await readJson(request))

/** The key of a record, a positive whole number. */
export const recordId = (body: Record<string, unknown>, field: string) => {
  const value = body[field]
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) throw invalidField(field, 'Give the key of a record')
  return value
}

/** A text value; an empty one counts as given. */
export const text = (body: Record<string, unknown>, field: string) => {
  const value = body[field]
  if (typeof value !== 'string') throw invalidField(field, 'Give a text')
  return value
}
