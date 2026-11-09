-- PRD 037: private receipts, shared admission, and retryable count-only digests.
-- Intentionally no public views, policies, sequences, or anonymous RPC access.
create table public.community_notification_batches (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  payload jsonb not null,
  message_count integer not null check (message_count between 1 and 500),
  lease_token uuid, lease_until timestamptz,
  attempts integer not null default 0,
  next_retry_at timestamptz not null default now(),
  error_class text check (error_class in ('provider', 'timeout', 'configuration')),
  sent_at timestamptz
);
create table public.community_submissions (
  id uuid primary key default gen_random_uuid(),
  request_id uuid unique,
  payload_digest text,
  created_at timestamptz not null default now(),
  payload jsonb, -- bounded plain-text contract from the server; never put in logs/exports
  privacy_version text not null default '037-v1',
  review_status text not null default 'new' check (review_status in ('new','reviewed','closed','spam')),
  reviewed_at timestamptz,
  synthetic boolean not null default false, -- operator-only; not a public request field
  publication_status text not null default 'none' check (publication_status in ('none','candidate','awaiting_approval','approved','withdrawn')),
  -- Only final public text, credit/link, content version, approval time and evidence reference.
  -- No original message/contact in this separate permission record.
  publication_permission jsonb check (publication_permission is null or
    (jsonb_typeof(publication_permission) = 'object' and
     publication_permission - array['text','credit','link','quote','version','approved_at','evidence_ref'] = '{}'::jsonb)),
  withdrawn_at timestamptz,
  batch_id uuid references public.community_notification_batches(id) on delete set null,
  notified_at timestamptz,
  check (payload is null or (jsonb_typeof(payload) = 'object' and length(payload->>'message') between 1 and 4000)),
  check (publication_status <> 'withdrawn' or withdrawn_at is not null),
  check (publication_status <> 'approved' or
    (publication_permission is not null and publication_permission ?& array['text','credit','version','approved_at','evidence_ref']
     and coalesce(publication_permission->>'text','') <> ''
     and coalesce(publication_permission->>'credit','') <> ''
     and coalesce(publication_permission->>'version','') <> ''
     and coalesce(publication_permission->>'approved_at','') <> ''
     and coalesce(publication_permission->>'evidence_ref','') <> ''))
);
create table public.community_rate_limits (
  bucket text primary key check (bucket ~ '^[a-f0-9]{64}$'),
  admitted_at timestamptz[] not null default '{}',
  expires_at timestamptz not null default now() + interval '47 hours'
);
create index community_unnotified on public.community_submissions(created_at)
  where batch_id is null and notified_at is null and review_status = 'new';

alter table public.community_submissions enable row level security;
alter table public.community_rate_limits enable row level security;
alter table public.community_notification_batches enable row level security;
revoke all on public.community_submissions, public.community_rate_limits, public.community_notification_batches from public, anon, authenticated;
grant all on public.community_submissions, public.community_rate_limits, public.community_notification_batches to service_role;

create function public.community_submit(p_request_id uuid, p_digest text, p_payload jsonb, p_bucket text, p_previous_bucket text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare existing public.community_submissions; current_times timestamptz[]; previous_times timestamptz[]; recent timestamptz[]; receipt uuid; retry integer;
begin
  -- One short global admission transaction: low-volume queue, deterministic locks,
  -- no deadlocks between request identity and network limits across instances.
  perform pg_catalog.pg_advisory_xact_lock(37001);
  select * into existing from public.community_submissions where request_id = p_request_id;
  if found then
    if existing.payload_digest <> p_digest then return jsonb_build_object('status','conflict'); end if;
    return jsonb_build_object('status','duplicate','receipt',existing.id);
  end if;
  if p_digest !~ '^[a-f0-9]{64}$' or p_bucket !~ '^[a-f0-9]{64}$' or p_previous_bucket !~ '^[a-f0-9]{64}$'
    or p_request_id is null or p_payload is null then raise exception 'invalid admission'; end if;
  select admitted_at into current_times from public.community_rate_limits where bucket = p_bucket;
  select admitted_at into previous_times from public.community_rate_limits where bucket = p_previous_bucket;
  current_times := coalesce(current_times, '{}');
  select coalesce(array_agg(t), '{}') into recent from unnest(current_times || coalesce(previous_times, '{}')) t where t > now() - interval '10 minutes';
  if cardinality(current_times) >= 20 then
    retry := greatest(1, ceil(extract(epoch from (date_trunc('day',now() at time zone 'UTC') at time zone 'UTC' + interval '1 day' - now())))::integer);
    return jsonb_build_object('status','limited','retry_after',retry);
  end if;
  if cardinality(recent) >= 5 then
    select greatest(1, ceil(extract(epoch from (min(t) + interval '10 minutes' - now())))::integer) into retry from unnest(recent) t;
    return jsonb_build_object('status','limited','retry_after',retry);
  end if;
  insert into public.community_rate_limits(bucket,admitted_at) values (p_bucket, array_append(current_times,now()))
    on conflict (bucket) do update set admitted_at = excluded.admitted_at;
  insert into public.community_submissions(request_id,payload_digest,payload) values(p_request_id,p_digest,p_payload) returning id into receipt;
  return jsonb_build_object('status','created','receipt',receipt);
end $$;

create function public.community_claim_notification(p_sender text, p_inbox_url text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare batch public.community_notification_batches; ids uuid[]; n integer; token uuid := gen_random_uuid();
begin
  perform pg_catalog.pg_advisory_xact_lock(37002);
  -- Oldest unresolved batch always wins, including after lease expiry.
  select * into batch from public.community_notification_batches where sent_at is null order by created_at limit 1 for update;
  if found then
    if batch.next_retry_at > now() or batch.lease_until > now() then return null; end if;
  else
    select array_agg(id) into ids from (select id from public.community_submissions
      where review_status = 'new' and not synthetic and payload is not null and batch_id is null and notified_at is null order by created_at limit 500 for update skip locked) s;
    n := cardinality(ids);
    if coalesce(n,0) = 0 then return null; end if;
    if p_sender <> 'CollegeData.fyi <feedback@notify.collegedata.fyi>' or
      p_inbox_url !~ '^https://supabase\.com/dashboard/project/[a-z0-9]{20}/editor(/[^?#[:space:]]*)?$' then raise exception 'invalid configuration'; end if;
    insert into public.community_notification_batches(message_count,payload)
      values(n,jsonb_build_object('from',p_sender,'to',jsonb_build_array('contact@bolewood.com'),
        'subject',format('CollegeData.fyi: %s new feedback message(s)',n),
        'text',format('There are %s new messages waiting for review.%s%sOpen the private feedback inbox: %s',n,chr(10),chr(10),p_inbox_url))) returning * into batch;
    update public.community_submissions set batch_id = batch.id where id = any(ids);
  end if;
  update public.community_notification_batches set lease_token = token, lease_until = now() + interval '5 minutes', attempts = attempts + 1 where id = batch.id;
  return jsonb_build_object('id',batch.id,'token',token,'payload',batch.payload,'count',batch.message_count);
end $$;

create function public.community_finish_notification(p_id uuid, p_token uuid, p_error text default null)
returns boolean language plpgsql security definer set search_path = '' as $$
declare batch public.community_notification_batches;
begin
  select * into batch from public.community_notification_batches where id = p_id and lease_token = p_token and sent_at is null for update;
  if not found then return false; end if;
  if p_error is null then
    update public.community_notification_batches set sent_at = now(), lease_until = null, lease_token = null, error_class = null where id = p_id;
    update public.community_submissions set notified_at = now() where batch_id = p_id;
  else
    if p_error not in ('provider','timeout','configuration') then raise exception 'invalid error class'; end if;
    update public.community_notification_batches set lease_until = null, lease_token = null, error_class = p_error,
      next_retry_at = now() + make_interval(secs => least(21600, (300 * power(2,least(batch.attempts,6)))::integer)) where id = p_id;
  end if;
  return true;
end $$;

create function public.community_notification_health() returns jsonb
language sql security definer set search_path = '' as $$
  select jsonb_build_object('overdue',count(*) filter(where created_at < now()-interval '24 hours'), 'pending',count(*))
  from public.community_notification_batches where sent_at is null;
$$;

create function public.community_expire() returns void
language plpgsql security definer set search_path = '' as $$
begin
  delete from public.community_rate_limits where expires_at <= now();
  -- No pending notification or foreign key can extend raw-content retention.
  update public.community_submissions set payload=null, payload_digest=null, request_id=null
    where created_at <= now()-interval '179 days 23 hours' or (review_status='spam' and created_at <= now()-interval '29 days 23 hours');
  update public.community_submissions set publication_permission=null
    where publication_status='withdrawn' and withdrawn_at <= now()-interval '89 days 23 hours';
  delete from public.community_submissions where payload is null and publication_status <> 'approved'
    and (publication_status <> 'withdrawn' or publication_permission is null);
  delete from public.community_notification_batches where sent_at <= now()-interval '29 days 23 hours';
end $$;

revoke all on function public.community_submit(uuid,text,jsonb,text,text), public.community_claim_notification(text,text), public.community_finish_notification(uuid,uuid,text), public.community_notification_health(), public.community_expire() from public, anon, authenticated;
grant execute on function public.community_submit(uuid,text,jsonb,text,text), public.community_claim_notification(text,text), public.community_finish_notification(uuid,uuid,text), public.community_notification_health(), public.community_expire() to service_role;
-- pg_cron already exists in this project's Supabase infrastructure. Independent of mail.
-- Guard lets this feature migration also run against isolated vanilla PostgreSQL.
do $$ begin
  if exists(select 1 from pg_extension where extname='pg_cron') then
    perform cron.schedule('community-feedback-retention','41 * * * *','select public.community_expire()');
  end if;
end $$;
