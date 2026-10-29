-- A caller proves who they are with their customer number and support PIN. Only the PIN's scrypt hash is kept, with a
-- salt of its own, and no role reads it. Wrong PINs are counted on the call (three end its verification) and on the
-- customer (five within 24 hours lock the PIN until a manager unlocks it), so calling again does not start over. A
-- count is the number of wrong PINs so far, zero before the first; each time is NULL until it happens.

-- `scrypt:<salt>:<hash>`, both base64; NULL until staff set a PIN.
alter table public.customers add column support_pin_hash text;
alter table public.customers add column pin_set_at timestamptz;
alter table public.customers add column pin_failures integer not null default 0 check (pin_failures >= 0);
-- When the first wrong PIN that pin_failures counts was given: a count older than 24 hours starts over.
alter table public.customers add column pin_failures_since timestamptz;
alter table public.customers add column pin_locked_at timestamptz;

alter table public.phone_calls add column pin_failures integer not null default 0 check (pin_failures >= 0);
