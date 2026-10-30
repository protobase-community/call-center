import { createHmac, randomBytes, randomUUID } from 'node:crypto'

// Signs a request as the phone line does, by the Standard Webhooks scheme: an HMAC-SHA256 of `<id>.<timestamp>.<body>`
// with the secret's base64 key, in the webhook-signature header as `v1,<base64>`.

export const newSecret = () => `whsec_${randomBytes(32).toString('base64')}`

export const signedHeaders = (secret: string, body: string, { id = randomUUID(), seconds = Math.floor(Date.now() / 1000) } = {}) => {
  const key = Buffer.from(secret.replace(/^whsec_/, ''), 'base64')
  const signature = createHmac('sha256', key).update(`${id}.${seconds}.${body}`).digest('base64')
  return { 'webhook-id': id, 'webhook-timestamp': String(seconds), 'webhook-signature': `v1,${signature}` }
}
