-- The calls on records, who is in them, whom they ring, and the signals between the processes serving the app, written by `protobase migration`.
-- Applied with the project's other migrations; edit or remove statements the project handles differently.

create schema if not exists "calls";

create table if not exists "calls"."calls" (
  "id" uuid primary key,
  "resource" text not null,
  "record_key" text not null,
  "started_by" text not null,
  "started_at" timestamptz not null,
  "ends_at" timestamptz not null,
  "ended_at" timestamptz
);
create unique index if not exists "calls_live" on "calls"."calls" ("resource", "record_key") where "ended_at" is null;
create index if not exists "calls_record" on "calls"."calls" ("resource", "record_key", "started_at");

create table if not exists "calls"."members" (
  "id" bigint generated always as identity primary key,
  "call_id" uuid not null references "calls"."calls" ("id") on delete cascade,
  "member" text not null,
  "process" uuid not null,
  "tracks" jsonb not null,
  "joined_at" timestamptz not null,
  "seen_at" timestamptz not null,
  "left_at" timestamptz,
  "removed_at" timestamptz
);
create unique index if not exists "members_present" on "calls"."members" ("call_id", "member") where "left_at" is null;
create index if not exists "members_call" on "calls"."members" ("call_id", "member");
create index if not exists "members_seen" on "calls"."members" ("seen_at") where "left_at" is null;

create table if not exists "calls"."signals" (
  "id" bigint generated always as identity primary key,
  "process" uuid not null,
  "call_id" uuid not null,
  "to_member" text not null,
  "from_member" text not null,
  "body" json not null,
  "at" timestamptz not null
);
create index if not exists "signals_process" on "calls"."signals" ("process", "id");
create index if not exists "signals_at" on "calls"."signals" ("at");

create table if not exists "calls"."rings" (
  "call_id" uuid not null references "calls"."calls" ("id") on delete cascade,
  "user_id" text not null,
  "title" text not null,
  "body" text,
  "rung_at" timestamptz not null,
  "until" timestamptz not null,
  "stopped_at" timestamptz,
  primary key ("call_id", "user_id")
);
create index if not exists "rings_user" on "calls"."rings" ("user_id", "until") where "stopped_at" is null;
create index if not exists "rings_until" on "calls"."rings" ("until") where "stopped_at" is null;;
