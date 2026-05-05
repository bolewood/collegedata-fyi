-- PRD 019: allow public surfaces to show only explicitly published,
-- verified change events. Generated candidates remain operator-only.

create policy cds_field_change_events_public_verified_read
  on public.cds_field_change_events
  for select
  to anon, authenticated
  using (
    public_visible = true
    and verification_status in ('not_required', 'confirmed')
  );

grant select on public.cds_field_change_events to anon, authenticated;
