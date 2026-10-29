import { fileURLToPath } from 'node:url'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { loadProjectAuth } from '@protobase/cli/auth'
import { configExports, createAdmin } from '@protobase/server'
import * as config from './index'

// Protobase's own check that each example starts, run here against the pinned release through its public API: the
// app's admin API built with createAdmin over its own sign-in, as protobase.config.ts describes it, so a startup check
// such as an owner field that must hold the user ids refuses here instead of on the app's first start. Building the API
// reaches no database.

const root = fileURLToPath(new URL('..', import.meta.url))

describe('the app', () => {
  beforeAll(() => {
    vi.stubEnv('PROTOBASE_URL', 'http://localhost:5173')
    vi.stubEnv('PROTOBASE_SECRET', 'a-secret-only-this-test-uses-0123456789')
    vi.stubEnv('DATABASE_URL', 'postgres://nobody@127.0.0.1:1/none')
  })

  afterAll(() => {
    vi.unstubAllEnvs()
  })

  it('passes the startup checks with its own sign-in', async () => {
    const auth = await loadProjectAuth(root)
    const { resources, views, pages, userMenu, bottomBars, subscriptions } = configExports(config)
    const build = () =>
      createAdmin({
        resources,
        views,
        pages,
        ...(userMenu && { userMenu }),
        bottomBars,
        subscriptions,
        db: {} as never,
        authenticate: () => {
          throw new Error('No requests in this test')
        },
        auth,
      })
    expect(build).not.toThrow()
  }, 60_000)
})
