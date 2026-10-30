-- The signed messages the phone line sent, by their webhook-id, so each is acted on once: a captured request is refused
-- when sent again, even while its timestamp is still fresh. Kept only as long as a timestamp is: the phone line function
-- deletes older ones as it adds new ones.

create table public.phone_line_messages (
  id text primary key check (length(id) between 1 and 200),
  received_at timestamptz not null default now()
);

create index phone_line_messages_received_at on public.phone_line_messages (received_at);
