# Call center

An example of an AI call center built with Protobase: people call a number and an AI voice assistant answers, or they
wait in a queue with hold music, while staff see the incoming, waiting and active calls, join any of them, verify the
caller with a support PIN and work the caller's ticket and customer record.

This part is the app the staff work in: **customers**, each with the customer number a caller keys on the phone, an
email address and a phone number, and their **tickets**, open, pending or solved, with comments for the staff's notes.
A customer's page lists their tickets. Agents work customers and tickets, managers too and may delete them, and admins
manage the accounts. A phone number is only shown: a caller is never identified by it.

Each **phone call** is a live record: incoming while the AI assistant has the caller, waiting in the queue, active once
a person is in the call, then ended. The sidebar lists the calls that have not ended, with a dot for their status, and
the pages of a customer and a ticket list their calls. Staff read the calls and pick the ticket a call is about; the
phone line writes the rest, and the support PIN check the verified customer.

Staff join a call from its page with **Join**, at the call's own address, `/phone_calls/<id>?call=join`, as a manager
at any time or an agent when the caller asks for a person; nobody joins a call that has ended, and whoever is in it
leaves within the minute once it ends. The phone line joins the same call as the caller, through an account of its own
with the `phone_line` role, which only reads the calls. The first staff member to join answers the call: it becomes
active. A person who joins takes the call over from the assistant. The call's audio goes through a LiveKit server,
`LIVEKIT_URL` with `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`.

A call reaches a customer only through their **support PIN**. Agents and managers set a customer's PIN of six digits
(**Set support PIN** on the customer's page); only a salted scrypt hash of it is kept, which no role reads. On a call's
page, **Verify caller** takes the customer number and PIN the caller says, and links the call to that customer only
when both match; a wrong PIN, an unknown number and a locked PIN get the same answer. Three wrong PINs end a call's
verification, and five on one customer within 24 hours lock their PIN, whichever calls they came from, until a manager
chooses **Unlock support PIN**.

The phone line reports its calls and acts for a verified caller through one public function, `/api/functions/phone-line`,
whose every request is signed by the [Standard Webhooks](https://www.standardwebhooks.com) scheme with
`PHONE_LINE_SECRET`. A request without a valid signature, with a timestamp more than five minutes off, or with a
`webhook-id` sent before is refused with 401 and changes nothing, so the line signs each request, a retry too, anew.

| Route | Body | Answer |
| --- | --- | --- |
| `POST /calls` | `{ room_name, caller_number }` | 201 with the new incoming call, or 200 with the call the room already has |
| `POST /calls/<id>/status` | `{ status }`: `waiting` or `ended` | 200 with the call; 409 when it has ended, or is active and asked to wait |
| `POST /calls/<id>/verify` | `{ customer_number, pin }` | `{ result }`: `verified`, `not_verified` with `tries_left`, or `locked` |
| `GET /calls/<id>/customer` | | `{ name, tickets }`: the verified customer's name and tickets not solved |
| `POST /calls/<id>/tickets` | `{ subject, description }` | 201 with an open ticket of the verified customer, which the call is then about |

The customer and ticket routes answer 404 while the call is not verified, and they and the verify route 409 once
the call has ended. A call is verified as one customer and is about one ticket: a second is a 409.

<gap>The call view cannot name the other staff members in a call because the app has no organizations, whose member list gives their names.</gap>
<gap>The phone line cannot join calls while the sign-in policy requires two-factor authentication or passkeys because a sign-in policy exception for service accounts is not implemented in Protobase.</gap>

## Run it locally

You need [Bun](https://bun.sh) 1.4 and Docker.

```sh
bun install
bun run db:up                     # Postgres 18 in Docker on port 55432; creates .env from .env.example
bun run db:migrate
bun run protobase skill install   # gives Claude Code, Codex and other agents the Protobase docs of this version
bun run protobase users create you@example.com --role admin --generate-password
bun run dev                       # http://localhost:5173
bun run test
```

Set your own `PROTOBASE_SECRET` in `.env` (`openssl rand -base64 32`). `bun run db:down` stops the database. The
calls' media goes through the phone stack's LiveKit server (see below), as the phone line's does: one server for both,
as in production.

The phone line signs in with an ordinary account of the `phone_line` role and a password, and joins calls with its
session cookie. Create it with the password on standard input:

```sh
bun run protobase users create phone-line@example.com --role phone_line --password-stdin
```

## The phone side

`phone/` holds the phone side: an AI agent on [LiveKit Agents](https://docs.livekit.io/agents/) that answers each
call through OpenAI's gpt-realtime-2.1. LiveKit SIP takes the call and puts it in a room of its own (`call-…`), and
the dispatch rule sends the `call-center-agent` agent there. Keys the caller presses reach the model as a message
such as `{"keypad": "42"}`, one per sequence, which ends at the pound key or after 3 seconds.

The agent works for the app through its phone line: `CALL_CENTER_URL` names the `phone-line` function, such as
`https://example.com/api/functions/phone-line`, and `CALL_CENTER_SECRET` is the app's `PHONE_LINE_SECRET`. Both are
required, and the agent does not start with one missing or malformed; plain http is taken only on the same machine.
It registers each call with the caller's number, and reports it ended when the caller hangs up or the agent does.
Before anything about an account, the agent puts the keypad in PIN entry: the caller's next two sequences, the
customer number and the PIN, go straight to the app's check, never to the model, a log or the transcript, and the
model hears only `{"verified": true}`, `false` or `"locked"`. Once the caller is verified, it reads their name and
open tickets and opens a new ticket for them; before that, these tools refuse.

A caller who asks for a person waits in the queue: the agent says it is finding someone, sets the call `waiting`, so
staff see it among the waiting calls, stops listening and plays hold music in the caller's own room, looped through
LiveKit Agents' `BackgroundAudioPlayer`. Keys pressed meanwhile are ignored, unless PIN entry is on. The wait ends when
a staff member joins the call (see the bridge below), when the caller hangs up, or after `MAX_WAIT_MINUTES` (5 when
unset): then the music stops and the agent offers to open a ticket instead, or puts the caller back in the queue. The music is `phone/hold_music/hold-music.ogg`, self-made and
public domain (CC0), see its README; `HOLD_MUSIC_FILE` names another file.
<gap>A caller who takes a ticket after the longest wait stays waiting in the app because the phone line has no route that takes a call back from the queue.</gap>

### The bridge

Staff and the caller meet through a bridge, the phone package's second process beside the agent. Once the agent has
registered a call, it sends the bridge to the call's room through LiveKit's agent dispatch. The bridge signs in to the
app as the `phone_line` account (`PHONE_LINE_EMAIL` and `PHONE_LINE_PASSWORD`, without which it does not start),
joins the Protobase call on the call's record as member `caller` through the `phone-call` function, and carries the
audio both ways until the caller hangs up:

```text
  phone ──SIP──▶ SIP room call-…                               Protobase call on /phone_calls/<id>
                 ┌───────────────────────────┐                ┌──────────────────────────────┐
                 │ caller                    │                │                              │
                 │ assistant                 │── one mix ────▶│ member `caller` (the bridge) │
                 │ hold music                │                │                              │
                 │ the bridge's track        │◀──── one mix ──│ staff members ◀──▶ browsers  │
                 └───────────────────────────┘                └──────────────────────────────┘
```

Neither side hears itself: the call gets the room without the bridge's own track, and the room gets the staff members
without what the bridge sends. When a staff member is in the call, the hold music stops and the assistant hears and
says nothing; when the last one leaves while the caller is still there, the assistant takes over again.

The bridge keeps the session cookie of its password sign-in in memory and joins every call with it, so its sockets
outlive any token. A join refused with 401, such as after an admin revoked the session, signs in again once; a
second refusal, or a refused sign-in such as a wrong password, gives up on that call, which stays with the assistant.
Neither the password nor the cookie goes into a log.
<gap>The bridge cannot carry a call whose app sends media peer to peer because only the LiveKit media path is implemented.</gap>
<gap>A bridge whose socket to the app drops cannot rejoin the call because resuming a call session is not implemented in the bridge.</gap>

### Run the phone side locally

`phone/sip/inbound-trunk.json` is for local development only: its password is in this repository. For a real
trunk, write a trunk file with a long random password outside the repository and name it as `SIP_TRUNK_FILE` in
`phone/.env`. The setup refuses a trunk without a digest username and password.

Run it with [uv](https://docs.astral.sh/uv/) and Docker, beside the app's `bun run dev`. The phone stack's LiveKit
server carries the app's calls too, so the app's `.env` names its key pair:

```sh
cd phone
uv sync
cp .env.example .env              # set OPENAI_API_KEY, and LIVEKIT_API_SECRET to `openssl rand -hex 32`
```

- In `phone/.env`, set `CALL_CENTER_URL=http://localhost:5173/api/functions/phone-line`, `CALL_CENTER_SECRET` to a
  new `whsec_` secret, and `PHONE_LINE_EMAIL` and `PHONE_LINE_PASSWORD` to the phone line's account.
- In the app's `.env`, set `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` to the pair in `phone/.env`, and
  `PHONE_LINE_SECRET` to the same `whsec_` secret, then restart `bun run dev`.

```sh
docker compose up --build         # LiveKit, LiveKit SIP, Redis, the trunk's setup, the agent and the bridge
tests/sip_call/run.sh             # SIPp calls: two refused, one the agent must greet and answer, one with a PIN,
                                  # one that asks for a person
tests/bridge_call/run.sh          # SIPp callers and a staff member in Chromium, through the app
uv run pytest && uv run pyright && uv run ruff check src tests
```

The agent and the bridge run on the host's network, so the app on port 5173 is on their loopback and the agent's
plain http rule holds; they listen on loopback only. With Docker Desktop, turn on its host networking.

The SIPp calls cost a few cents of model use. The first saves what the caller heard as
`phone/sip-call-out/agent.wav`. The second keys a wrong, then the right PIN and asks for a ticket, against a stand-in
of the app's phone line that checks signatures as the app does and logs what it answered to
`phone/sip-call-out/phone-line.jsonl`; `run.sh` points the agent at it with a secret of its own. The third asks for
a person and must hear the hold music without a pause from 12 to 27 seconds after its request, and see the stand-in set
the call `waiting`; the agent's side is in `phone/sip-call-out/person-agent.wav`.

`tests/bridge_call/run.sh` goes through the app itself: it starts `bun run dev` on the database of the app's `.env`,
with accounts and a phone line secret of its own, and the phone stack against it. A caller waits on hold until a staff
member joins in Chromium through `@protobase/client/calls`, then each says a line, recorded on both sides: each side
must hear the other's line and not its own, and neither the music nor the assistant. A second caller's staff member
joins while the assistant talks, after an admin revoked the phone line's session, and leaves again, after which the
assistant must speak. A third call runs the bridge on a wrong password: it must give up after one sign-in. Its
output goes to `/tmp/call-center-bridge-call`, outside the project, since `bun run dev` restarts the calls' sockets on
any change in it.

Every published port listens on 127.0.0.1 only, and LiveKit runs on the key pair from `.env`, never in dev mode.

<gap>A provider that delivers calls only to a registered phone cannot reach the agent because a SIP registration bridge is not implemented.</gap>

## Use it as a template

Press **Use this template** at the top of this page, then **Create a new repository**, to get your own copy with a
clean history. Clone it and run it as above:

```sh
git clone https://github.com/<you>/<your-repository>.git
cd <your-repository>
```

You can also fork it to contribute back, or start from it with `git clone https://github.com/protobase-community/starter.git`.

## Customise it

A new table, a list of orders for example:

1. Write the migration `db/migrations/012_orders.sql`, numbered after the last one, and run `bun run db:migrate`.
2. Run `bun run protobase scaffold <connection string> --ui` to write `config/orders/data.ts` and
   `config/orders/ui.ts` from the table, or write them yourself.
3. Export them from `config/index.ts`: `export * from './orders/data'` and `export * from './orders/ui'`.
4. `bun run dev` shows the new list and record page.

- **Tables and screens.** Each table's data config is in `config/<name>/data.ts` (fields, validation, who may read
  and change what) and its screens in `config/<name>/ui.ts` (lists, filters, record pages), all exported from
  `config/index.ts`. See the [data config](https://docs.protobase.net/reference/data-config/) and [UI config](https://docs.protobase.net/reference/ui-config/)
  references.
- **Database changes.** Add a migration in `db/migrations/`, numbered after the last one, and run
  `bun run db:migrate`. Never edit a migration that has run. For a new table, `bun run protobase scaffold
  <connection string> --ui` reads the database and writes its `data.ts` and `ui.ts`, which you then adjust.
- **Sign-in and accounts** are the `auth` of `protobase.config.ts`, on Better Auth ([Login](https://docs.protobase.net/reference/auth/)).
- **Coding agents.** [AGENTS.md](AGENTS.md) holds the rules an assistant follows when it changes the app.
- **Data from anywhere.** `tests/locales.test.ts` checks that a table like the customers takes names,
  addresses, postal codes and phone numbers from many countries and scripts. Plain `f.text()` fields take them all; a
  pattern such as `/^[A-Za-z ]+$/` for names or `/^\d{5}$/` for postal codes refuses most of the world. The made-up
  customers in `tests/customers.ts` are there for your own tests;
  `tests/customers-tickets.test.ts` keeps each of them through the app's API, on a Postgres database of its own.
- Check every change with `bun run typecheck`, `bun run test`, `bun run build` and, after `bun run db:migrate`,
  `bun run doctor`, as CI does. Doctor checks the config against the database, such as the index each filterable or
  sortable field needs; Protobase Cloud runs it before it deploys.

## Deploy it on Protobase Cloud

Push your copy to GitHub, then in the [console](https://console.protobase.net) press **New app** and pick **An existing
GitHub repository**. Protobase keeps the app in sync with the repository and deploys every push that passes
`db:migrate`, `typecheck`, `test` and doctor. New to the cloud? [Start here](https://console.protobase.net/start).

## Built with Protobase

[Protobase](https://github.com/PrototeamHQ/protobase) builds the app from a Postgres database and a typed config: each table's data config sits in
`config/<name>/data.ts` and its screens in `config/<name>/ui.ts`, all exported from `config/index.ts`, and
`protobase dev` and `protobase serve` serve the API and the app from them.

- Tested with Protobase **0.66.6**, and CI runs against it. The app is bundled: the `@protobase/*` packages are dev
  dependencies in the caret range of that release, and dev, the build and the `db:*` scripts (`protobase run`) use the
  CLI's own copies, so a newer CLI within the range updates the app with no change to its files. `tsconfig.json`
  extends the `.protobase/tsconfig.json` that `protobase types` writes, so the editor types the CLI's copies too. To move a copy of your own outside the range, set the new range on each `@protobase/*` package, run `bun install`, then `bun run typecheck`,
  `bun run test` and `bun run build`. The [release notes](https://github.com/PrototeamHQ/protobase/releases) say what changed.
  [Versioning](https://docs.protobase.net/reference/versioning/) says how bundled and locked apps differ.
- Docs: [docs.protobase.net](https://docs.protobase.net). Source and issues: [PrototeamHQ/protobase](https://github.com/PrototeamHQ/protobase).
- This app started as an example in Protobase's repository; its history came with it.
- It started as the `scratch` preset that new Protobase apps can start from ([`@protobase/presets`](https://github.com/PrototeamHQ/protobase/tree/main/packages/presets)).

## Contributing

Contributions are welcome, from a typo to a new screen: see [CONTRIBUTING.md](CONTRIBUTING.md). A problem in Protobase
itself goes to [Protobase's issues](https://github.com/PrototeamHQ/protobase/issues).

## Licence

[Apache License 2.0](LICENSE).
