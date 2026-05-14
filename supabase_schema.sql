-- Schema for find-my-towed-car-boston
-- Paste into Supabase → SQL Editor → Run.

-- Plates we know about (discovered by scrape.py).
create table if not exists plates (
  state          text not null default '',
  plate          text not null,
  last_seen_date date not null,
  created_at     timestamptz default now(),
  primary key (state, plate)
);

create index if not exists plates_last_seen_idx on plates (last_seen_date desc);

-- One row per tow event (discovered by enrich.py from the detail page).
create table if not exists tows (
  state        text not null default '',
  plate        text not null,
  time         timestamptz not null,
  year         text default '',
  make         text default '',
  model        text default '',
  color        text default '',
  vehicle_desc text default '',
  tow_company  text default '',
  agency       text default '',
  reason       text default '',
  modified     timestamptz,
  created_at   timestamptz default now(),
  primary key (state, plate, time)
);

create index if not exists tows_time_idx on tows (time desc);

-- Row-level security: public can read, only service_role can write.
alter table plates enable row level security;
alter table tows   enable row level security;

drop policy if exists "public read" on plates;
drop policy if exists "public read" on tows;

create policy "public read" on plates for select using (true);
create policy "public read" on tows   for select using (true);
-- service_role bypasses RLS by default; no insert/update policy needed.
