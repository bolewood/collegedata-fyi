-- Brand-color coverage-gap batch 4 of 8 (overall scouting batch 33).
-- Researched 30 public in-scope schools in coverage/enrollment order;
-- 28 have defensible colors (19 high, 5 medium, 4 low)
-- and 2 remain null after documented source and identity checks.
-- Audit records: data/brand-colors/batch-33-2026-08-25.jsonl

begin;

create temporary table brand_color_seed_batch_33 (
  school_id text primary key,
  ipeds_id text not null,
  brand_colors text[] not null,
  source text not null,
  confidence text not null,
  notes text not null
) on commit drop;

insert into brand_color_seed_batch_33 (
  school_id, ipeds_id, brand_colors, source, confidence, notes
)
values
  ('northeastern-university-professional-programs', '482705', array['#C8102E']::text[], 'https://advancement.northeastern.edu/wp-content/uploads/2023/02/EXP_StyleGuide-February-2023.pdf', 'medium', 'Official Northeastern campaign style guide explicitly prints primary Red #C8102E; record is for the professional-programs institution row and uses the university-wide palette. Neutral black/white omitted.'),
  ('kent-state-university-at-tuscarawas', '203483', array['#0A0D6F', '#FFAB1B']::text[], 'https://www.kent.edu/ucm/kent-state-university-seal', 'high', 'Official Kent State University page lists web blue HEX #0A0D6F and web gold HEX #FFAB1B for the university seal. Tuscarawas and Geauga are Kent State regional campuses; same university palette applied.'),
  ('kent-state-university-at-trumbull', '203474', array['#0A0D6F', '#FFAB1B']::text[], 'https://www.kent.edu/ucm/kent-state-university-seal', 'medium', 'Official Kent identity prints blue #0A0D6F and gold #FFAB1B; Trumbull uses university identity.'),
  ('swarthmore', '216287', array['#84000D']::text[], 'https://brandpad.io/swarthmore/', 'low', 'Official-domain Swarthmore search found current prose/garnet references but no extractable hex in the official PDF. The current Swarthmore College brand identity guide hosted on Brandpad explicitly prints primary Garnet #84000D; low confidence because host is not swarthmore.edu.'),
  ('kent-state-university-at-geauga', '203526', array['#0A0D6F', '#FFAB1B']::text[], 'https://www.kent.edu/ucm/kent-state-university-seal', 'high', 'Official Kent State University page lists web blue HEX #0A0D6F and web gold HEX #FFAB1B for the university seal. Tuscarawas and Geauga are Kent State regional campuses; same university palette applied.'),
  ('capital-university', '201548', array['#380982']::text[], 'https://www.capital.edu/media/q52lkxvz/comets-style-guide-2021.pdf?n=3464', 'high', 'Repaired dead general stylebook URL with reachable official Capital Comets style guide; it states the Comet colors are approved by General University Branding Guidelines and prints purple HEX #380982.'),
  ('concord-university', '237330', array['#862633']::text[], 'https://www.trucolor.net/portfolio/mountain-east-conference-2012-2013-through-present/', 'low', 'Official Concord pages confirm Maroon/Gray but no hex/RGB. TruColor exact Concord University (Athens, WV) institutional record gives Burgundy #862633; gray omitted as neutral and conflicting older indexes were not used; low confidence.'),
  ('new-mexico-highlands-university', '187897', array['#5B2D82']::text[], 'https://its.nmhu.edu/intranetuploads/002127-nmhu_graphic-76201090336.pdf', 'high', 'Official NMHU branding PDF labels the primary identity color PMS 268C and explicitly prints RGB 91/45/130 and HEX #5B2D82. White is described as a complement but omitted as neutral.'),
  ('haverford-college', '212911', array['#981E32']::text[], 'https://www.haverford.edu/sites/default/files/Office/Communications/Visual-Identity-Guidelines.pdf', 'medium', 'Official guide prints RGB 152/30/50, converted to #981E32.'),
  ('claremont-mckenna', '112260', array['#981A31']::text[], 'https://www.cmc.edu/news/identity-guidelines', 'high', 'CMC official identity guidelines state CMC Maroon RGB 152/26/49 (losslessly #981A31); black is neutral and omitted.'),
  ('bryn-mawr-college', '211273', array['#FFC600', '#002858']::text[], 'https://www.brynmawr.edu/inside/offices-services/communications-marketing/guides-resources/institutional-positioning-guide/design-visual-guidance/color-palette', 'high', 'Official Bryn Mawr College Color Palette labels Lanterns Glow and Navy as primary colors and lists WEB #FFC600 and #002858.'),
  ('kent-state-university-at-ashtabula', '203447', array['#0A0D6F', '#FFAB1B']::text[], 'https://www.kent.edu/ucm/kent-state-university-seal', 'medium', 'Official Kent identity prints blue #0A0D6F and gold #FFAB1B; Ashtabula uses university identity.'),
  ('viterbo-university', '240107', array['#A51E36', '#1F2F5F']::text[], 'https://www.viterbo.edu/sites/default/files/2024-10/ViterboBrandGuidelines2024.pdf', 'high', 'Viterbo official 2024 guide explicitly prints primary Viterbo Red #a51e36 and Viterbo Navy #1f2f5f; white omitted.'),
  ('pitzer-college', '121257', array['#F7941D']::text[], 'https://www.pitzer.edu/visual-brand-style-guide', 'high', 'Official Pitzer Visual Brand Style Guide explicitly prints Pitzer Orange RGB 247,148,29 / HEX #F7941D and identifies orange/white as the school palette.'),
  ('kent-state-university-at-salem', '203492', array['#003976', '#EFAB00']::text[], 'https://www.kent.edu/brand/swatches', 'high', 'Kent State official brand swatches explicitly print primary blue #003976 and gold #EFAB00; applies to regional campus branding including Salem.'),
  ('allegheny-college', '210669', array['#1B3054', '#FEDA48']::text[], 'https://sites.allegheny.edu/brand-center/colors/', 'high', 'Official Allegheny Brand Center Colors page explicitly prints Navy RGB 27,48,84 / HEX #1B3054 and Bold Gold RGB 254,218,72 / HEX #FEDA48.'),
  ('university-of-pikeville', '157535', array['#FF671D']::text[], 'https://www.upike.edu/offices/marcomm/social-media-guidelines/brand-guidelines/', 'high', 'Official UPIKE brand guidelines print main Orange RGB 255/103/29 and HEX #FF671D.'),
  ('scripps-college', '123165', array['#326E5A']::text[], 'https://inside.scrippscollege.edu/communication/wp-content/uploads/sites/7/files/Style_guide_2019.pdf', 'high', 'Scripps official style guide identifies preferred College color and explicitly prints #326E5A; gray/black are neutral and omitted.'),
  ('central-college', '153108', array['#CB2026']::text[], 'https://brand.central.edu/graphic-identity/', 'high', 'Official Central College (Iowa) brand identity page lists the primary web red as HEX #CB2026.'),
  ('guilford-college', '198613', array['#981B36']::text[], 'https://guilfordquakers.com/sports/2021/10/27/information-sportsinfo.aspx', 'medium', 'Repaired dead institutional brandbook URL with reachable official Guilford Athletics Communications color table; it identifies Guilford College and prints Cardinal HEX 981b36. The former Tan value was omitted because this live table lists Cardinal and Grey, with grey treated as neutral.'),
  ('albertus-magnus-college', '128498', array['#003D98']::text[], 'https://encycolorpedia.com/schools/us/albertus-magnus-college', 'low', 'Official Albertus search confirms Blue/White but no explicit hex/RGB. Encycolorpedia exact Albertus Magnus College school-color record gives Blue #003D98; low-confidence third-party fallback.'),
  ('harvey-mudd', '115409', array['#000000', '#FDB913']::text[], 'https://www.hmc.edu/communications/identity-standards/color-palette/', 'high', 'Official Harvey Mudd College Brand Color Palette identifies black and gold as school colors and lists HMC Black WEB #000000 and HMC Gold WEB #FDB913.'),
  ('tennessee-wesleyan-university', '221731', array['#0032A0']::text[], 'https://www.trucolor.net/portfolio/appalachian-athletic-conference-2001-2002-through-present/', 'low', 'Official Tennessee Wesleyan search confirms Bulldogs/blue identity; TruColor conference index matches Tennessee Wesleyan and prints current Royal Blue #0032A0. White omitted.'),
  ('rocky-mountain-college', '180595', array['#0E572D', '#806F3F']::text[], 'https://rocky.edu/marketing-communication/marketing-toolkit/', 'high', 'Rocky Mountain College marketing toolkit explicitly lists primary palette hexes #0e572d and #806f3f; pale tan #bfb290 omitted as neutral/supporting.'),
  ('miami-university-middletown', '204015', array['#C41230', '#FFFFFF']::text[], 'https://miamioh.edu/miami-brand/_files/documents/brand-standards-2025_508.pdf', 'high', 'Current official Miami University Brand Guide primary palette explicitly lists Miami Red HEX C41230 and White HEX FFFFFF. Hamilton and Middletown are named Miami University regional campuses; same institutional palette applied.'),
  ('agnes-scott-college', '138600', array['#633296', '#F7DA00', '#EFB900']::text[], 'https://www.agnesscott.edu/communications-and-marketing/brand-guidelines/our-color-palette.html', 'high', 'Official palette prints Purple #633296, yellow #F7DA00, gold #EFB900.'),
  ('kent-state-university-at-east-liverpool', '203456', array['#003976', '#EFAB00']::text[], 'https://www.kent.edu/brand/swatches', 'high', 'Kent State official brand swatches explicitly print primary blue #003976 and gold #EFAB00; applies to regional campus branding including East Liverpool.'),
  ('hiram-college', '203128', array['#0B2136']::text[], 'https://www.hiram.edu/marketing-and-media-relations/brand-guidelines/typography-and-colors/', 'high', 'Official page prints Dark Blue #0B2136.');

update public.institution_directory as directory
set brand_colors = seed.brand_colors,
    brand_colors_source = seed.source,
    brand_colors_checked_at = date '2026-08-25',
    brand_colors_confidence = seed.confidence,
    brand_colors_notes = seed.notes
from brand_color_seed_batch_33 as seed
where directory.school_id = seed.school_id
  and directory.ipeds_id = seed.ipeds_id
  and directory.brand_colors is null;

do $$
declare
  uncovered_count integer;
begin
  select count(*) into uncovered_count
  from brand_color_seed_batch_33 as seed
  left join public.institution_directory as directory
    on directory.school_id = seed.school_id
   and directory.ipeds_id = seed.ipeds_id
  where directory.brand_colors is null;

  if uncovered_count <> 0 then
    raise exception 'Brand-color batch 33 verification found % uncovered rows', uncovered_count;
  end if;
end$$;

commit;
