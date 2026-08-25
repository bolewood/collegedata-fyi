-- Brand-color coverage-gap batch 8 of 8 (overall scouting batch 37).
-- Researched 27 public in-scope schools in coverage/enrollment order;
-- 16 have defensible colors (10 high, 1 medium, 5 low)
-- and 11 remain null after documented source and identity checks.
-- Audit records: data/brand-colors/batch-37-2026-08-25.jsonl

begin;

create temporary table brand_color_seed_batch_37 (
  school_id text primary key,
  ipeds_id text not null,
  brand_colors text[] not null,
  source text not null,
  confidence text not null,
  notes text not null
) on commit drop;

insert into brand_color_seed_batch_37 (
  school_id, ipeds_id, brand_colors, source, confidence, notes
)
values
  ('dakota-state-university', '219082', array['#004165', '#00A9E0']::text[], 'https://dsu.edu/marketing/brand/brand-manual.html', 'high', 'Current official Dakota State Brand Manual labels DarkBLUE / DSU Blue and LightBLUE / Trojan Blue as the two primary colors and explicitly prints HEX #004165 and #00A9E0. Replaced a moved legacy URL with the live brand-manual path.'),
  ('saint-ambrose-university', '154235', array['#003087']::text[], 'https://www.trucolor.net/portfolio/chicagoland-collegiate-athletic-conference-1949-1950-through-present/#st-ambrose-u', 'low', 'Repaired unreachable College Football Commission URL with reachable TruColor CCAC record explicitly matching St. Ambrose University; current institutional and athletics records print Blue #003087. White omitted as neutral.'),
  ('university-of-minnesota-crookston', '174075', array['#7A0019', '#FFCC33']::text[], 'https://umarcomm.umn.edu/resources/colors-and-type', 'high', 'Official University of Minnesota system colors page prints Maroon #7A0019 and Gold #FFCC33; these system colors apply to the Crookston campus. Neutrals omitted.'),
  ('lawrence-technological-university', '170675', array['#005EB8']::text[], 'https://www.ltu.edu/wp-content/uploads/2024/06/brand_guidelines_v6.pdf', 'high', 'Lawrence Tech official brand guidelines explicitly print LTU Blue #005EB8; white is neutral and omitted.'),
  ('lenoir-rhyne-university', '198835', array['#A31F34']::text[], 'https://www.lr.edu/marketing-and-communications/brand-toolkit', 'high', 'Official toolkit prints Red #A31F34.'),
  ('albion-college', '168546', array['#512D6D', '#EAAA00']::text[], 'https://www.trucolor.net/portfolio/michigan-intercollegiate-athletic-association-1888-1889-through-present/', 'low', 'Official Albion visual-identity page links guidelines but no citable hex/RGB. TruColor exact Albion College (Albion, MI) record gives Purple #512D6D and Gold #EAAA00; low-confidence third-party fallback.'),
  ('university-of-virginias-college-at-wise', '233897', array['#D21414', '#232D4B']::text[], 'https://brand.uvawise.edu/brand-essentials/colors', 'high', 'Official page prints Red #D21414 and Blue #232D4B.'),
  ('saint-michaels-college', '231059', array['#702F8A', '#C5B783']::text[], 'https://www.trucolor.net/portfolio/northeast-10-conference-1980-1981-through-present/', 'low', 'Official Saint Michael’s search confirms Purple/Gold but no citable hex/RGB. TruColor exact Saint Michael’s College (Colchester, VT) record gives Purple #702F8A and Gold #C5B783; low confidence.'),
  ('life-university', '140252', array['#97D700', '#FDDD00']::text[], 'https://marketing.life.edu/wp-content/uploads/2022/01/Life-Brand-Toolkit-01-2022.pdf', 'high', 'Official toolkit prints Green #97D700 and Yellow #FDDD00.'),
  ('mcpherson-college', '155511', array['#A70000', '#3B0B00']::text[], 'https://wwwi.mcpherson.edu/wp-content/uploads/2015/01/McPherson_BrandGuidelines_Identity.pdf', 'high', 'McPherson official brand guidelines explicitly print McPherson Red #A70000 and Dark Red #3B0B00; black/white omitted.'),
  ('eastern-mennonite-university', '232043', array['#0056B8']::text[], 'https://emu.edu/marketing/docs/emu-brand-identity.pdf', 'medium', 'Official guide identifies PMS 2935 C / digital blue #0056B8.'),
  ('clarke-university', '153126', array['#000033', '#FFCC00']::text[], 'https://clarke.edu/faculty-and-staff/marketing-and-communication/visual-identity-standards/', 'high', 'Clarke official visual identity standards explicitly print Official University Navy web #000033 and Gold web #FFCC00.'),
  ('suny-college-at-geneseo', '196167', array['#003087']::text[], 'https://www.brandcolorcode.com/suny-geneseo', 'low', 'Official guide confirms blue but is Pantone-only; third-party fallback reports #003087.'),
  ('husson-university', '487524', array['#16453B', '#B09247']::text[], 'https://teamcolorcodes.com/husson-university-eagles-color-codes/', 'low', 'Official Husson search did not expose citable hex/RGB. Team Color Codes exact Husson University Eagles record gives Dark Green #16453B and its listed Gray/Gold #B09247; white omitted as neutral; low confidence.'),
  ('arkansas-tech-university', '106467', array['#FFCD00', '#00533E']::text[], 'https://www.atu.edu/marcomm/resources.php', 'high', 'Official Arkansas Tech University MarComm resources page explicitly prints ATU Gold HEX #FFCD00 and ATU Green HEX #00533E; the guide’s PDF text renders the green as #115740 in one extraction, so the live HTML official value #00533E is used.'),
  ('saint-cloud-state-university', '174783', array['#CD1041']::text[], 'https://www.stcloudstate.edu/ucomm/brand/logo-usage.aspx', 'high', 'Official page prints Spirit Red #CD1041.');

update public.institution_directory as directory
set brand_colors = seed.brand_colors,
    brand_colors_source = seed.source,
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = seed.confidence,
    brand_colors_notes = seed.notes
from brand_color_seed_batch_37 as seed
where directory.school_id = seed.school_id
  and directory.ipeds_id = seed.ipeds_id
  and directory.brand_colors is null;

do $$
declare
  uncovered_count integer;
begin
  select count(*) into uncovered_count
  from brand_color_seed_batch_37 as seed
  left join public.institution_directory as directory
    on directory.school_id = seed.school_id
   and directory.ipeds_id = seed.ipeds_id
  where directory.brand_colors is null;

  if uncovered_count <> 0 then
    raise exception 'Brand-color batch 37 verification found % uncovered rows', uncovered_count;
  end if;
end$$;

commit;
