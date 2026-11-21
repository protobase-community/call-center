-- The calls on records, who is in them, whom they ring, their guests, and the signals between the processes serving the app, written by `protobase migration`.
-- Applied with the project's other migrations; edit or remove statements the project handles differently.

alter table "calls"."members" add column if not exists "name" text;

create table if not exists "calls"."guest_links" (
  "id" uuid primary key,
  "call_id" uuid not null references "calls"."calls" ("id") on delete cascade,
  "token_hash" bytea not null unique,
  "created_by" text not null,
  "organization_id" text,
  "publish" jsonb not null,
  "created_at" timestamptz not null,
  "expires_at" timestamptz,
  "revoked_at" timestamptz
);
create index if not exists "guest_links_call" on "calls"."guest_links" ("call_id");
create index if not exists "guest_links_organization" on "calls"."guest_links" ("organization_id") where "revoked_at" is null;

create table if not exists "calls"."guests" (
  "id" uuid primary key,
  "link_id" uuid not null references "calls"."guest_links" ("id") on delete cascade,
  "call_id" uuid not null references "calls"."calls" ("id") on delete cascade,
  "name" text not null,
  "token_hash" bytea not null unique,
  "entered_at" timestamptz not null,
  "seen_at" timestamptz not null,
  "admitted" boolean,
  "decided_by" text,
  "decided_at" timestamptz
);
create index if not exists "guests_waiting" on "calls"."guests" ("call_id") where "admitted" is null;
create index if not exists "guests_link" on "calls"."guests" ("link_id");

create table if not exists "calls"."organization_guests" (
  "organization_id" text primary key,
  "allowed" boolean not null,
  "set_by" text not null,
  "set_at" timestamptz not null
);;
