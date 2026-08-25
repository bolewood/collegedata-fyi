-- Brand-color coverage-gap batch 7 of 8 (overall scouting batch 36).
-- Researched 30 public in-scope schools in coverage/enrollment order;
-- 23 have defensible colors (14 high, 1 medium, 8 low)
-- and 7 remain null after documented source and identity checks.
-- Audit records: data/brand-colors/batch-36-2026-08-25.jsonl

begin;

create temporary table brand_color_seed_batch_36 (
  school_id text primary key,
  ipeds_id text not null,
  brand_colors text[] not null,
  source text not null,
  confidence text not null,
  notes text not null
) on commit drop;

insert into brand_color_seed_batch_36 (
  school_id, ipeds_id, brand_colors, source, confidence, notes
)
values
  ('northwest-university-center-for-online-and-extended', '487603', array['#063966', '#B0013A']::text[], 'https://www.northwestu.edu/assets/documents/marketing/brand-and-visual-style-guide.pdf', 'high', 'Official guide prints Blue #063966 and Red #B0013A; extension center uses university identity.'),
  ('franklin-w-olin-college-of-engineering', '441982', array['#009BDF']::text[], 'https://www.olin.edu/sites/default/files/2022-01/olin-brandguidelines_081913_screen.pdf', 'high', 'Official Olin brand guidelines explicitly print school Process Blue HEX #009BDF; silver/gray and black omitted as neutrals.'),
  ('san-francisco-conservatory-of-music', '122506', array['#9C2140', '#F1C44A']::text[], 'https://jaucodesign.com/wp-content/uploads/2019/07/BrandGuide-SFCM-WEBVIEW.pdf', 'low', 'Official SFCM announcement confirms the 2017 rebrand and palette; publicly mirrored SFCM brand guide prints primary Raspberry #9C2140 and Gold #F1C44A. Mirror used because exact guide values are not exposed on sfcm.edu.'),
  ('antioch-college', '483018', array['#A52238']::text[], 'https://antiochcollege.edu/wp-content/uploads/migrate/150717-Brand%20Standards-Final.pdf', 'high', 'Official Antioch College brand guidelines explicitly print Antioch Crimson RGB 165/34/56 and Hex #A52238; black/white paired neutrals omitted.'),
  ('lone-star-college-system', '227182', array['#003768', '#B30838']::text[], 'https://www.lonestar.edu/college-departments/marketing-communications/brand-and-logo-styleguide.htm', 'high', 'Official Lone Star College system style guide labels Main Blue #003768 and Main Red #B30838.'),
  ('san-jacinto-community-college', '227979', array['#004C97', '#FFC61E']::text[], 'https://www.sanjac.edu/sites/default/files/inline-files/brand-standards.pdf', 'high', 'Official San Jacinto College Brand Standards PDF explicitly prints San Jac Blue HEX #004C97 and San Jac Gold HEX #FFC61E.'),
  ('metropolitan-state-university-of-denver', '127565', array['#00447C', '#D11242']::text[], 'https://s3.amazonaws.com/sidearm.sites/rmacsports.org/documents/2018/10/12/2018_19_RMAC_Style_Guide.pdf', 'medium', 'Official MSU Denver Brand Central confirms Navy/Red/PMS 295/193; official RMAC athletics style guide prints exact Web Blue #00447C and Red #D11242.'),
  ('university-of-houston-downtown', '225432', array['#092E6E', '#C60E3B']::text[], 'https://www.uhd.edu/documents/aur/university-relations/uhd-graphic-standards.pdf', 'high', 'Official UHD Graphic Standards PDF explicitly prints UHD Blue RGB 9/46/110 Hex 092e6e and UHD Red RGB 198/14/59 Hex c60e3b; exact downtown campus palette, not main UH colors.'),
  ('north-carolina-a-and-t-state-university', '199102', array['#004684', '#FDB927']::text[], 'https://www.ncat.edu/styleguide/colors-and-icons.php', 'high', 'Official NC A&T style guide lists approved brand colors; the linked university brand guide identifies Aggie Blue HEX #004684 and Aggie Gold HEX #FDB927 as primary university colors.'),
  ('texas-a-and-m-university-corpus-christi', '224147', array['#007F3E', '#0067C5']::text[], 'https://www.tamucc.edu/marketing-and-communications/assets/documents/tamu-cc-web-style-guide.pdf', 'high', 'Official guide prints green #007F3E and blue #0067C5.'),
  ('florida-agricultural-and-mechanical-university', '133650', array['#F4811F', '#008344']::text[], 'https://www.brandcolorcode.com/florida-am-university-famu', 'low', 'Official FAMU policy provides Pantone-only Orange/Green and no hex/RGB. BrandColorCode exact Florida A&M University fallback gives Orange #F4811F and Green #008344; low confidence.'),
  ('indiana-university-of-pennsylvania-main-campus', '213020', array['#9D2235']::text[], 'https://www.iup.edu/marcom/visual-guide/index.html', 'high', 'Official IUP Visual Guide labels IUP Crimson as a core color and lists HEX #9d2235. Gray is a core neutral and was omitted.'),
  ('northeastern-illinois-university', '147776', array['#FDB813', '#003DA7']::text[], 'https://www.brandcolorcode.com/northeastern-illinois-university-neiu', 'low', 'Official NEIU page references the palette but its hex values are image-only in the citable page. BrandColorCode exact Northeastern Illinois University fallback gives Gold #FDB813 and Blue #003DA7; low confidence.'),
  ('aurora-university', '143118', array['#47AA42', '#00467F']::text[], 'https://www.brandcolorcode.com/aurora-university', 'low', 'Official Aurora University search found school colors but no readable exact institution-wide HEX palette. BrandColorCode has an exact Aurora University (Illinois) match and prints Green #47AA42 and Blue #00467F; fallback marked low.'),
  ('eastern-connecticut-state-university', '129215', array['#002D72', '#862633']::text[], 'https://www.easternct.edu/branding/index.html', 'high', 'Official page prints blue #002D72 and burgundy #862633.'),
  ('colorado-state-university-pueblo', '128106', array['#00205C', '#08AEDB']::text[], 'https://www.csupueblo.edu/marketing-communications-and-community-relations/_doc/external-csu-pueblo-brand-guide.pdf', 'high', 'CSU Pueblo official guide explicitly prints primary dark blue #00205C and cyan #08AEDB; lighter cyan/red/neutral colors omitted.'),
  ('frostburg-state-university', '162584', array['#B12025']::text[], 'https://www.brandcolorcode.com/frostburg-state-university-fsu', 'low', 'Official Frostburg search confirms institution/colors prose; BrandColorCode institution page prints Red #B12025. Black omitted.'),
  ('university-of-wisconsin-parkside', '240374', array['#00452A']::text[], 'https://teamcolorcodes.com/wisconsin-parkside-rangers-color-codes/', 'low', 'Official UW-Parkside search did not expose citable hex/RGB. Team Color Codes exact University of Wisconsin-Parkside Rangers record gives Green #00452A; black/white omitted as neutrals; low confidence.'),
  ('baldwin-wallace-university', '201195', array['#3D2D1F', '#FFCC33']::text[], 'https://www.bw.edu/assets/offices/university-relations/visual-identity-guidelines.pdf', 'high', 'Official Baldwin Wallace Visual Identity Guidelines list web brown RGB 61/45/31 (HEX #3D2D1F) and gold RGB 255/204/0 (HEX #FFCC33) as basic University colors.'),
  ('suny-college-of-technology-at-canton', '196015', array['#004B8D', '#00A160', '#CFAB7A']::text[], 'https://www.brandcolorcode.com/suny-canton', 'low', 'Official search did not expose digital values; third-party fallback reports #004B8D, #00A160, #CFAB7A.'),
  ('augustana-college', '143084', array['#002F6C', '#FFDD00']::text[], 'https://www.augustana.edu/files/2018-01/_BrandGuidelines_Short.pdf', 'high', 'Official Augustana College (Rock Island, Illinois) brand guidelines explicitly print core Blue #002F6C and Gold #FFDD00; exact IL institution, not Augustana University in South Dakota.'),
  ('california-lutheran-university', '110413', array['#3B2360', '#FFC222']::text[], 'https://web.archive.org/web/20260516055037/https://www.callutheran.edu/offices/marketing/brand/color.html', 'high', 'The official Cal Lutheran Brand Color page now returns 404. A stable Wayback capture from 2026-05-16 preserves the page’s explicit Primary Purple HEX #3B2360 and Primary Yellow HEX #FFC222; archived official evidence is documented.'),
  ('john-carroll-university', '203368', array['#003D6D', '#DDB500']::text[], 'https://www.brandcolorcode.com/john-carroll-university', 'low', 'Official search confirms names but not exact values; third-party fallback reports #003D6D and #DDB500.');

update public.institution_directory as directory
set brand_colors = seed.brand_colors,
    brand_colors_source = seed.source,
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = seed.confidence,
    brand_colors_notes = seed.notes
from brand_color_seed_batch_36 as seed
where directory.school_id = seed.school_id
  and directory.ipeds_id = seed.ipeds_id
  and directory.brand_colors is null;

do $$
declare
  uncovered_count integer;
begin
  select count(*) into uncovered_count
  from brand_color_seed_batch_36 as seed
  left join public.institution_directory as directory
    on directory.school_id = seed.school_id
   and directory.ipeds_id = seed.ipeds_id
  where directory.brand_colors is null;

  if uncovered_count <> 0 then
    raise exception 'Brand-color batch 36 verification found % uncovered rows', uncovered_count;
  end if;
end$$;

commit;
