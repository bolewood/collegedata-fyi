-- Rename prep: the feedback notification claim accepts either the current or
-- the renamed sender. The allow-list lives in one helper that returns the
-- display name, so the subject prefix always matches the sender used.
-- Nothing calls community_claim_notification yet; no data changes.
create function public.community_notification_sender_name(p_sender text)
returns text language sql immutable set search_path = '' as $$
  select case p_sender
    when 'CollegeData.fyi <feedback@notify.collegedata.fyi>' then 'CollegeData.fyi'
    when 'Quadfile <feedback@notify.quadfile.org>' then 'Quadfile'
  end;
$$;

create or replace function public.community_claim_notification(p_sender text, p_inbox_url text)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare batch public.community_notification_batches; ids uuid[]; n integer; token uuid := gen_random_uuid(); sender_name text;
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
    sender_name := public.community_notification_sender_name(p_sender);
    if sender_name is null or
      p_inbox_url !~ '^https://supabase\.com/dashboard/project/[a-z0-9]{20}/editor(/[^?#[:space:]]*)?$' then raise exception 'invalid configuration'; end if;
    insert into public.community_notification_batches(message_count,payload)
      values(n,jsonb_build_object('from',p_sender,'to',jsonb_build_array('contact@bolewood.com'),
        'subject',format('%s: %s new feedback message(s)',sender_name,n),
        'text',format('There are %s new messages waiting for review.%s%sOpen the private feedback inbox: %s',n,chr(10),chr(10),p_inbox_url))) returning * into batch;
    update public.community_submissions set batch_id = batch.id where id = any(ids);
  end if;
  update public.community_notification_batches set lease_token = token, lease_until = now() + interval '5 minutes', attempts = attempts + 1 where id = batch.id;
  return jsonb_build_object('id',batch.id,'token',token,'payload',batch.payload,'count',batch.message_count);
end $$;

revoke all on function public.community_notification_sender_name(text), public.community_claim_notification(text,text) from public, anon, authenticated;
grant execute on function public.community_notification_sender_name(text), public.community_claim_notification(text,text) to service_role;

do $$ begin
  if not coalesce(public.community_notification_sender_name('CollegeData.fyi <feedback@notify.collegedata.fyi>') = 'CollegeData.fyi', false) then raise exception 'community_notification_sender_name self-test failed: old sender'; end if;
  if not coalesce(public.community_notification_sender_name('Quadfile <feedback@notify.quadfile.org>') = 'Quadfile', false) then raise exception 'community_notification_sender_name self-test failed: new sender'; end if;
  if not coalesce(public.community_notification_sender_name('Quadfile <feedback@notify.quadfile.org.evil.com>') is null, false) then raise exception 'community_notification_sender_name self-test failed: suffix look-alike'; end if;
  if not coalesce(public.community_notification_sender_name('quadfile <feedback@notify.quadfile.org>') is null, false) then raise exception 'community_notification_sender_name self-test failed: lowercase name'; end if;
  if not coalesce(public.community_notification_sender_name('Quadfile <Feedback@notify.quadfile.org>') is null, false) then raise exception 'community_notification_sender_name self-test failed: uppercase local part'; end if;
  if not coalesce(public.community_notification_sender_name('') is null, false) then raise exception 'community_notification_sender_name self-test failed: empty'; end if;
  if not coalesce(public.community_notification_sender_name(null) is null, false) then raise exception 'community_notification_sender_name self-test failed: null'; end if;
end $$;
