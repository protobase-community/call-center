import { describe, expect, it } from 'vitest'
import { HttpProblem } from '@protobase/server'
import { boundedText, optionalText, parseBody } from './body'
import { callKey } from './call-of'

const statusOf = (run: () => unknown) => {
  try {
    run()
  } catch (error) {
    if (error instanceof HttpProblem) return error.status
    throw error
  }
  return
}

describe('the body of a signed request', () => {
  it('is a JSON object', () => {
    expect(parseBody('{"room_name":"a"}')).toEqual({ room_name: 'a' })
    expect(statusOf(() => parseBody(''))).toBe(400)
    expect(statusOf(() => parseBody('[1]'))).toBe(400)
    expect(statusOf(() => parseBody('null'))).toBe(400)
  })

  it('holds texts within their bounds, an optional one as null when missing', () => {
    expect(boundedText({ subject: 'x' }, 'subject', 1, 3)).toBe('x')
    expect(statusOf(() => boundedText({ subject: '' }, 'subject', 1, 3))).toBe(400)
    expect(statusOf(() => boundedText({ subject: 'long' }, 'subject', 1, 3))).toBe(400)
    expect(statusOf(() => boundedText({ subject: 7 }, 'subject', 1, 3))).toBe(400)
    expect(optionalText({}, 'description', 3)).toBeNull()
    expect(optionalText({ description: null }, 'description', 3)).toBeNull()
    expect(optionalText({ description: '' }, 'description', 3)).toBe('')
  })
})

describe("a call's key in the path", () => {
  it('is a whole number a call can have, otherwise the call is not there', () => {
    expect(callKey('12')).toBe(12)
    for (const text of ['0', '-1', '1.5', 'abc', '', '2147483648']) expect(statusOf(() => callKey(text))).toBe(404)
  })
})
