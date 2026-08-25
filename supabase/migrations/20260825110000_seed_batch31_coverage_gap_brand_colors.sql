-- Brand-color coverage-gap batch 2 of 8 (overall scouting batch 31).
-- Researched 30 public in-scope schools in coverage/enrollment order;
-- 28 have defensible colors (23 high, 3 medium, 2 low)
-- and 2 remain null after documented source and identity checks.
-- Audit records: data/brand-colors/batch-31-2026-08-25.jsonl

begin;

create temporary table brand_color_seed_batch_31 (
  school_id text primary key,
  ipeds_id text not null,
  brand_colors text[] not null,
  source text not null,
  confidence text not null,
  notes text not null
) on commit drop;

insert into brand_color_seed_batch_31 (
  school_id, ipeds_id, brand_colors, source, confidence, notes
)
values
  ('university-of-missouri-columbia', '178396', array['#FDB719']::text[], 'https://brand.missouri.edu/brand-visuals/colors/', 'high', 'Mizzou primary colors explicitly state Mizzou Gold #FDB719 and Tiger Paw Black; retained the chromatic primary and omitted black.'),
  ('university-of-massachusetts-amherst', '166629', array['#840028', '#212721']::text[], 'https://www.umass.edu/brand/visual-identity/brand-colors', 'high', 'Current official UMass Amherst Brand Colors page identifies maroon and black as the main palette and lists HEX #840028 and #212721. Amherst identity confirmed.'),
  ('university-of-oklahoma-norman-campus', '207500', array['#841617', '#FDF9D8']::text[], 'https://www.ou.edu/content/dam/cas/docs/OUCAS%20Brand%20Guidelines.pdf', 'high', 'Official guide prints Crimson #841617 and Cream #FDF9D8.'),
  ('the-university-of-texas-at-dallas', '228787', array['#E87500', '#154734']::text[], 'https://wds.utdallas.edu/brand/', 'high', 'UT Dallas web design system explicitly labels UTD Orange #e87500 and UTD Green #154734 as primary colors; secondary/accessibility variants omitted.'),
  ('st-petersburg-college', '137078', array['#0D2142']::text[], 'https://go.spcollege.edu/uploadedFiles/SPC%20Vis%20ID%20Guide%20rev.pdf', 'high', 'Official St. Petersburg College Branding and Visual Identity Guide lists Deep Blue as a secondary print/web color with RGB 13-33-66 and HEX #0d2142; the guide names SPC and its campuses. Used the explicit institutional blue only, not unlabelled Pantone-only Reflex blue.'),
  ('georgia-tech', '139755', array['#003057', '#B3A369']::text[], 'https://brand.gatech.edu/sites/default/files/assets/pdfs/2021-11/mini-brand-book.pdf', 'high', 'Official mini brand book prints Navy #003057 and Tech Gold #B3A369.'),
  ('university-of-california-santa-cruz', '110714', array['#003C6C', '#FDC700']::text[], 'https://communications.ucsc.edu/brand-overview/color/', 'high', 'UC Santa Cruz primary blue #003c6c and primary yellow #fdc700 are explicitly printed; secondary palette omitted.'),
  ('miami-university-oxford', '204024', array['#C41230', '#FFFFFF']::text[], 'https://miamioh.edu/miami-brand/_files/documents/brand-standards-2025_508.pdf', 'high', 'Current official Miami University Brand Guide primary palette explicitly lists Miami Red HEX C41230 and White HEX FFFFFF. Hamilton and Middletown are named Miami University regional campuses; same institutional palette applied.'),
  ('cuny-bernard-m-baruch-college', '190512', array['#05336B']::text[], 'https://toolkit.baruch.cuny.edu/wp-content/uploads/sites/11/2022/08/Final-BrandIdentityGuidelines.pdf', 'high', 'Official guide identifies Baruch Blue #05336B as primary.'),
  ('california-state-university-san-bernardino', '110510', array['#0065BD']::text[], 'https://www.csusb.edu/sites/default/files/upload/file/CSUSBAthletics-StyleManual.pdf', 'medium', 'Official CSUSB athletics style manual explicitly prints Coyote Blue #0065BD. Athletics-domain source; no separate institutional hex palette found in this pass.'),
  ('cuny-city-college', '190567', array['#7D55C7', '#545859']::text[], 'https://www.ccny.cuny.edu/sites/default/files/2022-04/CCNY_Guidestyle_2022_update_040422.pdf', 'medium', 'Official guide prints primary PMS colors with HTML values including #7D55C7 and #545859.'),
  ('georgia-gwinnett-college', '447689', array['#00704A']::text[], 'https://www.ggc.edu/about/departments/communications/graphic-standards-guide/colors', 'high', 'GGC official colors page labels GGC Green #00704a; gray/silver and black are neutral/supporting, so only the chromatic primary is retained.'),
  ('college-of-charleston', '217819', array['#660000']::text[], 'https://www.brandcolorcode.com/college-of-charleston', 'low', 'Official College of Charleston branding search found prose maroon/white but no readable exact HEX. BrandColorCode has an exact College of Charleston match and prints Maroon #660000; used as fallback rather than conflicting athletics color lists.'),
  ('farmingdale-state-college', '196042', array['#006456']::text[], 'https://www.brandcolorcode.com/suny-farmingdale', 'low', 'Official Farmingdale materials confirm institutional green/white identity; BrandColorCode SUNY Farmingdale page prints Green #006456. White omitted.'),
  ('california-state-university-bakersfield', '110486', array['#003594', '#FFC72C']::text[], 'https://www.csub.edu/brand/university-visual-identity/colors.shtml', 'high', 'The prior CSUB sign-specification PDF URL returned 404. The current official CSUB University Visual Identity Colors page explicitly prints Blue HEX 003594 (RGB 0/53/148) and Gold HEX FFC72C (RGB 255/199/44).'),
  ('washington-university-in-st-louis', '179867', array['#A51417']::text[], 'https://web.archive.org/web/20240519123803/https://cpb-us-w2.wpmucdn.com/sites.wustl.edu/dist/4/9/files/2016/01/Communications_Resource_2016-y4ei5q.pdf', 'medium', 'The original official WashU communications PDF URL now returns 404. A stable Wayback capture from 2024-05-19 preserves the institutional guide’s explicit red HEX #A51417 (and green #007360); red retained while neutral support colors are omitted. This is historical pre-August-2024 refresh evidence, so confidence remains medium.'),
  ('fashion-institute-of-technology', '191126', array['#0036F9', '#12C477', '#FF2EAA']::text[], 'https://www.fitnyc.edu/about/administration/cer/toolkit/guides/color-and-layout.php', 'high', 'Official palette prints #0036F9, #12C477, and #FF2EAA.'),
  ('chapman-university', '111948', array['#A50034']::text[], 'https://brand.chapman.edu/symbols-and-marks/', 'high', 'Chapman primary palette explicitly states Chapman Red #A50034; Panther Black and white are neutral and omitted.'),
  ('berklee-college-of-music', '164748', array['#D81118', '#005587']::text[], 'https://www.berklee.edu/digital-strategy-and-development/web-standards-style-guide', 'high', 'Official Berklee web standards page labels Berklee Red #D81118 and Boston Conservatory Blue #005587 in its brand-color table. These are the institutional brand colors stated on Berklee.edu.'),
  ('west-texas-a-and-m-university', '229814', array['#450012']::text[], 'https://www.wtamu.edu/news/identity-system/graphic-standards.html', 'high', 'Official standards print primary digital maroon #450012.'),
  ('texas-aandm-university-san-antonio', '459949', array['#702E3E']::text[], 'https://resources.tamusa.edu/employees/brand-guide/documents/Visual-Brand-2023.pdf', 'high', 'A&M-San Antonio brand guide explicitly states primary Madla Maroon #702E3E; black/gray/white and secondary colors omitted.'),
  ('university-of-michigan-dearborn', '171137', array['#FFCB05', '#00274C']::text[], 'https://umdearborn.edu/external-relations/marketing/brand-identity-guidelines-material/colors', 'high', 'Official UM-Dearborn Colors page lists Michigan Maize HEX #FFCB05 and Michigan Blue HEX #00274C as signature primary colors. Dearborn campus identity confirmed.'),
  ('university-of-washington-bothell-campus', '377555', array['#32006E', '#B7A57A']::text[], 'https://www.washington.edu/brand/brand-elements/colors/', 'high', 'Official UW palette applies to Bothell and prints Purple #32006E and Gold #B7A57A.'),
  ('worcester-polytechnic-institute', '168421', array['#AC2B37']::text[], 'https://www.wpi.edu/sites/default/files/docs/Offices/Marketing-Communications/WPI_Institutional_9-4-12.pdf', 'high', 'WPI official institutional guide explicitly states Crimson HTML AC2B37; gray/black are supporting/accent and omitted.'),
  ('university-of-north-carolina-at-pembroke', '199281', array['#947843']::text[], 'https://www.uncp.edu/_files/uncp-style-guide-2026.pdf', 'high', 'Official guide prints primary Gold #947843.'),
  ('sonoma-state-university', '123572', array['#004C97']::text[], 'https://marcomm.sonoma.edu/resources-and-faqs/brand-guide/colors-typography', 'high', 'Sonoma State brand page explicitly states University Blue #004C97; light blue is a tint/supporting color and omitted.'),
  ('university-of-missouri-st-louis', '178420', array['#BA0C2F', '#EAAB00']::text[], 'https://www.umsl.edu/branding/design-elements/colors.html', 'high', 'Official UMSL branding page labels Triton Red and Triton Gold as primary colors and lists HEX #ba0c2f and #eaab00.'),
  ('suny-oneonta', '196185', array['#CC0025']::text[], 'https://suny.oneonta.edu/university-style-guide/graphics', 'high', 'Official guide prints red #CC0025.');

update public.institution_directory as directory
set brand_colors = seed.brand_colors,
    brand_colors_source = seed.source,
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = seed.confidence,
    brand_colors_notes = seed.notes
from brand_color_seed_batch_31 as seed
where directory.school_id = seed.school_id
  and directory.ipeds_id = seed.ipeds_id
  and directory.brand_colors is null;

do $$
declare
  uncovered_count integer;
begin
  select count(*) into uncovered_count
  from brand_color_seed_batch_31 as seed
  left join public.institution_directory as directory
    on directory.school_id = seed.school_id
   and directory.ipeds_id = seed.ipeds_id
  where directory.brand_colors is null;

  if uncovered_count <> 0 then
    raise exception 'Brand-color batch 31 verification found % uncovered rows', uncovered_count;
  end if;
end$$;

commit;
