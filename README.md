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

<gap>Calls cannot reach the app yet because the phone line and the voice assistant are not implemented.</gap>
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
bun run calls:up                  # LiveKit in Docker on port 7880, for the calls
bun run dev                       # http://localhost:5173
bun run test
```

Set your own `PROTOBASE_SECRET` in `.env` (`openssl rand -base64 32`). `bun run db:down` stops the database and
LiveKit.

The phone line signs in with an ordinary account of the `phone_line` role and a password, and joins calls with its
session cookie. Create it with the password on standard input:

```sh
bun run protobase users create phone-line@example.com --role phone_line --password-stdin
```

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

- Tested with Protobase **0.62.2**, and CI runs against it. The app is bundled: the `@protobase/*` packages are dev
  dependencies in the caret range of that release, and dev, the build and the `db:*` scripts (`protobase run`) use the
  CLI's own copies, so a newer CLI within the range updates the app with no change to its files. `tsconfig.json`
  extends the `.protobase/tsconfig.json` that `protobase types` writes, so the editor types the CLI's copies too. A
  GitHub Action in this template (not in copies of it) moves the range to each new release and merges the move once
  CI passes. To move a copy of your own outside the range, set the new range on each `@protobase/*` package, run `bun install`, then `bun run typecheck`,
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
