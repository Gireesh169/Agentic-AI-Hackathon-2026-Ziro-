-- Run this in Supabase SQL Editor.
-- This starter uses the secret key only from the FastAPI server.
-- Do not expose SUPABASE_SECRET_KEY to the frontend.

create table if not exists public.learning_plans (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists public.approvals (
  plan_id text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

create table if not exists public.scheduled_sessions (
  session_key text primary key,
  plan_id text not null,
  data jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists scheduled_sessions_plan_id_idx
  on public.scheduled_sessions(plan_id);

create table if not exists public.test_runs (
  id text primary key,
  data jsonb not null,
  created_at timestamptz not null default now()
);

-- The API uses a server-side secret key. Enable RLS as defense in depth.
alter table public.learning_plans enable row level security;
alter table public.approvals enable row level security;
alter table public.scheduled_sessions enable row level security;
alter table public.test_runs enable row level security;

-- No browser-facing policies are added. Access these tables through the backend only.

-- Phase 3 authenticated roadmap tables. These additions preserve the legacy
-- tables above and are safe to run against an existing project.
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.roadmaps (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text not null,
  career_goal text not null,
  skill_level text not null check (skill_level in ('Beginner', 'Intermediate', 'Advanced')),
  weekly_hours integer not null check (weekly_hours between 1 and 40),
  duration_weeks integer not null check (duration_weeks > 0),
  total_estimated_hours numeric not null check (total_estimated_hours > 0),
  generation_mode text not null check (generation_mode in ('ai', 'fallback')),
  status text not null default 'active' check (status in ('active', 'completed', 'archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.roadmap_weeks (
  id uuid primary key default gen_random_uuid(),
  roadmap_id uuid not null references public.roadmaps(id) on delete cascade,
  week_number integer not null check (week_number > 0),
  title text not null,
  learning_objectives jsonb not null default '[]'::jsonb,
  activities jsonb not null default '[]'::jsonb,
  estimated_hours numeric not null check (estimated_hours > 0),
  completion_status text not null default 'not_started'
    check (completion_status in ('not_started', 'in_progress', 'completed')),
  unique (roadmap_id, week_number)
);

create table if not exists public.roadmap_resources (
  id uuid primary key default gen_random_uuid(),
  roadmap_week_id uuid not null references public.roadmap_weeks(id) on delete cascade,
  title text not null,
  url text not null check (url ~ '^https?://'),
  resource_type text not null,
  access_status text not null default 'unknown',
  verification_status text not null default 'not_checked',
  verification_evidence text,
  is_completed boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists roadmaps_user_updated_idx
  on public.roadmaps(user_id, updated_at desc);
create index if not exists roadmap_weeks_roadmap_idx
  on public.roadmap_weeks(roadmap_id, week_number);
create index if not exists roadmap_resources_week_idx
  on public.roadmap_resources(roadmap_week_id);

alter table public.profiles enable row level security;
alter table public.roadmaps enable row level security;
alter table public.roadmap_weeks enable row level security;
alter table public.roadmap_resources enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'profiles' and policyname = 'profiles_owner') then
    create policy profiles_owner on public.profiles for all using (auth.uid() = id) with check (auth.uid() = id);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'roadmaps' and policyname = 'roadmaps_owner') then
    create policy roadmaps_owner on public.roadmaps for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'roadmap_weeks' and policyname = 'roadmap_weeks_owner') then
    create policy roadmap_weeks_owner on public.roadmap_weeks for all
      using (exists (select 1 from public.roadmaps r where r.id = roadmap_id and r.user_id = auth.uid()))
      with check (exists (select 1 from public.roadmaps r where r.id = roadmap_id and r.user_id = auth.uid()));
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = 'roadmap_resources' and policyname = 'roadmap_resources_owner') then
    create policy roadmap_resources_owner on public.roadmap_resources for all
      using (exists (
        select 1 from public.roadmap_weeks w
        join public.roadmaps r on r.id = w.roadmap_id
        where w.id = roadmap_week_id and r.user_id = auth.uid()
      ))
      with check (exists (
        select 1 from public.roadmap_weeks w
        join public.roadmaps r on r.id = w.roadmap_id
        where w.id = roadmap_week_id and r.user_id = auth.uid()
      ));
  end if;
end $$;
