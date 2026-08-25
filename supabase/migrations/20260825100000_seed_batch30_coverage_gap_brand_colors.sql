-- Brand-color coverage-gap batch 1 of 8 (overall scouting batch 30).
-- Researched 30 public in-scope schools in coverage/enrollment order;
-- 30 have defensible colors (15 high, 4 medium, 11 low)
-- and 0 remain null after documented source and identity checks.
-- Audit records: data/brand-colors/batch-30-2026-08-25.jsonl

begin;

create temporary table brand_color_seed_batch_30 (
  school_id text primary key,
  ipeds_id text not null,
  brand_colors text[] not null,
  source text not null,
  confidence text not null,
  notes text not null
) on commit drop;

insert into brand_color_seed_batch_30 (
  school_id, ipeds_id, brand_colors, source, confidence, notes
)
values
  ('cuny-john-jay-college-of-criminal-justice', '190600', array['#232C64', '#00AEEF']::text[], 'https://www.jjay.cuny.edu/sites/default/files/2023-09/JJC-Branding-Guidelines-2023.pdf', 'high', 'Current John Jay branding guidelines explicitly print dark blue #232c64 and light blue/cyan #00aeef; candidate matched these. Black/white omitted.'),
  ('central-connecticut-state-university', '128771', array['#205999']::text[], 'https://docs.ccsu.edu/central-brand-guidelines.pdf', 'high', 'Official CCSU Central Brand Guidelines PDF explicitly prints the primary Central Blue as RGB 32, 89, 153 and HEX/HTML #205999; the prior dead candidate PDF was superseded by this live official guide.'),
  ('william-paterson-university-of-new-jersey', '187444', array['#F06122']::text[], 'https://www.brandcolorcode.com/william-paterson-pioneers', 'low', 'Official William Paterson page confirms orange/black prose; BrandColorCode institution athletics index matches William Paterson Pioneers and prints Orange #F06122. Black omitted as neutral.'),
  ('salisbury-university', '163851', array['#8A0000', '#FFC420']::text[], 'https://www.salisbury.edu/brand/_files/SU_Brand_Graphics_Standards_Manual-REV.pdf', 'high', 'Current Salisbury graphics standards explicitly print primary Maroon #8A0000 and Gold #FFC420; candidate matched these. White omitted.'),
  ('saginaw-valley-state-university', '172051', array['#A6192E', '#01426A']::text[], 'https://www.brandcolorcode.com/saginaw-valley-state-university', 'low', 'Official SVSU branding URL was checked but returned a 404/JS shell without a readable exact palette. BrandColorCode has an exact Saginaw Valley State University match and prints Cardinal #A6192E and Blue #01426A; used as a documented third-party fallback.'),
  ('princeton', '186131', array['#E77500']::text[], 'https://www.brandcolorcode.com/princeton-university', 'low', 'Official Princeton search checked; BrandColorCode institution page prints Princeton Orange #E77500. Uses institutional value instead of athletics-only Princeton Tigers #FF6000.'),
  ('south-carolina-state-university', '218733', array['#872837', '#002F70']::text[], 'https://scsu.edu/strategic_communications-marketing/SCSU%20Branding-revised.pdf', 'high', 'Current SC State branding guide corrects the candidate: web Garnet #872837 and Blue #002F70, explicitly printed in the university guide.'),
  ('lafayette-college', '213385', array['#822433']::text[], 'https://communications.lafayette.edu/style-guides/', 'high', 'Official Lafayette Communications style-guide page identifies maroon and white and exposes the web palette with HEX #822433 for the official maroon; the older Pantone-only guide was not used for conversion.'),
  ('keene-state-college', '183062', array['#E51937', '#52A2DB']::text[], 'https://sites.keene.edu/marketing/files/2012/04/KSC_Field_Guide_First_Edition.pdf', 'medium', 'Official field guide prints Red #E51937 and Blue #52A2DB; older guide.'),
  ('western-new-england-university', '168254', array['#004B8D']::text[], 'https://alumni.wne.edu/s/1919/20/interior-menu.aspx?gid=2&pgid=414&sid=1919', 'medium', 'Official WNE subdomain page explicitly prints Primary Blue #004B8D. The older university PDF provides only Pantone values for the other logo colors, so only the citable blue is retained.'),
  ('stonehill-college', '167996', array['#4F2684']::text[], 'https://www.brandcolorcode.com/stonehill-college', 'low', 'Official Stonehill brand-standards page was checked but supplies Pantone 268C/metallic gold without exact HEX/RGB. BrandColorCode has an exact Stonehill College match and prints purple #4F2684; used as a documented fallback.'),
  ('north-central-college', '147660', array['#B60016']::text[], 'https://teamcolorcodes.com/north-central-college-cardinals-color-codes/', 'low', 'Official North Central College Naperville source confirms cardinal red/white prose; TeamColorCodes institution athletics page matches Naperville and prints Red #B60016. White omitted.'),
  ('flagler-college', '133711', array['#A4343A', '#FFB81C']::text[], 'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/flaglerathletics.com/documents/2019/8/7/Rampant_Lion_logo_usage.pdf', 'medium', 'The prior ColorCodesHub fallback was unreliable/unreachable and supplied conflicting approximations. A reachable official Flagler Athletics logo-usage PDF explicitly prints Crimson RGB 164/52/58 (#A4343A) and Gold RGB 255/184/28 (#FFB81C); confidence is medium because this is an athletics-owned palette rather than the institution-wide brand portal.'),
  ('ashland-university', '201104', array['#5C068C', '#FFC72C']::text[], 'https://goashlandeagles.com/documents/2021/9/10/Visitor_s_Guide_21_22.pdf', 'medium', 'Official Ashland Eagles athletics visitor guide explicitly names school colors Purple and Gold and prints Purple HEX #5C068C and Gold HEX #FFC72C. Athletics source is used because no institution-wide readable digital palette was found.'),
  ('bowdoin', '161004', array['#000000', '#FFFFFF']::text[], 'https://www.bowdoin.edu/communications/guidelines/website/style-guide/color-and-typography.html', 'high', 'Official style guide identifies black and white as college colors.'),
  ('lake-forest-college', '146481', array['#C8102E', '#89764B']::text[], 'https://www.trucolor.net/portfolio/midwest-conference-1921-1922-through-present/', 'low', 'Official Lake Forest search found prose red/black but no citable hex/RGB. TruColor exact Lake Forest College, Illinois record gives current institutional Red #C8102E and Gold #89764B (black omitted as neutral); low-confidence third-party fallback.'),
  ('canisius-university', '189705', array['#0C2340', '#FFBA00']::text[], 'https://teamcolorcodes.com/canisius-golden-griffins-color-codes/', 'low', 'Official Canisius identity/athletics materials were checked but no readable exact HEX palette was available. TeamColorCodes has an exact Canisius Golden Griffins match and prints Navy #0C2340 and Gold #FFBA00; used as fallback.'),
  ('massachusetts-maritime-academy', '166692', array['#CFAB79', '#0355A2']::text[], 'https://teamcolorcodes.com/massachusetts-maritime-academy-buccaneers-color-codes/', 'low', 'Official Maritime branding search confirms Buzzards Bay institution and blue/gold identity; TeamColorCodes exact Buccaneers values are Moccasin #CFAB79 and Blue #0355A2. Black/white omitted.'),
  ('immaculata-university', '213011', array['#1B365D', '#69B3E7']::text[], 'https://www.immaculata.edu/contact-us/university-communications/brand-guide/visual-style/color/', 'high', 'Current official Immaculata University brand guide explicitly lists Primary Naval Blue #1B365D and Immaculata Blue #69B3E7; this supersedes the stale candidate athletics palette.'),
  ('kentucky-state-university', '157058', array['#0A8137', '#EDCB04']::text[], 'https://www.brandcolorcode.com/kentucky-state-university-ksu', 'low', 'Official Kentucky State materials were checked; they identify green and gold but did not provide exact digital values. BrandColorCode has an exact Kentucky State University match and prints Green #0A8137 and Gold #EDCB04; third-party conversion is explicitly treated as low confidence.'),
  ('adams-state-university', '126182', array['#007A53']::text[], 'https://www.brandcolorcode.com/adams-state-university', 'low', 'Official Adams State page names Pantone 341 green; BrandColorCode institution page prints Green #007A53. Black omitted.'),
  ('dominican-university-of-california', '113698', array['#008EB3', '#FFCD00']::text[], 'https://www.dominican.edu/visual-design-guide', 'high', 'Current Dominican official visual design guide explicitly prints main palette Blue #008EB3 and Yellow #FFCD00; orange/gray are supporting colors and omitted.'),
  ('texas-am', '228723', array['#500000', '#FFFFFF']::text[], 'https://marcomm.tamu.edu/creative-platform/visual-style/web-branding/', 'high', 'Live official Texas A&M Marketing & Communications Web Branding page explicitly labels Primary Brand HEX #500000 and Secondary Brand white HEX #FFFFFF; replaces the dead Singing Cadets PDF URL.'),
  ('arizona-state-university-digital-immersion', '483124', array['#8C1D40', '#FFC627']::text[], 'https://www.brandcolorcode.com/arizona-state-university', 'low', 'Arizona State Digital Immersion is an ASU program; official ASU identity search checked and BrandColorCode ASU institution page prints Maroon #8C1D40 and Gold #FFC627.'),
  ('uw', '236948', array['#32006E', '#B7A57A']::text[], 'https://www.washington.edu/brand/brand-elements/colors/', 'high', 'UW Brand lists Husky Purple (#32006e) and Husky Gold (#b7a57a) as primary digital colors; excluded neutral black/white and accent colors.'),
  ('university-of-minnesota-twin-cities', '174066', array['#7A0019', '#FFCC33']::text[], 'https://umarcomm.umn.edu/resources/colors-and-type', 'high', 'Official University Marketing Communications page identifies UMN Maroon HEX #7a0019 and UMN Gold HEX #ffcc33 as the primary colors. Twin Cities institution identity confirmed.'),
  ('virginia-polytechnic-institute-and-state-university', '233921', array['#861F41', '#E87722']::text[], 'https://vetmed.vt.edu/content/dam/vetmed_vt_edu/news/college-brand-guide/VMCVM_BrandGuidelines.pdf', 'high', 'Official guideline prints Chicago Maroon #861F41 and Burnt Orange #E87722.'),
  ('the-university-of-tennessee-knoxville', '221759', array['#FF8200']::text[], 'https://brand.utk.edu/standards/colors/', 'high', 'UT Knoxville identifies Tennessee Orange as the primary color and explicitly gives HEX FF8200; white and Smokey are supporting neutrals and were omitted.'),
  ('university-of-south-carolina-columbia', '218663', array['#73000A', '#000000', '#FFFFFF']::text[], 'https://www.sc.edu/about/offices_and_divisions/communications/toolbox/colors/index.php', 'high', 'Official USC Colors page says garnet, black and white are official primary colors and explicitly lists HEX #73000a, #000000 and #ffffff. Columbia campus identity confirmed.'),
  ('california-state-polytechnic-university-pomona', '110529', array['#005030', '#FFB81C']::text[], 'https://www.cpp.edu/brand/toolkits/design.shtml', 'high', 'Official toolkit labels CPP Green #005030 and CPP Gold #FFB81C primary.');

update public.institution_directory as directory
set brand_colors = seed.brand_colors,
    brand_colors_source = seed.source,
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = seed.confidence,
    brand_colors_notes = seed.notes
from brand_color_seed_batch_30 as seed
where directory.school_id = seed.school_id
  and directory.ipeds_id = seed.ipeds_id
  and directory.brand_colors is null;

do $$
declare
  uncovered_count integer;
begin
  select count(*) into uncovered_count
  from brand_color_seed_batch_30 as seed
  left join public.institution_directory as directory
    on directory.school_id = seed.school_id
   and directory.ipeds_id = seed.ipeds_id
  where directory.brand_colors is null;

  if uncovered_count <> 0 then
    raise exception 'Brand-color batch 30 verification found % uncovered rows', uncovered_count;
  end if;
end$$;

commit;
