-- Batch 27 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given (only trimmed a mechanically-
-- attached neutral, if any): southern-virginia-university (Crimson/White/
-- Silver, all three explicitly "the primary colors" per svu.edu -- kept as-
-- is, 3-of-3 match), washington-college (dark red/white, exact match via
-- the athletics site's own site_colors JSON).
--
-- Corrected (candidate hex, color set, or source did not match the
-- school's own current official source): university-of-pittsburgh-bradford
-- (candidate's Pitt Athletics PDF groups white under a separate Secondary
-- Palette, not Primary; re-sourced to brand.pitt.edu's university-wide
-- Color Palettes page -- "Primary Colors ... Royal and Gold" -- kept only
-- the two primary chromatics, dropped white), franklin-pierce-university
-- (candidate's citation domain is dead with no Wayback capture; the two
-- obvious athletics-domain guesses, fpuathletics.com and ravenathletics.com,
-- are WRONG SCHOOLS -- Fresno Pacific and Benedictine College respectively,
-- both confirmed by og:site_name -- re-sourced to the real fpuravens.com
-- site_colors JSON, maroon corrected A91938->6F1931, gray confirmed exact),
-- california-institute-of-technology (single official primary color
-- confirmed #FF6C0C; candidate's white and near-black do not appear
-- anywhere on the source page at all, dropped), barton-college (blue
-- corrected 18468B->003082 via the page's own "Colors: Royal Blue & White"
-- prose plus site_colors JSON, black dropped as ungrounded), st-thomas-
-- aquinas-college (gold corrected F5BE48->F3BE48 one digit, white dropped
-- as not part of the document's 2-color Primary Palette), rockford-
-- university ("Our primary colors are Purple and White" -- kept purple/
-- white exactly, dropped candidate's gold which the same document frames
-- as part of a separate secondary/extended palette), keuka-college (green
-- corrected 00583D->0A5942 via the page's own Primary Colors table, white
-- dropped), saint-josephs-college-of-maine (re-sourced from a 404'd page to
-- the live gomonks.com homepage after confirming it's the correct school by
-- og:site_name; blue corrected 0077D4->0246BE via site_colors JSON,
-- corroborated by sjcme.edu's own logo SVG fill; white/near-black dropped),
-- regis-college (re-sourced from a 403'd page to the live homepage after
-- confirming og:site_name is Regis College MA, not Regis University CO;
-- both hexes corrected via the page's own theme-color meta tags, white
-- dropped), west-virginia-wesleyan-college (orange corrected FF4C00->
-- F05123 and gray added via a recovered real PDF -- most Wayback captures
-- of this exact filename are 404 stubs, found one real capture -- "the
-- three primary colors" explicitly named as orange/gray/black, white
-- dropped as a fourth not on that list), marietta-college (the 37-page
-- official PDF is Pantone-only with zero hex anywhere; cross-referenced
-- hex via marietta.edu's own CSS classes explicitly named
-- "marietta-blue"/"metallic-silver" matching the PDF's own color names --
-- all three kept, matching candidate exactly), wisconsin-lutheran-college
-- (kept only the single "primary brand color" Green #006643 per the
-- document's own singular framing, black/white dropped as complementary
-- neutrals not primaries), maine-maritime-academy (all three candidate
-- hexes replaced -- navy 002F6C, cyan 36C6FD, gold FFCD00 -- via the
-- document's own "OFFICIAL COLORS" block with explicit WEB hex, white
-- dropped, none of candidate's guesses were on the page), manchester-
-- university (recovered via Wayback after a live 404; kept Black + the
-- institutional Manchester Gold per "Vegas Gold is acceptable only for
-- athletics and is not to be used as a substitute ... in other
-- institutional marks", candidate's athletics-only Vegas Gold and neutral
-- gray dropped), university-of-minnesota-morris (recovered via Wayback
-- after the live netfiles.umn.edu link died; candidate's white corrected to
-- the document's actual third primary color, Morris Green -- "the primary
-- color palette consists of Morris Gold, Morris Green, and Morris Maroon",
-- all three chromatic and kept), beloit-college (confirmed candidate's
-- blue/gold exactly via the document's own "Beloit College colors" labels,
-- white dropped as not part of that 2-color list), livingstone-college
-- (blue corrected 86B0C6->8CB0BF -- candidate's guess was actually a
-- decorative gradient stop elsewhere on the page, not the labeled "Blue
-- Specifications" value -- "the official colors of Livingstone College --
-- black and blue" kept exactly, white dropped), william-jewell-college
-- (recovered via Wayback after a live 404; red confirmed exact via "Jewell's
-- official colors are cardinal red and black", white dropped), hilbert-
-- college (recovered via Wayback after a live 404; kept only the single
-- labeled "Primary Hilbert Blue", gold/white dropped as explicitly
-- "Secondary"), king-university (both hexes corrected via the page's own
-- "Colors: Blue & Scarlet" prose plus site_colors JSON, white dropped),
-- salem-university (green corrected 198643->006233 via the page's own
-- "Colors: Green and White" prose plus site_colors JSON, near-black
-- dropped), the-university-of-olivet (red corrected BD0034->B21D38 via the
-- fast-facts page's own site-wide CSS primary-menu color, confirming the
-- page's stated "Colors: Red and white"), shaw-university (candidate's CIAA
-- conference-site citation states no hex at all and its visible hex codes
-- belong to the CIAA's own branding, not Shaw's -- re-sourced to Shaw's own
-- shawbears.com site_colors JSON, garnet and gold both corrected), lees-
-- mcrae-college (candidate's citation 403s and its Wayback recovery is
-- Pantone-only; re-sourced to lmc.edu's own CSS, whose explicitly
-- green-/gold-named classes gave both corrected hexes, white dropped),
-- wabash-college (scarlet corrected EC1C2C->B7242E via the athletics site's
-- own site_colors JSON; no dedicated wabash.edu brand page with a stated
-- hex was found; candidate's peach/tan accent dropped as ungrounded),
-- wilson-college (blue corrected 04428D->1C3F95 via site_colors JSON;
-- kept single chromatic ink, white and the non-chromatic gray both
-- dropped), presbyterian-college (recovered via Wayback after a live 404;
-- blue corrected 0060A9->0033A0, red confirmed exact, candidate's white
-- corrected to the document's actual third primary color, Rail Steel
-- Gray -- all three explicitly the "PRIMARY COLORS" per Presbyterian's own
-- brand guide), lake-erie-college (candidate's cited PDF has never been
-- successfully archived across ~30 Wayback crawls -- always a 404 stub;
-- re-sourced to the live lakeeriestorm.com site_colors JSON, green
-- corrected 113D2A->153C2E, white/black replaced with the site's actual
-- configured near-black secondary).
--
-- See data/brand-colors/batch-27-2026-08-24.jsonl for the full per-school
-- record. No rows were left null in this batch -- every school had a
-- usable on-domain source once the dead/wrong-school citations were
-- worked around.

with seed (
  school_id,
  ipeds_id,
  brand_colors,
  brand_colors_source,
  brand_colors_confidence,
  brand_colors_notes
) as (
  values
    (
      'university-of-pittsburgh-bradford',
      '215266',
      array['#003594', '#FFB81C']::text[],
      'https://www.brand.pitt.edu/brand-elements/color-palettes',
      'high',
      'Candidate''s cited athletics PDF (pitt_idmanual_21.pdf) confirmed live; its Color Palette table lists PITT ROYAL #003594 and PITT GOLD #FFB81C under ''PRIMARY PALETTE'', with WHITE and ANTHRACITE grouped separately under ''SECONDARY PALETTE''. Re-sourced to the University''s main brand.pitt.edu Color Palettes page (university-wide, applies to the Bradford branch campus): ''Pitt relies on our historical Royal and Gold as our primary and most-used colors ... Primary Colors ... Pitt Royal Blue HEX: #003594 ... Pitt Gold HEX: #FFB81C ... Secondary Colors [include] White''. Exact match to candidate''s blue/gold; dropped candidate''s white since it is explicitly Secondary on both documents.'
    ),
    (
      'franklin-pierce-university',
      '182795',
      array['#6F1931', '#6D6E71']::text[],
      'https://fpuravens.com/',
      'medium',
      'Candidate''s eraven.franklinpierce.edu citation domain no longer resolves and has no Wayback capture. The obvious replacement domains are wrong-school traps: fpuathletics.com is actually Fresno Pacific University Athletics and ravenathletics.com is Benedictine College (also Ravens), neither Franklin Pierce -- both ruled out via og:site_name. Found the real official athletics site via web search: fpuravens.com (og:site_name: ''Franklin Pierce University''). Its own site_colors JSON declares primary_background #6F1931 (maroon) and secondary_background #6D6E71 (gray). Corrected candidate''s guessed maroon (#A91938, not found anywhere); gray matched candidate exactly. Dropped candidate''s white.'
    ),
    (
      'california-institute-of-technology',
      '110404',
      array['#FF6C0C']::text[],
      'https://identity.caltech.edu/colors',
      'high',
      'Candidate''s citation confirmed live. ''Caltech''''s official color system is made up of four palettes: a primary color, a neutral palette, a deep palette, and a bright palette ... Primary Color: Caltech''''s primary color is Pantone MS 1585c Orange ... HEX #FF6C0C'' -- exact match to candidate, explicitly the sole primary color (singular). Candidate''s white (#FFFFFF) and near-black (#010101) do not appear anywhere on this page -- not in primary, neutral, deep, or bright palettes -- so both dropped rather than guessed.'
    ),
    (
      'barton-college',
      '197911',
      array['#003082', '#FFFFFF']::text[],
      'https://bartonbulldogs.com/sports/2020/7/13/athletics-quickfacts-index.aspx',
      'medium',
      'Candidate''s citation confirmed live. Its own prose states ''Colors: Royal Blue & White'' (no black mentioned), and its Sidearm site_colors JSON declares primary_background #003082. Corrected candidate''s guessed blue (#18468B, not found on-domain) to the site''s actual configured royal blue; kept White per the page''s own two-color naming; dropped candidate''s black, only a generic secondary_background UI default not named in the prose.'
    ),
    (
      'st-thomas-aquinas-college',
      '195243',
      array['#72263D', '#F3BE48']::text[],
      'https://stac.edu/about/logo-identity-guidelines/',
      'high',
      'Candidate''s citation confirmed live. ''PRIMARY COLOR PALLETTE ... MAROON ... HEX: #72263D ... GOLD ... HEX: #f3be48'' -- exactly two colors under the Primary heading, both chromatic, followed by a separate ''SECONDARY COLOR PALLETTE''. Maroon matched candidate exactly; corrected candidate''s gold guess (#F5BE48, one digit off) to the document''s actual #F3BE48. Dropped candidate''s white -- not part of the Primary Palette.'
    ),
    (
      'rockford-university',
      '148405',
      array['#522E91', '#FFFFFF']::text[],
      'https://www.rockford.edu/community/marketing-communications/creativeservices/',
      'high',
      'Candidate''s citation confirmed live. ''Brand Color Palette. Our primary colors are Purple (Pantone 2104) and White. However, we also have an extended palette of secondary colors'' -- Purple Web 522e91 (exact match) explicitly paired with White as the only two primary colors; the page''s Gold is explicitly framed as part of the secondary/extended palette. Kept White per the brief''s exception for an explicitly labeled 2-color primary set; dropped candidate''s gold.'
    ),
    (
      'keuka-college',
      '192192',
      array['#0A5942', '#FFC423']::text[],
      'https://www.keuka.edu/brand/visual-identity',
      'high',
      'Candidate''s citation confirmed live. ''Primary Colors'' table lists exactly two chromatic swatches with stated hex: green #0A5942 and gold #FFC423 (Web values), followed by a separate ''Secondary Colors'' section. Gold matched candidate exactly; corrected candidate''s guessed green (#00583D, not on the page) to the document''s actual Primary Colors value. Dropped candidate''s white.'
    ),
    (
      'saint-josephs-college-of-maine',
      '161518',
      array['#0246BE']::text[],
      'https://www.gomonks.com/',
      'medium',
      'Candidate''s /information/why_monks citation 404s; confirmed instead on the live gomonks.com homepage (og:site_name: ''Saint Joseph''''s College of Maine''). Its own Sidearm site_colors JSON declares primary_background #0246be, secondary_background #c9cacc (gray, not chromatic). Corroborated by sjcme.edu''s own homepage logo SVG fill, the near-identical #0446be. Corrected candidate''s guessed blue (#0077D4) and near-black (#010101); dropped candidate''s white and the non-chromatic gray.'
    ),
    (
      'regis-college',
      '167598',
      array['#A52238', '#F4A518']::text[],
      'https://www.goregispride.com/',
      'medium',
      'Candidate''s /Inside_the_Pride citation 403s under curl; confirmed on the live goregispride.com homepage instead (og:site_name: ''Regis (Mass.)'', ruling out the Regis University CO name collision). Its own <meta name="theme-primary-color"> and <meta name="theme-secondary-color"> tags declare #a52238 and #f4a518 respectively. Corrected candidate''s guessed crimson (#B6121D) and gold (#ECA600), neither found on-domain; dropped candidate''s white.'
    ),
    (
      'west-virginia-wesleyan-college',
      '237969',
      array['#F05123', '#949CA1', '#000000']::text[],
      'http://web.archive.org/web/20230817224643/http://www2.wvwc.edu/MCEUploads/PDFs/WVWC%20Style%20Guide%2010.16.pdf',
      'high',
      'Live URL 404s; several Wayback captures of this exact filename are themselves 404 stubs, but the 2023-08-17 capture is a real 5.4MB PDF. ''the logo ... appear in a combination of orange, gray and black ... HEXADECIMAL (FOR WEB): ORANGE f05123, GRAY 949ca1, BLACK 000000 ... Any combination of the three primary colors (PMS 1655, PMS 430, and black) are acceptable'' -- all three explicitly named. Corrected candidate''s guessed orange (#FF4C00, not on the page); added the document''s actual gray; dropped candidate''s white.'
    ),
    (
      'marietta-college',
      '203845',
      array['#00205B', '#FFFFFF', '#8A8D8F']::text[],
      'https://www.marietta.edu/sites/default/files/marietta_college_visual_identity_guidelines.pdf',
      'medium',
      'Candidate''s citation confirmed live and extracts cleanly, but the 37-page guide states colors as Pantone-only throughout (''The official colors of Marietta College are "Marietta Blue" (PMS 281/295), white and metallic silver'') with no hex anywhere. Found matching hex via marietta.edu''s own compiled site CSS: ''.background-color--marietta-blue{background-color:#00205b}'' and ''.background-color--metallic-silver{background-color:#8a8d8f}'', both class names matching the PDF''s own color names. White is explicitly one of only three official colors per the PDF''s prose. All three kept, exact match to candidate; medium confidence since hex was cross-referenced via CSS rather than stated directly in the official document.'
    ),
    (
      'wisconsin-lutheran-college',
      '240338',
      array['#006643']::text[],
      'https://www.wlc.edu/_files/about-wlc/WLC-Quick-Style-Guide.pdf',
      'high',
      'Candidate''s citation confirmed live. ''PRIMARY COLOR PALETTE: Green is WLC''''s primary brand color and should be present in every layout ... Black, gray, and white may be used to complement WLC''''s green.'' Green HEX# 006643 (exact match). Black/gray are explicitly framed as complementary neutrals to the single named primary color, not co-equal primaries. Kept the single chromatic primary; dropped candidate''s white and black.'
    ),
    (
      'maine-maritime-academy',
      '161299',
      array['#002F6C', '#36C6FD', '#FFCD00']::text[],
      'https://mainemaritime.edu/about-mma/wp-content/uploads/sites/2/2022/04/Maine-Maritime-Academy_Brand-Guidelines.pdf',
      'high',
      'Candidate''s citation confirmed live. ''OFFICIAL COLORS'' block states three colors with explicit WEB hex: PMS 294 WEB 002F6C (dark blue), Cyan 100% WEB 36C6FD, PMS 116 WEB FFCD00 (gold) -- none matching candidate''s guessed hexes (#005EAE blue, white, #FEC925 gold), all corrected. Kept all three explicitly-labeled ''OFFICIAL COLORS''.'
    ),
    (
      'manchester-university',
      '151777',
      array['#0A0203', '#EEB111']::text[],
      'http://web.archive.org/web/20220320030102/https://www.manchester.edu/docs/default-source/about-manchester-docs/marketing/mu_athletics_standards.pdf',
      'high',
      'Live URL 404s; recovered the identical PDF via Wayback. ''Our two primary colors are Black and Gold -- which can either be Vegas Gold or Manchester Gold ... Manchester Gray ... [is] considered neutral''. Black HEX #0A0203 (exact match to candidate), Manchester Gold HEX #EEB111. Since ''Vegas Gold is acceptable only for athletics and is not to be used as a substitute for Manchester Gold in other institutional marks or branding,'' used institutional Manchester Gold rather than candidate''s athletics-only Vegas Gold; dropped candidate''s gray as explicitly neutral.'
    ),
    (
      'university-of-minnesota-morris',
      '174251',
      array['#8C1919', '#E19B14', '#827D28']::text[],
      'http://web.archive.org/web/20170305032948/https://netfiles.umn.edu/umm/www/urelations/Morris_Graphic_Identity_Guidelines.pdf',
      'high',
      'Live URL is dead; recovered the identical PDF via a 2017 Wayback capture. ''The University of Minnesota, Morris primary color palette consists of Morris Gold, Morris Green, and Morris Maroon ... hexadecimal numbers for the Web'': Morris Gold #E19B14 and Morris Maroon #8C1919 (exact matches to candidate), Morris Green #827D28. All three explicitly the full primary palette, all chromatic. Corrected candidate''s white to the document''s actual third primary color, Morris Green.'
    ),
    (
      'southern-virginia-university',
      '233611',
      array['#9E1B32', '#FFFFFF', '#A0A1A2']::text[],
      'https://svu.edu/about/brand-guidelines/',
      'high',
      'Candidate''s citation confirmed live. ''The primary colors of Southern Virginia University ... Crimson ... HEX: #9e1b32 ... White ... HEX: #ffffff ... Silver ... HEX: #A0A1A2'' -- exact 3-of-3 match to candidate, all three explicitly named the University''s primary colors. Confirmed candidate''s set exactly as given.'
    ),
    (
      'beloit-college',
      '238333',
      array['#003865', '#F2A900']::text[],
      'https://www.beloit.edu/live/files/504-beloit-college-brand-identity-quick-guide',
      'high',
      'Candidate''s citation confirmed live (1-page PDF). ''Beloit College colors: Beloit Blue ... Hex #003865. Beloit Gold ... Hex #F2A900'' -- exact 2-of-2 match to candidate, the only two named colors on the page. Dropped candidate''s white.'
    ),
    (
      'livingstone-college',
      '198862',
      array['#8CB0BF', '#000000']::text[],
      'https://livingstone.edu/brand-guide/',
      'high',
      'Candidate''s citation confirmed live. ''The official colors of Livingstone College -- black and blue -- are as much a part of our identity ... Blue Specifications ... hex #8CB0BF ... Black Specifications ... hex #000'' -- exact 2-of-2 official colors with stated hex. Corrected candidate''s guessed blue (#86B0C6, actually a decorative gradient stop elsewhere on the page, not the labeled Blue Specification); dropped candidate''s white.'
    ),
    (
      'william-jewell-college',
      '179955',
      array['#E4002B', '#000000']::text[],
      'http://web.archive.org/web/20221229232617/https://www.jewell.edu/sites/default/files/pdf/Jewell_Brand_Standards.pdf',
      'high',
      'Live URL 404s; recovered the identical PDF via Wayback. ''COLORS: Jewell''''s official colors are cardinal red and black. PMS 185 ... HEX/HTML: E4002B'' -- exact match to candidate''s red, explicitly one of only two official colors (black has no printed hex in this section; used standard #000000). Dropped candidate''s white.'
    ),
    (
      'hilbert-college',
      '191621',
      array['#0071CE']::text[],
      'http://web.archive.org/web/20250427224225/https://www.hilbert.edu/news/marketing-communications/logos-style-guide',
      'high',
      'Live URL 404s; recovered the identical page via a 2025 Wayback capture. ''Colors: Primary Hilbert Blue ... Hex: #0071CE. Secondary Hilbert Gold ... Hex: #FFC629. Secondary Black ...'' -- explicit Primary/Secondary split with exactly one Primary color, matching candidate''s blue exactly. Kept the single labeled Primary color; dropped candidate''s gold and white, both Secondary or absent.'
    ),
    (
      'king-university',
      '220516',
      array['#1A428A', '#CF102D']::text[],
      'https://kingtornado.com/sports/2020/4/28/information-Quick-Facts.aspx',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''King University''). Its own prose states ''Colors: Blue & Scarlet'', and its Sidearm site_colors JSON declares primary_background #1A428A, secondary_background #CF102D. Corrected candidate''s guessed blue (#1C448C) and red (#CC132C); dropped candidate''s white.'
    ),
    (
      'salem-university',
      '237783',
      array['#006233', '#FFFFFF']::text[],
      'https://salemtigers.com/sports/2015/1/25/GEN_0125150912.aspx',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''Salem University Athletics''). Its own prose states ''Colors: Green and White'', and its Sidearm site_colors JSON declares primary_background #006233. Corrected candidate''s guessed green (#198643); dropped candidate''s near-black (#23252A), not mentioned in the two-color naming.'
    ),
    (
      'the-university-of-olivet',
      '171599',
      array['#B21D38', '#FFFFFF']::text[],
      'https://www.olivetcollege.edu/about-olivet-college/fast-facts/',
      'medium',
      'Candidate''s citation confirmed live. Its own prose states ''Colors: Red and white'' but prints no hex. The page''s own site-wide CSS hardcodes ''.primary-menu .menu-button a { background: #B21D38; }'' as the site''s own red used sitewide in navigation -- used over candidate''s unconfirmed guess (#BD0034, not found anywhere on-domain).'
    ),
    (
      'washington-college',
      '164216',
      array['#650205', '#FFFFFF']::text[],
      'https://washcollsports.com/sports/2022/6/7/insideAthletics-athletics-communications.aspx',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''Washington College''). Its own Sidearm site_colors JSON declares primary_background #650205, secondary_background #ffffff. Confirmed candidate''s exact pair as-is.'
    ),
    (
      'shaw-university',
      '199643',
      array['#6E1233', '#FBBD29']::text[],
      'https://shawbears.com/',
      'medium',
      'Candidate''s CIAA conference-site news-article citation confirmed live but states no hex -- only ''garnet and white'' prose; its visible hex codes belong to the CIAA''s own site branding, not Shaw''s, and were not used. Re-sourced to Shaw''s own shawbears.com (og:site_name: ''Shaw University''), whose site_colors JSON declares primary_background #6E1233 (garnet), secondary_background #FBBD29 (gold). Corrected candidate''s guessed garnet (#671333) and gold (#F5B544); dropped candidate''s white.'
    ),
    (
      'lees-mcrae-college',
      '198808',
      array['#005C42', '#CF9B2C']::text[],
      'https://www.lmc.edu/_global/_css/styles.css',
      'medium',
      'Candidate''s citation 403s; recovered via Wayback, where its own prose states ''Colors: Green (Pantone 626) & Gold (Pantone 123)'' -- Pantone-only, no hex. Fell back to lmc.edu''s own CSS, which pervasively (108 occurrences) uses #005C42 in explicitly green-named classes and has a class literally named ''.gold { color: #cf9b2c; }''. Corrected candidate''s guessed green (#2A574A) and gold (#FCC01C); dropped candidate''s white.'
    ),
    (
      'wabash-college',
      '152673',
      array['#B7242E', '#FFFFFF']::text[],
      'https://sports.wabash.edu/index.aspx',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''Wabash College Athletics''). Its own site_colors JSON declares primary_background #b7242e, secondary_background #ffffff. No dedicated wabash.edu brand-guidelines page with a stated hex was found (searched). Corrected candidate''s guessed scarlet (#EC1C2C); dropped candidate''s peach/tan accent (#FDC9A1), not found on-domain.'
    ),
    (
      'wilson-college',
      '217013',
      array['#1C3F95']::text[],
      'https://wilsonphoenix.com/',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''Wilson College Athletics''). Its own site_colors JSON declares primary_background #1c3f95, secondary_background #999999 (gray, not chromatic). Web search corroborates ''blue, grey & white'' colors but no dedicated brand page with stated hex for gray/white was found. Corrected candidate''s guessed blue (#04428D); dropped candidate''s white and the non-chromatic gray.'
    ),
    (
      'presbyterian-college',
      '218539',
      array['#0033A0', '#9D2235', '#B2B4B3']::text[],
      'http://web.archive.org/web/20240726023335/https://www.presby.edu/doc/communications/BrandStandardsGuide.pdf',
      'high',
      'Live URL 404s; recovered the identical PDF via Wayback. ''PRIMARY COLORS: PC True Blue [Pantone 286] Hex: 0033A0, Tartan Red [Pantone 201] Hex: 9D2235, Rail Steel Gray [Pantone 421] Hex: B2B4B3'' -- three explicitly named primary colors, distinct from further Secondary/Accent groups. Corrected candidate''s guessed blue (#0060A9); red matched exactly; corrected candidate''s white to the document''s actual third primary color, Rail Steel Gray.'
    ),
    (
      'lake-erie-college',
      '203580',
      array['#153C2E', '#1A1919']::text[],
      'http://www.lakeeriestorm.com/',
      'medium',
      'Candidate''s cited PDF (branding_guide14.pdf) has never been captured as a real PDF by Wayback across roughly 30 crawls -- every snapshot is a small text/html 404-equivalent stub. Fell back to the live lakeeriestorm.com homepage (og:site_name: ''Lake Erie College''), whose site_colors JSON declares primary_background #153C2E (dark green), secondary_background #1A1919 (near-black), consistent with the Storm''s known green-and-black identity. Corrected candidate''s guessed green (#113D2A); replaced candidate''s white/pure-black with the site''s actual configured near-black secondary.'
    )
)
update public.institution_directory as d
set
  brand_colors = s.brand_colors,
  brand_colors_source = s.brand_colors_source,
  brand_colors_checked_at = date '2026-08-24',
  brand_colors_confidence = s.brand_colors_confidence,
  brand_colors_notes = s.brand_colors_notes
from seed s
where d.school_id = s.school_id
  and d.ipeds_id = s.ipeds_id;
