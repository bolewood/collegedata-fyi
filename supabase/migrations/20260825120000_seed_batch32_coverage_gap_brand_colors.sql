-- Brand-color coverage-gap batch 3 of 8 (overall scouting batch 32).
-- Researched 30 public in-scope schools in coverage/enrollment order;
-- 29 have defensible colors (19 high, 2 medium, 8 low)
-- and 1 remain null after documented source and identity checks.
-- Audit records: data/brand-colors/batch-32-2026-08-25.jsonl

begin;

create temporary table brand_color_seed_batch_32 (
  school_id text primary key,
  ipeds_id text not null,
  brand_colors text[] not null,
  source text not null,
  confidence text not null,
  notes text not null
) on commit drop;

insert into brand_color_seed_batch_32 (
  school_id, ipeds_id, brand_colors, source, confidence, notes
)
values
  ('united-states-military-academy', '197036', array['#D3BC8D']::text[], 'https://www.trucolor.net/portfolio/patriot-league-official-colors-and-nicknames-1986-1987-through-present/', 'low', 'Official West Point identity search found Pantone-only guidance. TruColor exact United States Military Academy/Army West Point record gives current Gold #D3BC8D (black and gray omitted as neutrals); low-confidence third-party fallback.'),
  ('university-of-washington-tacoma-campus', '377564', array['#32006E', '#4B2E83', '#B7A57A']::text[], 'https://www.tacoma.uw.edu/brand/uw-tacoma-brand-colors', 'high', 'Official UW Tacoma Brand Colors page lists primary Husky Purple #32006e, Spirit Purple #4b2e83 and Husky Gold #b7a57a. Tacoma campus identity is explicit; omitted web-only/secondary gold variants.'),
  ('brandeis', '165015', array['#003478', '#00B3E9']::text[], 'https://www.brandeis.edu/brand/visual-identity-system/color.html', 'high', 'Brandeis official palette explicitly states Brandeis Blue #003478 and Cyan #00B3E9 as primary/secondary institutional colors.'),
  ('florida-institute-of-technology', '133881', array['#770000', '#AB946C']::text[], 'https://www.fit.edu/marketing-and-communications/marcomm-toolbox/graphic-identity-standards/color-palette-and-typography/', 'high', 'Official Florida Tech palette page lists primary Crimson HEX #770000 and Gold HEX #AB946C. Institutional Florida Tech identity confirmed.'),
  ('barnard', '189097', array['#99CAEA']::text[], 'https://usteamcolors.com/columbia-university-barnard-college-colors/', 'low', 'Official Barnard pages checked but print no digital value; U.S. Team Colors institution athletics index explicitly matches Columbia University-Barnard and prints Columbia Blue #99CAEA.'),
  ('suny-at-purchase-college', '196219', array['#462372']::text[], 'https://www.brandcolorcode.com/purchase-college', 'low', 'Official Purchase identity guide names heliotrope/puce and provides Pantone only, with separate blue/orange athletics colors. BrandColorCode exact Purchase College fallback gives closest digital Purple #462372 and explicitly flags it as an approximation; low confidence.'),
  ('calvin-university', '169080', array['#8C2131', '#F3CD00']::text[], 'https://calvin.edu/sites/default/files/migrated/offices-services-marketing-communications-files-calvin-university-brand-identity-standards.pdf', 'high', 'Official Calvin University Brand Identity Standards PDF labels Classic Maroon and Classic Gold as primary and lists HEX #8C2131 and #F3CD00.'),
  ('university-of-south-carolina-aiken', '218645', array['#002341', '#FF0039']::text[], 'https://www.usca.edu/departments/marketing/brand-guide/official-colors/', 'high', 'Official page prints Midnight #002341 and Fire Red #FF0039.'),
  ('oregon-institute-of-technology', '209506', array['#003767', '#FFD24F']::text[], 'https://www.oit.edu/sites/default/files/2023/documents/2023-24%20Oregon%20Tech%20Style%20Guide.pdf', 'high', 'The prior Oregon Tech university-brand-guidelines.pdf URL returned 404. The reachable official 2023-24 Oregon Tech Style Guide explicitly prints Blue RGB 0/55/103, hexadecimal 00 37 67 (#003767), and Gold RGB 255/210/79, hexadecimal FF D2 4F (#FFD24F).'),
  ('loyola-university-new-orleans', '159656', array['#660000', '#F4A400']::text[], 'https://www.loyno.edu/sites/default/files/2020-05/Loyola-Brand-Book.pdf', 'high', 'Official Loyola University New Orleans Brand Book explicitly prints Loyola Maroon HEX #660000 and Loyola Gold HEX #F4A400.'),
  ('citadel-military-college-of-south-carolina', '217864', array['#002856', '#7BADD3', '#EDAE17']::text[], 'https://brand.citadel.edu/wp-content/uploads/2025/10/Citadel-Style-Guide-2025.pdf', 'high', 'Official guide prints Flag Blue #002856, Infantry Blue #7BADD3, Ring Gold #EDAE17.'),
  ('kent-state-university-at-stark', '203465', array['#003976', '#EFAB00']::text[], 'https://www.kent.edu/brand/swatches', 'high', 'Kent State official brand swatches explicitly print primary blue #003976 and gold #EFAB00; applies to regional campus branding including Stark.'),
  ('fairleigh-dickinson-university-metropolitan-campus', '184603', array['#28334A', '#70273D']::text[], 'https://www.fdu.edu/about/university-leadership-offices/office-of-communication/graphic-standards-guide/color-font/', 'high', 'Official FDU Color and Font page lists identity colors Pantone 2380 HEX #28334A and Pantone 2042 HEX #70273D. Metropolitan campus is an FDU campus; same university identity applied.'),
  ('dominican-university', '148496', array['#1D3B6E']::text[], 'https://www.dom.edu/sites/default/files/pdfs/about/OMC_Branding_Quick_Guide_2017_02.28.18_HRF.pdf', 'high', 'Official Illinois Dominican guide prints primary #1D3B6E.'),
  ('auburn-university-at-montgomery', '100830', array['#F04E29']::text[], 'https://www.brandcolorcode.com/auburn-montgomery-warhawks', 'low', 'Official AUM page confirms Orange PMS 172 and black but no hex/RGB. BrandColorCode exact Auburn Montgomery Warhawks fallback gives Orange #F04E29 (black omitted as neutral); low confidence.'),
  ('university-of-hawaii-west-oahu', '141981', array['#A71930', '#000000']::text[], 'https://westoahu.hawaii.edu/brand/identity/colors/', 'high', 'Official UH West Oahu Design System says primary colors are UH West Oahu Red and black and explicitly lists HEX #A71930 and #000000. West Oahu campus identity confirmed.'),
  ('bard-college', '189088', array['#AD1A1F']::text[], 'https://www.bard.edu/wwwmedia/files/3712195/3/Bard%20Web%20Style%20Guide%202025.pdf', 'high', 'Official Bard Web Style Guide labels Red #AD1A1F as the primary color.'),
  ('eastern-university', '212133', array['#6A1F32']::text[], 'https://teamcolorcodes.com/eastern-university-eagles-color-codes/', 'low', 'Official Eastern University search found color names but no explicit hex/RGB. Team Color Codes exact Eastern University Eagles record (St. Davids, PA) gives Maroon #6A1F32; white/silver omitted as neutral; low-confidence fallback.'),
  ('lewis-clark-state-college', '142328', array['#003865']::text[], 'https://www.lcsc.edu/media/he3fhwba/lc-state-athletics-quick-branding-guide-20.pdf', 'high', 'Official LC State athletics quick branding guide explicitly labels Warrior Blue and prints HEX #003865. Other official prose colors were not converted because no exact digital values were printed.'),
  ('denison-university', '202523', array['#E51636']::text[], 'https://teamcolorcodes.com/denison-university-big-red-color-codes/', 'low', 'Official Denison search found no retrievable digital value; TeamColorCodes page explicitly matches Denison University Big Red and prints Red #E51636. Neutrals omitted.'),
  ('rose-hulman-institute-of-technology', '152318', array['#800000']::text[], 'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/athletics.rose-hulman.edu/documents/2025/8/4/R-H_Athletics_Style_Guide_4-17-15.pdf', 'medium', 'Current official Rose-Hulman Athletics style guide explicitly prints Rose-Hulman Red RGB 128/0/0 and HEX 800000; athletics source is exact but not the institution-wide communications guide, so medium confidence.'),
  ('eastern-oregon-university', '208646', array['#002856', '#B68400']::text[], 'https://web.archive.org/web/20220319182720/https://www.eou.edu/marketing-resources/files/2016/11/EOU-EasternEdge-CampaignCreativeGuide-6.29.18.pdf', 'high', 'The official EOU Eastern Edge Campaign Creative Guide URL now returns 404. A stable Wayback capture from 2022-03-19 preserves the official guide’s explicit Eastern Navy HEX #002856 and Eastern Gold HEX #B68400 (accent red #9C182F omitted); archive status is documented.'),
  ('the-evergreen-state-college', '235167', array['#266726']::text[], 'https://www.evergreen.edu/offices-services/marketing-and-communications/style-guide', 'high', 'Official Evergreen style guide labels Forest #266726 in the core palette.'),
  ('louisiana-state-university-shreveport', '159416', array['#461D7C', '#FDD023']::text[], 'https://www.lsus.edu/Documents/StyleGuide.pdf', 'high', 'Official LSUS logo/style guide explicitly prints LSUS Purple #461D7C and LSUS Gold #FDD023 in its RGB/Hex table; black/gray omitted as neutrals.'),
  ('desales-university', '210739', array['#192C4E', '#C21B32']::text[], 'https://sportcolorcodes.com/desales-university-bulldogs-color-codes/', 'low', 'Official DeSales brand-center search did not yield a readable exact HEX palette. SportColorCodes has an exact DeSales University Bulldogs match and prints Navy #192C4E and Red #C21B32; used as a documented fallback.'),
  ('lewis-and-clark-college', '209056', array['#F36F21']::text[], 'https://www.lclark.edu/details/profile-pubcom.php?id=3919', 'medium', 'Official page prints orange #F36F21; conflicting RGB description lowers confidence.'),
  ('gettysburg-college', '212674', array['#043371', '#CC4E00']::text[], 'https://www.gettysburg.edu/brand-guide/visual-style', 'high', 'The prior www3 Gettysburg visual-style URL timed out during citation checking. The reachable official Gettysburg brand-guide visual-style page explicitly prints Gettysburg Blue #043371 (RGB 4/51/113) and Gettysburg Orange #CC4E00 (RGB 204/78/0).'),
  ('miami-university-hamilton', '204006', array['#C41230', '#FFFFFF']::text[], 'https://miamioh.edu/miami-brand/_files/documents/brand-standards-2025_508.pdf', 'high', 'Current official Miami University Brand Guide primary palette explicitly lists Miami Red HEX C41230 and White HEX FFFFFF. Hamilton and Middletown are named Miami University regional campuses; same institutional palette applied.'),
  ('eckerd-college', '133492', array['#0D2240', '#38939B']::text[], 'https://eckerdtritons.com/sports/2009/7/8/sportsinfo.aspx', 'low', 'Official athletics page prints Navy #0D2240 and Teal #38939B; athletics-only.');

update public.institution_directory as directory
set brand_colors = seed.brand_colors,
    brand_colors_source = seed.source,
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = seed.confidence,
    brand_colors_notes = seed.notes
from brand_color_seed_batch_32 as seed
where directory.school_id = seed.school_id
  and directory.ipeds_id = seed.ipeds_id
  and directory.brand_colors is null;

do $$
declare
  uncovered_count integer;
begin
  select count(*) into uncovered_count
  from brand_color_seed_batch_32 as seed
  left join public.institution_directory as directory
    on directory.school_id = seed.school_id
   and directory.ipeds_id = seed.ipeds_id
  where directory.brand_colors is null;

  if uncovered_count <> 0 then
    raise exception 'Brand-color batch 32 verification found % uncovered rows', uncovered_count;
  end if;
end$$;

commit;
