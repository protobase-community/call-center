-- The change capture the resources' events and history need, written by `protobase migration`.
-- Applied with the project's other migrations; edit or remove statements the project handles differently.
-- Adds pin_failures, which 013 put on phone_calls, to their capture: without it `protobase dev` refuses to start, and
-- the bridge's automated call runs on `protobase dev`.

drop trigger if exists "phone_calls_changes" on "public"."phone_calls";

create trigger "phone_calls_changes" after insert or delete on "public"."phone_calls" for each row execute function "changes"."capture"('phone_calls', '{"id","room_name","caller_number","status","customer_id","verified_at","ticket_id","started_at","waiting_since","answered_at","ended_at","pin_failures"}', '{}');

drop trigger if exists "phone_calls_changes_update" on "public"."phone_calls";

create trigger "phone_calls_changes_update" after update on "public"."phone_calls" for each row when (old.* is distinct from new.*) execute function "changes"."capture"('phone_calls', '{"id","room_name","caller_number","status","customer_id","verified_at","ticket_id","started_at","waiting_since","answered_at","ended_at","pin_failures"}', '{}');
