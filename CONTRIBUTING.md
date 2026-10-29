# Contributing

Everyone is welcome here: bug reports, questions, fixes and new features alike. This project belongs to the
[protobase-community](https://github.com/protobase-community) organization and exists for anyone who builds with
[Protobase](https://github.com/PrototeamHQ/protobase).

## Reporting a problem

Open an issue with what you did, what you expected and what happened instead. A problem in Protobase itself, rather
than in this app, belongs in [Protobase's issues](https://github.com/PrototeamHQ/protobase/issues).

## Making a change

1. Fork the repository and create a branch.
2. Set it up as the [README](README.md#run-it-locally) says:

   ```sh
   bun install
   bun run db:up
   bun run db:migrate
   ```

3. Make your change. A change to the database is a new migration in `db/migrations/`, numbered after the last one;
   never edit one that exists. [AGENTS.md](AGENTS.md) has the rules this app follows.
4. Check it with `bun run typecheck`, `bun run test`, `bun run build` and `bun run doctor`, as CI does.
5. Open a pull request that says what changed and why.

Keep each pull request to one change. Commit messages follow [Conventional Commits](https://www.conventionalcommits.org),
such as `feat: filter the orders by status` or `fix: the seed's invoice totals`.

## Licence

By contributing you agree that your contribution is licensed under the [Apache License 2.0](LICENSE).
