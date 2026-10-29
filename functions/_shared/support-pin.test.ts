import { describe, expect, it } from 'vitest'
import { hashPin, isPin, pinMatches } from './support-pin'

describe('a support PIN', () => {
  it('is six digits', () => {
    expect(isPin('012345')).toBe(true)
    for (const pin of ['12345', '1234567', '12345a', ' 123456', 123456, null]) expect(isPin(pin)).toBe(false)
  })

  it('is kept as a salted scrypt hash that does not hold the PIN', async () => {
    const stored = await hashPin('482915')
    expect(stored).toMatch(/^scrypt:[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+$/)
    expect(stored).not.toContain('482915')
  })

  it('gets a salt of its own each time it is set', async () => {
    expect(await hashPin('482915')).not.toBe(await hashPin('482915'))
  })

  it('matches only the PIN it was made from', async () => {
    const stored = await hashPin('482915')
    expect(await pinMatches('482915', stored)).toBe(true)
    expect(await pinMatches('482916', stored)).toBe(false)
    expect(await pinMatches('', stored)).toBe(false)
  })

  it('refuses a stored value that is no hash of this module', async () => {
    await expect(pinMatches('482915', '482915')).rejects.toThrow('Not a support PIN hash')
  })
})
