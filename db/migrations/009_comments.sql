-- The comments table of the resources with comments, written by `protobase migration`.
-- Applied with the project's other migrations; edit or remove statements the project handles differently.

create schema if not exists "comments";

create table if not exists "comments"."comments" (
  "id" bigint generated always as identity primary key,
  "resource" text not null,
  "record_key" text not null,
  "tenant_id" text,
  "author_id" text not null,
  "body" text not null,
  "mentions" jsonb not null,
  "created_at" timestamptz not null default now()
);
create index if not exists "comments_record" on "comments"."comments" ("resource", "record_key", "id");
create index if not exists "comments_tenant" on "comments"."comments" ("tenant_id", "id");
create index if not exists "comments_author" on "comments"."comments" ("author_id", "id");
create index if not exists "comments_created_at" on "comments"."comments" ("created_at");
