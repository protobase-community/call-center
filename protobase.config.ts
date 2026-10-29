import { defineConfig } from '@protobase/config'

// The whole app, as one object; it grows as the app does. Its resources are found in config/. Its address and secret
// are Protobase's defaults, PROTOBASE_URL and PROTOBASE_SECRET, and its calls' LiveKit server LIVEKIT_URL,
// LIVEKIT_API_KEY and LIVEKIT_API_SECRET (see .env.example).
export default defineConfig(({ env }) => ({
  auth: {
    // No defaultRole on purpose: every account is created with an explicit role (`protobase users create --role`).
    roles: ['admin', 'agent', 'manager'],
  },
  // Every user works in tenant 1, which access rules can compare with an organization_id column.
  authenticate: { tenant: 1 },
  // Staff and the phone line meet in the call on a phone call's record (functions/phone-call.ts).
  calls: {
    backend: { kind: 'livekit', url: env.LIVEKIT_URL!, apiKey: env.LIVEKIT_API_KEY!, apiSecret: env.LIVEKIT_API_SECRET! },
  },
}))
