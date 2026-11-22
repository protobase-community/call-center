// The staff side of run.sh's calls, in Chromium: a staff member signs in with their password, joins
// the call on the newest phone call's record and says a line, and what the caller's member sent is
// saved. Between calls an admin revokes the phone line's sessions, so the bridge must sign in again.
//   bun driver.ts <out dir> hold          joins once the caller waits on hold, until the call ends
//   bun driver.ts <out dir> staff-first   joins while the assistant has the caller, then leaves
//   bun driver.ts <out dir> revoke        revokes the phone line's sessions
//   bun driver.ts <out dir> sessions      writes how many sessions the phone line has
// Environment: APP_URL, DATABASE_URL, STAFF_EMAIL and STAFF_PASSWORD, ADMIN_EMAIL and
// ADMIN_PASSWORD, PHONE_LINE_EMAIL, STAFF_PAGE (the bundled staff-page.ts), CLIPS_DIR.
import { readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import postgres from 'postgres'
import { chromium, type APIRequestContext, type Page } from 'playwright'

const env = (name: string) => {
  const value = process.env[name]
  if (!value) throw new Error(`${name} is not set`)
  return value
}

const out = process.argv[2]!
const step = process.argv[3]!
const app = env('APP_URL')
const sql = postgres(env('DATABASE_URL'), { max: 1, onnotice: () => {} })
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

// Sent with an Origin, as the app's own sign-in page would, since the request context keeps cookies.
const signIn = async (request: APIRequestContext, email: string, password: string) => {
  const response = await request.post(`${app}/api/auth/sign-in/email`, { data: { email, password }, headers: { Origin: app } })
  if (!response.ok()) throw new Error(`The sign-in of ${email} answered ${response.status()}`)
}

const phoneLineSessions = async () => {
  const [row] = await sql`
    select count(*)::int as sessions from auth.session s join auth."user" u on u.id = s.user_id where u.email = ${env('PHONE_LINE_EMAIL')}`
  return row!.sessions as number
}

type PhoneCall = { id: number; status: string; started_at: Date }

/** The newest phone call started after `since`, once it reaches one of `statuses`. */
const phoneCall = async (since: Date, statuses: string[], timeoutMs: number): Promise<PhoneCall> => {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const [call] = await sql<PhoneCall[]>`
      select id, status, started_at from public.phone_calls where started_at > ${since} order by id desc limit 1`
    if (call && statuses.includes(call.status)) return call
    await sleep(200)
  }
  throw new Error(`No phone call reached ${statuses.join(' or ')} within ${timeoutMs / 1000} s`)
}

const steps: { at: number; step: string; detail?: unknown }[] = []
const mark = (name: string, detail?: unknown) => steps.push({ at: Date.now(), step: name, ...(detail !== undefined && { detail }) })

const staffPage = async () => {
  const browser = await chromium.launch({
    args: ['--mute-audio', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--autoplay-policy=no-user-gesture-required'],
  })
  const context = await browser.newContext()
  await signIn(context.request, env('STAFF_EMAIL'), env('STAFF_PASSWORD'))
  const page = await context.newPage()
  page.on('pageerror', (error) => mark('page error', error.message))
  await page.goto(`${app}/`)
  await page.addScriptTag({ content: await readFile(env('STAFF_PAGE'), 'utf8'), type: 'module' })
  await page.waitForFunction(() => window.staff !== undefined)
  return { browser, page }
}

const say = async (page: Page, name: string) => {
  const clip = (await readFile(path.join(env('CLIPS_DIR'), `${name}.wav`))).toString('base64')
  await page.evaluate(([n, c]) => window.staff.say(n!, c!), [name, clip])
}

const saveRecording = async (page: Page) =>
  writeFile(path.join(out, `${step}-staff.webm`), Buffer.from(await page.evaluate(() => window.staff.recording()), 'base64'))

const saveEvents = async (page: Page, call: PhoneCall) => {
  const events = await page.evaluate(() => window.staff.events())
  await writeFile(path.join(out, `${step}-staff.json`), JSON.stringify({ call: call.id, started_at: call.started_at, steps, events }, null, 1))
}

if (step === 'revoke') {
  const browser = await chromium.launch()
  const context = await browser.newContext()
  await signIn(context.request, env('ADMIN_EMAIL'), env('ADMIN_PASSWORD'))
  const [user] = await sql`select id from auth."user" where email = ${env('PHONE_LINE_EMAIL')}`
  const response = await context.request.post(`${app}/api/auth/admin/revoke-user-sessions`, { data: { userId: user!.id }, headers: { Origin: app } })
  if (!response.ok()) throw new Error(`Revoking the phone line's sessions answered ${response.status()}`)
  await browser.close()
} else if (step === 'sessions') {
  await writeFile(path.join(out, 'sessions.txt'), `${await phoneLineSessions()}\n`, { flag: 'a' })
} else if (step === 'hold' || step === 'staff-first') {
  const since = new Date()
  const { browser, page } = await staffPage()
  await writeFile(path.join(out, `${step}-ready`), '')
  let call: PhoneCall
  if (step === 'hold') {
    // a few seconds of hold music, then the staff member joins
    call = await phoneCall(since, ['waiting'], 120_000)
    mark('waiting', call.id)
    await sleep(6000)
  } else {
    call = await phoneCall(since, ['incoming'], 60_000)
    mark('incoming', call.id)
    await sleep(2000)
  }
  await page.evaluate((id) => window.staff.join(id), call.id)
  mark('joined')
  await sleep(3000)
  await say(page, 'staff-line')
  if (step === 'hold') {
    await phoneCall(since, ['ended'], 120_000)
    mark('call ended')
    await saveRecording(page)
  } else {
    // stays until 40 s into the call, past the caller's line, then hands the caller back
    await sleep(Math.max(0, call.started_at.getTime() + 40_000 - Date.now()))
    await saveRecording(page)
    await page.evaluate(() => window.staff.leave())
    mark('left')
  }
  await saveEvents(page, call)
  await browser.close()
} else {
  throw new Error(`Unknown step ${step}`)
}
await sql.end()
