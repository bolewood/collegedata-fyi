-- Brand-color coverage-gap batch 5 of 8 (overall scouting batch 34).
-- Researched 30 public in-scope schools in coverage/enrollment order;
-- 27 have defensible colors (21 high, 0 medium, 6 low)
-- and 3 remain null after documented source and identity checks.
-- Audit records: data/brand-colors/batch-34-2026-08-25.jsonl

begin;

create temporary table brand_color_seed_batch_34 (
  school_id text primary key,
  ipeds_id text not null,
  brand_colors text[] not null,
  source text not null,
  confidence text not null,
  notes text not null
) on commit drop;

insert into brand_color_seed_batch_34 (
  school_id, ipeds_id, brand_colors, source, confidence, notes
)
values
  ('montana-state-university-northern', '180522', array['#722325', '#E1A800']::text[], 'https://www.brandcolorcode.com/montana-state-university-northern', 'low', 'The official MSU-Northern branding guide previously printed school-color Web Maroon #722325 and Print/Web Gold #E1A800, but its Adobe-hosted PDF now returns 404. BrandColorCode has an exact Montana State University-Northern match, cites that guide, and reproduces the same two values; retained as a low-confidence fallback because the live primary source moved.'),
  ('hollins-university', '232308', array['#006F53', '#9A722C']::text[], 'https://www.hollins.edu/wp-content/uploads/2023/05/HLNS21206-04-Brand-Activation_Brand-Guidelines_FINAL.pdf', 'high', 'Official Hollins Brand Guidelines PDF explicitly prints Tinker Green HEX #006F53 as primary and Everett Gold HEX #9A722C as complementary.'),
  ('hope-international-university', '120537', array['#001489']::text[], 'https://www.trucolor.net/portfolio/golden-state-athletic-conference-1986-1987-through-present/', 'low', 'Official HIU athletics quick facts confirm Fullerton institution and navy/white/gray; TruColor GSAC index matches Hope International University and prints current Blue #001489. Neutrals omitted.'),
  ('springfield-college-regional-online-and-continuing-education', '475273', array['#862633']::text[], 'https://springfield.edu/sites/default/files/brand-guidelines-for-web.pdf', 'high', 'The IPEDS row is Springfield College Regional, Online, and Continuing Education, an official Springfield College unit. Springfield College official brand toolkit explicitly prints Springfield Maroon #862633; inherited institution palette is an exact unit match.'),
  ('louisiana-state-university-and-agricultural-and-mechanical', '159391', array['#582D83', '#FFC82C']::text[], 'https://www.brandcolorcode.com/louisiana-state-university-lsu', 'low', 'Official LSU materials/search confirm purple/gold identity; BrandColorCode institution page prints Purple #582D83 and Gold #FFC82C. Correct institution is main LSU, not LSU Health or LSU Law.'),
  ('university-of-hawaii-at-manoa', '141574', array['#024731']::text[], 'https://www.hawaii.edu/offices/communications/standards/graphics-standards/signatures/', 'high', 'University of Hawaii official signature standards explicitly state UH Manoa color HTML #024731; black is neutral and omitted.'),
  ('cuny-queens-college', '190664', array['#E71939']::text[], 'https://www.qc.cuny.edu/communications/wp-content/uploads/sites/21/2022/07/QC_BGG_Public.pdf', 'high', 'Official Queens College CUNY brand guide PDF prints Queens College Red RGB 231,25,57, normalized to HEX #E71939; black/gray neutrals omitted.'),
  ('university-of-massachusetts-boston', '166638', array['#005A8B']::text[], 'https://www.umb.edu/media/umassboston/content-assets/cpm/pdf/Style_Guide_v7.pdf', 'high', 'Official guide prints Beacon Blue #005A8B.'),
  ('florida-southwestern-state-college', '133508', array['#470A68', '#00BFB3']::text[], 'https://docs.fsw.edu/docnew/action.php?fDocumentId=354369&kt_path_info=ktcore.actions.document.view', 'high', 'FSW official operating-procedures page explicitly states Purple HTML 470A68 and Aqua HTML 00BFB3.'),
  ('st-johns-university-new-york', '195809', array['#CF102D', '#051C2C']::text[], 'https://www.stjohns.edu/sites/default/files/uploads/sju_style_guide.pdf', 'high', 'Official guide prints Red #CF102D and Blue #051C2C.'),
  ('commonwealth-university-of-pennsylvania', '498562', array['#921E33', '#F3D03E']::text[], 'https://www.commonwealthu.edu/documents/university-style-guide', 'high', 'Current official Commonwealth University style guide explicitly defines university-wide CU Red #921E33 and Gold #F3D03E; it distinguishes the integrated university palette from legacy Bloomsburg/Lock Haven/Mansfield campus palettes.'),
  ('prairie-view-a-and-m-university', '227526', array['#582C83', '#EAAA00']::text[], 'https://www.pvamu.edu/marcomm/resources/colors/', 'high', 'Official Prairie View A&M Marketing and Communications Colors page labels PVAMU Purple and Gold as primary and lists HEX #582c83 and #eaaa00.'),
  ('quinnipiac-university', '130226', array['#131D43', '#FFB718']::text[], 'https://www.brandcolorcode.com/quinnipiac-university', 'low', 'Official Quinnipiac search confirms institution but no exact digital values; BrandColorCode institution page prints Navy #131D43 and Gold #FFB718.'),
  ('columbia-college', '177065', array['#144678']::text[], 'https://www.ccis.edu/_files/directory/strategic-communications/brand-style-guide-pdf.pdf', 'high', 'Columbia College official brand guide digital palette explicitly prints navy #144678; other listed colors are secondary/supporting and omitted.'),
  ('southeastern-university', '137564', array['#E31B23']::text[], 'https://www.brandcolorcode.com/southeastern-university', 'low', 'Official Southeastern University (Lakeland, Florida; IPEDS 137564) pages were checked but no readable exact digital palette was found. BrandColorCode has an exact Southeastern University match and prints Red #E31B23; black neutral omitted and fallback marked low.'),
  ('regent-university', '231651', array['#002F6C', '#00833F', '#CFB87C']::text[], 'https://www.regent.edu/university-marketing/', 'high', 'Official marketing page prints Blue #002F6C, Green #00833F, Gold #CFB87C.'),
  ('college-of-southern-idaho', '142559', array['#FDC82F']::text[], 'https://web.archive.org/web/20201001014217id_/https://www.csi.edu/_files/pdf/public-information/visual-identity-guide.pdf', 'high', 'The direct CSI Visual Identity Guide URL returned 404, so this uses the stable Wayback capture of the official CSI PDF (2020-10-01). The archived official guide explicitly lists Gold RGB 255/195/0 and Hex FDC82F (#FDC82F); black/gray are neutrals and omitted. This value is archival, not presented as a live CSI URL.'),
  ('alabama-state-university', '100724', array['#C99700']::text[], 'https://www.alasu.edu/administration/institutional-effectiveness/marketing-and-strategic-communications/brand-guidelines.pdf', 'high', 'Official Alabama State University Brand Guidelines PDF explicitly prints ASU Old Gold RGB 201,151,0 and HEX #C99700; black is a neutral and omitted.'),
  ('university-of-la-verne', '117140', array['#2C5234', '#FF8200']::text[], 'https://www.laverne.edu/identity/colors/', 'high', 'Official La Verne Colors page labels primary Green #2C5234 and Orange #FF8200.'),
  ('college-of-coastal-georgia', '139250', array['#1A8FCE']::text[], 'https://www.ccga.edu/wp-content/uploads/2022/08/Visual_Identity_Standards_2020-1.pdf', 'high', 'College of Coastal Georgia official visual identity standards explicitly give primary blue RGB 26/143/206 (losslessly #1A8FCE); gray/metallic and black/white omitted.'),
  ('suny-at-fredonia', '196158', array['#0033A0']::text[], 'https://www.brandcolorcode.com/suny-fredonia', 'low', 'Official Fredonia source confirms Royal Blue/White prose and Pantone 286; BrandColorCode institution page prints Blue #0033A0. Black/white omitted.'),
  ('xavier-university-of-louisiana', '160904', array['#FFC530']::text[], 'https://www.xula.edu/university-communications/documents/xula-identity-guidelines-2025.pdf', 'high', 'The prior XULA identity-guidelinesupdated-6_23.pdf URL returned 404. The reachable current official Xavier University of Louisiana 2025 identity-guidelines PDF explicitly prints primary Xavier Gold HEX #FFC530 (RGB 255/197/48); white is neutral and omitted.'),
  ('governors-state-university', '145336', array['#E57726', '#405866']::text[], 'https://www.govst.edu/branding', 'high', 'Live official Governors State Branding page explicitly prints GovState Orange HEX #e57726 and GovState Blue HEX #405866; black neutral omitted. The prior /brandguide URL was stale, so this live official page is used.'),
  ('university-of-illinois-springfield', '148654', array['#003366', '#C8B18B']::text[], 'https://www.uis.edu/brand/colors-fonts', 'high', 'Official page prints Blue #003366 and Gold #C8B18B.'),
  ('taylor-university', '152530', array['#522D72', '#C1A027']::text[], 'https://www.taylor.edu/about/brand/colors-fonts', 'high', 'Taylor official brand page explicitly prints Taylor Purple #522D72 and Legacy Gold #C1A027 as primary/secondary palette colors.'),
  ('arcadia-university', '211088', array['#9D2235']::text[], 'https://www.arcadia.edu/wp-content/uploads/2023/06/22-MC_Arcadia-Brand-Guideline-v24_truncated-for-community.pdf', 'high', 'Official Arcadia University Brand Guidelines PDF labels Scarlette as a primary color and explicitly lists HEX #9D2235. Other primary entries are gray neutrals, omitted.'),
  ('university-of-maine-at-presque-isle', '161341', array['#004A9F', '#FFCC33']::text[], 'https://www.umpi.edu/offices/wp-content/uploads/sites/25/2023/11/umpi-identity-standards_brand-book.pdf', 'high', 'Official standards print Blue #004A9F and Gold #FFCC33.');

update public.institution_directory as directory
set brand_colors = seed.brand_colors,
    brand_colors_source = seed.source,
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = seed.confidence,
    brand_colors_notes = seed.notes
from brand_color_seed_batch_34 as seed
where directory.school_id = seed.school_id
  and directory.ipeds_id = seed.ipeds_id
  and directory.brand_colors is null;

do $$
declare
  uncovered_count integer;
begin
  select count(*) into uncovered_count
  from brand_color_seed_batch_34 as seed
  left join public.institution_directory as directory
    on directory.school_id = seed.school_id
   and directory.ipeds_id = seed.ipeds_id
  where directory.brand_colors is null;

  if uncovered_count <> 0 then
    raise exception 'Brand-color batch 34 verification found % uncovered rows', uncovered_count;
  end if;
end$$;

commit;
