-- Brand-color coverage-gap batch 6 of 8 (overall scouting batch 35).
-- Researched 30 public in-scope schools in coverage/enrollment order;
-- 23 have defensible colors (13 high, 3 medium, 7 low)
-- and 7 remain null after documented source and identity checks.
-- Audit records: data/brand-colors/batch-35-2026-08-25.jsonl

begin;

create temporary table brand_color_seed_batch_35 (
  school_id text primary key,
  ipeds_id text not null,
  brand_colors text[] not null,
  source text not null,
  confidence text not null,
  notes text not null
) on commit drop;

insert into brand_color_seed_batch_35 (
  school_id, ipeds_id, brand_colors, source, confidence, notes
)
values
  ('suny-college-of-agriculture-and-technology-at-cobleskill', '196033', array['#CF4817', '#6A7431']::text[], 'https://www.cobleskill.edu/about/leadership/campus-policies/pdfs/179048314_logo_guidelines_publish_04-22-26.pdf', 'high', 'SUNY Cobleskill official brand identity colors explicitly print primary Harvest Orange #cf4817 and Mossy Green #6a7431.'),
  ('florida-polytechnic-university', '482936', array['#501D83', '#009FDF']::text[], 'https://floridapoly.edu/about/departments/strategic-communications/', 'high', 'Repaired dead brand-manual URL with reachable official Florida Poly Brand Center page; it labels Poly Purple #501D83 and Cyber Blue #009FDF as primary colors.'),
  ('hillsdale-college', '170286', array['#091633']::text[], 'https://www.brandcolorcode.com/hillsdale-college', 'low', 'Official Hillsdale search found prose/navy references but no citable hex/RGB. BrandColorCode exact Hillsdale College fallback gives Blue #091633; white omitted as neutral; low confidence.'),
  ('alfred-university', '188641', array['#550D8A', '#F5AA01']::text[], 'https://www.brandcolorcode.com/alfred-university', 'low', 'Official search found names but not digital values; third-party fallback reports #550D8A and #F5AA01.'),
  ('university-of-dallas', '224323', array['#001A4B']::text[], 'https://teamcolorcodes.com/university-of-dallas-crusaders-color-codes/', 'low', 'Official University of Dallas pages confirm Navy/White but no institutional hex table. Team Color Codes exact University of Dallas Crusaders record (Irving, TX) gives Navy #001A4B; neutrals omitted; low-confidence fallback.'),
  ('concordia-university-chicago', '144351', array['#9D2235', '#84754E']::text[], 'https://webserv.cuchicago.edu/files/forms-repository/communications-and-marketing-services/CUC%20Visual%20Brand%20Guidelines.pdf', 'high', 'Official guide prints maroon #9D2235 and gold #84754E.'),
  ('hardin-simmons-university', '225247', array['#581483', '#AD841F']::text[], 'https://www.hsutx.edu/about-hsu/leadership-administration/university-marketing/hsu-brand-resources/', 'high', 'Official HSU Brand Resources page explicitly lists Academic Purple HEX #581483 and Academic Gold HEX #AD841F; athletics Spirit Gold was excluded in favor of institutional academic colors.'),
  ('concordia-university-texas', '224004', array['#582D83', '#FFD24F']::text[], 'https://www.concordia.edu/about/uploads/CTXBrandGuidelines-MediaKit.pdf', 'high', 'Concordia University Texas official brand guide explicitly prints primary purple #582d83 and gold #ffd24f; gray omitted.'),
  ('saint-martins-university', '236452', array['#BA0C2F']::text[], 'https://www.brandcolorcode.com/saint-martins-university', 'low', 'Official Saint Martin’s brand-resource search did not expose a readable exact digital palette. BrandColorCode has an exact Saint Martin’s University match and prints Red #BA0C2F; white/black neutrals omitted.'),
  ('hendrix-college', '107080', array['#E96B10']::text[], 'https://www.hendrix.edu/news/news.aspx?id=935', 'medium', 'Official page prints Hendrix Orange #E96B10; older page.'),
  ('huntington-university', '150941', array['#115740']::text[], 'https://www.trucolor.net/portfolio/crossroads-league-1959-1960-through-present/', 'low', 'Official Huntington search confirms Forest Green but no explicit hex/RGB. TruColor exact Huntington University (Huntington, IN) record gives current Forest Green #115740; white/black/silver omitted as neutrals; low confidence.'),
  ('reinhardt-university', '140872', array['#003468', '#EDAA00']::text[], 'https://www.reinhardt.edu/faculty-and-staff/marketing/', 'high', 'Official Reinhardt marketing page explicitly prints Reinhardt Blue HEX #003468 and Reinhardt Gold HEX #EDAA00.'),
  ('dillard-university', '158802', array['#003594']::text[], 'https://www.dillard.edu/wp-content/uploads/2023/07/dillard-university-brand-guidelines-2022.pdf', 'high', 'Official guidelines print primary blue #003594.'),
  ('bluefield-state-university', '237215', array['#13294B', '#B9975B']::text[], 'https://www.trucolor.net/portfolio/central-intercollegiate-athletic-association-official-colors-and-nicknames-1912-1913-through-present/', 'low', 'Official Bluefield State brand-guide link did not expose citable hex/RGB. TruColor exact Bluefield State University, West Virginia record gives Blue #13294B and Gold #B9975B; low-confidence third-party fallback.'),
  ('brenau-university', '139199', array['#FBCB6C']::text[], 'https://intranet.brenau.edu/wp-content/uploads/sites/11/press-kit/brenau_style_guide_031522.pdf', 'high', 'Official Brenau style guide PDF explicitly prints Web Gold HEX #FBCB6C; black is the primary neutral and Blue #52657F is secondary, so only the primary chromatic value is retained.'),
  ('new-mexico-institute-of-mining-and-technology', '187967', array['#182952']::text[], 'https://www.nmt.edu/mac/styleguide/brand-styleguide.pdf', 'high', 'Repaired dead 2023 brand-board URL with reachable current official New Mexico Tech Brand Style Guide; current primary Techie Blue is HEX #182952. This supersedes the stale #0C2753 anchor value.'),
  ('kansas-wesleyan-university', '155414', array['#5A2A82', '#FEC524']::text[], 'https://www.kwu.edu/wp-content/uploads/KWU-style-guide-2024-1.pdf', 'medium', 'KWU official style guide explicitly labels purple #5A2A82 and gold #FEC524; the printed RGB for gold differs slightly from the printed hex, so confidence is medium and the literal stated hex is retained.'),
  ('anna-maria-college', '164492', array['#8A1538']::text[], 'https://www.trucolor.net/portfolio/great-northeast-athletic-conference-1995-1996-through-present/#anna-maria-college', 'low', 'Repaired unreachable College Football Commission URL with reachable TruColor GNAC record explicitly matching Anna Maria College in Paxton; current 2009-present athletics record prints Cardinal #8A1538. White/black omitted as neutrals.'),
  ('hampshire-college', '166018', array['#009B9E']::text[], 'https://www.hampshire.edu/sites/default/files/2022-08/HAMP_Brand_Guidelines_COLORS.pdf', 'high', 'Hampshire official visual brand guidelines identify teal as primary and explicitly print #009b9e; charcoal/white are neutral and omitted.'),
  ('ferrum-college', '232089', array['#B4975A']::text[], 'https://www.ferrum.edu/directory/departments/office-of-marketing-and-communications/', 'high', 'Repaired dead PDF URL with reachable official Ferrum Marketing and Communications page; it states official Ferrum colors are black and gold and prints gold HEX #B4975A. Black omitted as neutral.'),
  ('mount-marty-university', '219198', array['#091F40', '#FDB71A']::text[], 'https://admission.mountmarty.edu/portal/marketing', 'high', 'Mount Marty official marketing portal explicitly prints primary Navy Blue #091F40 and Gold #FDB71A; white omitted.'),
  ('northwest-university', '236133', array['#063966', '#B0013A']::text[], 'https://www.northwestu.edu/assets/documents/marketing/brand-and-visual-style-guide.pdf', 'high', 'Official Northwest University (Kirkland, Washington) brand and visual style guide explicitly prints NU Blue HEX #063966 and PMS 201 Red HEX #B0013A; Northwest Missouri State sources excluded.'),
  ('drury-university-college-of-continuing-professional-studies', '492801', array['#BA0C2F']::text[], 'https://www.drury.edu/wp-content/uploads/2023/06/150th-Style-Sheet-3985.pdf', 'medium', 'Official Drury style sheet prints Scarlet #BA0C2F; continuing studies uses university brand.');

update public.institution_directory as directory
set brand_colors = seed.brand_colors,
    brand_colors_source = seed.source,
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = seed.confidence,
    brand_colors_notes = seed.notes
from brand_color_seed_batch_35 as seed
where directory.school_id = seed.school_id
  and directory.ipeds_id = seed.ipeds_id
  and directory.brand_colors is null;

do $$
declare
  uncovered_count integer;
begin
  select count(*) into uncovered_count
  from brand_color_seed_batch_35 as seed
  left join public.institution_directory as directory
    on directory.school_id = seed.school_id
   and directory.ipeds_id = seed.ipeds_id
  where directory.brand_colors is null;

  if uncovered_count <> 0 then
    raise exception 'Brand-color batch 35 verification found % uncovered rows', uncovered_count;
  end if;
end$$;

commit;
