import { badRequest } from '@protobase/server'
import { invalidField, objectOf } from '../_shared/read-body'

// The JSON object of a signed request, read from the body text the signature check gives, and the phone line's own
// values in it.

export const parseBody = (text: string) => {
  let body: unknown
  try {
    body = JSON.parse(text)
  } catch (error) {
    if (error instanceof SyntaxError) throw badRequest('malformed-json', 'The request body is not valid JSON')
    throw error
  }
  return objectOf(body)
}

/** A text of `min` to `max` characters. */
export const boundedText = (body: Record<string, unknown>, field: string, min: number, max: number) => {
  const value = body[field]
  if (typeof value !== 'string' || value.length < min || value.length > max) throw invalidField(field, `Give a text of ${min} to ${max} characters`)
  return value
}

/** A text of at most `max` characters, or NULL when it is missing or null. */
export const optionalText = (body: Record<string, unknown>, field: string, max: number) => {
  if (body[field] === undefined || body[field] === null) return null
  return boundedText(body, field, 0, max)
}
