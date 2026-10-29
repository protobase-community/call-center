-- The change capture the resources' events and history need, written by `protobase migration`.
-- Applied with the project's other migrations; edit or remove statements the project handles differently.

create schema if not exists "changes";

create table if not exists "changes"."outbox" (
  "id" bigint generated always as identity primary key,
  "transaction" bigint not null,
  "resource" text not null,
  "op" text not null,
  "old" jsonb,
  "new" jsonb,
  "changed" text[],
  "actor" jsonb,
  "database_role" text,
  "dispatch_after" timestamptz not null default now(),
  "created_at" timestamptz not null default now()
);
alter table "changes"."outbox" add column if not exists "database_role" text;

create or replace function "changes"."capture"() returns trigger language plpgsql security definer set search_path = pg_catalog, pg_temp as $capture$
declare
  kept text[] := TG_ARGV[1]::text[];
  hidden text[] := TG_ARGV[2]::text[];
  old_row jsonb;
  new_row jsonb;
  changed text[];
begin
  if current_setting('changes.capture', true) = 'off' then
    return null;
  end if;
  if TG_OP <> 'INSERT' then
    old_row := to_jsonb(OLD);
  end if;
  if TG_OP <> 'DELETE' then
    new_row := to_jsonb(NEW);
  end if;
  if TG_OP = 'UPDATE' then
    select array_agg(c.name order by c.position) into changed
    from unnest(kept || hidden) with ordinality as c(name, position)
    where old_row -> c.name is distinct from new_row -> c.name;
    if changed is null then
      return null;
    end if;
  end if;
  insert into "changes"."outbox" ("transaction", "resource", "op", "old", "new", "changed", "actor", "database_role")
  values (
    pg_current_xact_id()::text::bigint,
    TG_ARGV[0],
    TG_OP,
    (select jsonb_object_agg(o.key, o.value) from jsonb_each(old_row) as o where o.key = any(kept)),
    (select jsonb_object_agg(n.key, n.value) from jsonb_each(new_row) as n where n.key = any(kept)),
    changed,
    nullif(current_setting('changes.actor', true), '')::jsonb,
    coalesce(nullif(current_setting('role'), 'none'), session_user)
  );
  if current_setting('changes.dispatch', true) is distinct from 'queued' then
    perform jobs.enqueue('changes.dispatch', null, null, null, 'changes');
    perform set_config('changes.dispatch', 'queued', true);
  end if;
  return null;
end
$capture$;

create schema if not exists "changes";

create table if not exists "changes"."notices" (
  "id" bigint generated always as identity primary key,
  "resource" text not null,
  "record_key" text not null,
  "tenant_id" text,
  "operation" text not null check ("operation" in ('create', 'update', 'delete', 'undelete')),
  "at" timestamptz not null default now()
);
create index if not exists "notices_at" on "changes"."notices" ("at");

drop trigger if exists "phone_calls_changes" on "public"."phone_calls";

create trigger "phone_calls_changes" after insert or delete on "public"."phone_calls" for each row execute function "changes"."capture"('phone_calls', '{"id","room_name","caller_number","status","customer_id","verified_at","ticket_id","started_at","waiting_since","answered_at","ended_at"}', '{}');

drop trigger if exists "phone_calls_changes_update" on "public"."phone_calls";

create trigger "phone_calls_changes_update" after update on "public"."phone_calls" for each row when (old.* is distinct from new.*) execute function "changes"."capture"('phone_calls', '{"id","room_name","caller_number","status","customer_id","verified_at","ticket_id","started_at","waiting_since","answered_at","ended_at"}', '{}');
