-- Batch 20 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a dropped
-- mechanically-attached white: macalester-college (blue/orange exact hex
-- match on the official color-palette page, "the two core Macalester
-- colors"; white dropped), university-of-redlands (maroon/grey exact hex
-- match on the official -- recovered via Wayback -- Brand Identity Style
-- Guide, "our official logo colors: maroon, grey, black and white"; kept
-- candidate's exact 3-of-4 selection), minot-state-university (green/red
-- RGB-derived exact match on the official 2023 Athletics Brand Guide's
-- "PRIMARY COLORS"; white kept, candidate's exact 3-of-4 selection).
--
-- Wrong-swatch / wrong-tier / stale corrections (candidate hex did not
-- match the school's own current official source):
-- missouri-western-state-university (candidate's white dropped -- the
-- current MoWest Brand Guide names exactly "black and gold" as its
-- identifying colors, no white anywhere on the page), clark-university
-- (candidate's third value was a "50% black tint" foil-stamping spec
-- #939598, not black itself; corrected to #000000, one of exactly three
-- named "Approved Logo Colors: Red, Black, White"), barry-university
-- (candidate's #9D1C1F is a third-party site's own admitted guess --
-- "these color values have not been given explicitly in the Barry
-- University brand guidelines" -- corrected via the official
-- gobarrybucs.com domain's on-domain site-color config to #AC1A2F, medium
-- confidence), concordia-university-wisconsin (mechanically-attached white
-- dropped -- the current 2023 style guide lists 6 "Wisconsin colors"
-- without primary/secondary labels; reduced to the two exact-hex chromatic
-- matches), clarkson-university (candidate's 2015-era hexes superseded by
-- the current official colors PDF's CORE COLORS; white kept, the guide
-- explicitly frames it as "a third primary color"), mercyhurst-university
-- (candidate hex unsupported -- the cited PSAC guide is a third-party
-- conference document giving only Pantone numbers with no hex/RGB;
-- corrected via the official hurstathletics.com domain's on-domain site
-- config, medium confidence), otterbein-university (candidate hex
-- unsupported -- no otterbein.edu brand page found; corrected via the
-- official otterbeincardinals.com domain's on-domain site config, medium
-- confidence), university-of-montevallo (gold hex corrected from #FFC423
-- to the current Branding Standards Guide's own literal "HEX" field
-- FFC425, despite the same document's RGB line mathematically converting
-- to FFC423 -- an internal inconsistency in the source; white dropped,
-- not part of the 2-color University Colors section), trinity-college
-- (candidate's older hexes superseded by the current 2022 Brand
-- Guidelines' "Primary Colors... Trinity Blue and Trinity Gold"; white
-- dropped), saint-peters-university (candidate's white replaced with the
-- document's actual second core color -- "Two-Color Logo only when...
-- Pantone 541 and Pantone 285" -- Navy #003C71 confirmed, Blue #0072CE
-- added), university-of-new-england (candidate's blue/black were rough
-- approximations and its white does not appear in the current Brand
-- Identity Manual's actual "PRIMARY Color Palette" of Black/Blue/Gray;
-- corrected to the exact stated hexes), salve-regina-university (navy hex
-- corrected; candidate's green was actually the Secondary palette's green,
-- not Primary -- corrected to the documented two "PRIMARY COLOR" swatches,
-- Navy + White), wheaton-college (IPEDS 149781 confirmed as Wheaton
-- College, Illinois; live wheaton.edu is fully Cloudflare-walled for both
-- curl and WebFetch, so the candidate's own cited 2020 Brand Style Guide
-- PDF was recovered via the Wayback Machine and text-extracted directly --
-- "Wheaton blue and Wheaton orange," hexes corrected from third-party
-- approximations to the document's literal values, white dropped),
-- shenandoah-university (hex precision corrected against the current June
-- 2024 Graphic Guide's "Primary Brand Colors"; white dropped -- it is a
-- Secondary "VIBRANT WHITE," not Primary), saint-anselm-college (candidate
-- hexes were approximations; corrected to the RGB explicitly stated in the
-- current Nov 2024 Guidelines for Licensees' "Color Standards"), carleton-
-- college (candidate hexes were approximations of the official colors;
-- corrected to the current Oct 2023 Identity Guidelines' literal HEX
-- values for "the official colors of Carleton College," blue and maize;
-- white dropped), valparaiso-university (candidate's third value was
-- actually the document's separate "Yellow" swatch, not "Gold" -- the
-- current Brand Tool Kit explicitly says "lead with brown and gold";
-- corrected to the real Gold hex, white dropped), williams-college
-- (candidate hexes were approximations; corrected via identity.williams.edu
-- to the current portal's literal Purple/Gold hexes, reduced from a
-- 4-color primary set to the 2 chromatic colors), south-dakota-school-of-
-- mines-and-technology (navy hex corrected against the current Brand
-- Guidelines' "University Colors"; white kept, one of exactly three named),
-- university-of-south-carolina-beaufort (one hex digit corrected via the
-- official uscbathletics.com domain's on-domain site-color config, medium
-- confidence), tiffin-university (confirmed via on-domain CSS custom
-- properties on the current /our-brand page -- whose own color swatches
-- are image-only and not text-extractable -- medium confidence), union-
-- college (hex corrected against the current Colors page; white dropped,
-- it does not appear anywhere on the page -- corrected to the co-listed
-- untagged primary, Gate Black).
--
-- Left null (no usable on-domain hex/RGB found after a documented search,
-- or a wrong-school citation with no recoverable replacement; see
-- data/brand-colors/batch-20-2026-08-24.jsonl for full per-school detail):
-- ashland-university (candidate PDF 404s, no public brand-guidelines page
-- or PDF found anywhere on ashland.edu or ashlandeagles.com),
-- state-technical-college-of-missouri (WRONG-SCHOOL FLAG: candidate's
-- citation is Missouri State University in Springfield, an unrelated
-- institution -- this school is State Technical College of Missouri in
-- Linn, formerly Linn State Technical College; its actual colors are Navy
-- and Silver per secondary sources, but no hex/RGB for either was found
-- anywhere on statetechmo.edu).
--
-- Every populated row was run through the production deriveInks()/
-- glyphInks() (web/src/lib/derive-inks.ts) via a throwaway vitest case
-- before finishing (deleted, not committed). All 28 populated rows produce
-- their own derived plates (house=false) -- no school in this batch loses
-- its chromatic primary to the house forest/ochre fallback, including the
-- single-chromatic-hex row (bellarmine-university) whose sole brand color
-- anchors both plates via the deriver's single-ink rule.
-- See data/brand-colors/batch-20-2026-08-24.jsonl for the full per-school
-- record, including the two null entries.

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
      'missouri-western-state-university',
      '178387',
      array['#000000','#FFC700']::text[],
      'https://www.missouriwestern.edu/brand/brand-guide/',
      'high',
      'Citation resolved and text-extracted cleanly. "Black and gold have long been MoWest''s identifying colors. Griffon Gold and Griffon Black should comprise the majority of color usage." RGB and Hex table gives Griffon Black HEX #000000, Griffon Gold HEX #ffc700 (matches candidate''s gold exactly). Candidate''s white dropped -- not a stated color anywhere on the page; the secondary/accent palette is Centennial Silver #aeb2b7, Kelley Commons Sky #54afcb, Fall Leaves #d97245, none of them white.'
    ),
    (
      'clark-university',
      '165334',
      array['#CC0000','#000000','#FFFFFF']::text[],
      'https://www.clarku.edu/marketing-communications/www-content/blogs.dir/3/files/sites/106/2019/08/CU-Style-Guide-v4-2018.pdf',
      'high',
      'Candidate''s www2.clarku.edu citation 404s/redirects to the marcom homepage; recovered the current Brand Identity Style Guide PDF from clarku.edu. "Approved Logo Colors: Red, Black, White." Specifying Clark Colors gives Red as PMS 186 / HEX #cc0000 (matches candidate exactly). Black and White have no separate literal hex line (only a ''50% black tint'' foil-stamping spec, HEX #939598, which is NOT black itself) but are two of exactly three named Approved Logo Colors, so kept as the trivial #000000/#FFFFFF. Candidate''s third value (#939598, actually the 50% black tint used for foil stamping, not one of the three named logo colors) corrected to black.'
    ),
    (
      'barry-university',
      '132471',
      array['#AC1A2F','#FFFFFF']::text[],
      'http://gobarrybucs.com/sports/2014/12/30/inside-athletics_quick-facts.aspx',
      'medium',
      'Candidate''s cited quick-facts URL now redirects to a generic Sidearm landing page, but the same gobarrybucs.com domain response embeds a Barry-specific site_colors config: primary_background #ac1a2f, primary_text #ffffff, secondary_background #ffffff, secondary_text #ac1a2f (page content elsewhere confirms 99 mentions of "Barry" and CSS keyed to .sidearm-mobile-site with the same #AC1A2F). No official barry.edu brand/identity page with literal hex was found (adco pages return generic nav only; bucwis.barry.edu brand guidelines PDF is login-walled). A third-party index (brandcolorcode.com) explicitly states its #9D1C1F value "has not been given explicitly in the Barry University brand guidelines... closest numbers based on the official color codes" -- i.e. an admitted guess, which is what the candidate hex traces back to. Corrected to the on-domain site-config red #AC1A2F + white; candidate''s black dropped, not present in the config (Wikipedia lists Barry''s colors as red/black/silver, but only red+white are evidenced on-domain).'
    ),
    (
      'concordia-university-wisconsin',
      '238616',
      array['#005596','#FAA634']::text[],
      'https://www.cuw.edu/facultystaff/_assets/CUW-Style-Guide-2023_web.pdf',
      'high',
      'Candidate''s 2018-dated PDF filename 404s; recovered the current (2023) combined Concordia Wisconsin/Ann Arbor style guide from the same cuw.edu domain. "Wisconsin colors" section lists 6 swatches without primary/secondary labels: Lake Blue HEX #005596 (matches candidate''s first value exactly), Sky Blue #90b9e2, Midnight Blue #002641, Sunrise Gold HEX #faa634 (matches candidate''s third value exactly), Sunset Gold #e89a30, Snowy White #ffffff. No text anywhere labels a tight 2-3 "primary" subset, so reduced to the two exact-hex chromatic matches; candidate''s mechanically-attached white dropped.'
    ),
    (
      'clarkson-university',
      '190044',
      array['#004E42','#FFCD00','#FFFFFF']::text[],
      'https://www.clarkson.edu/sites/default/files/2023-07/CU_brand%20colors.pdf',
      'high',
      'Candidate''s 2015 Brand Toolkit PDF 404s; recovered the current colors PDF linked from clarkson.edu/about/clarkson-brand. "CORE COLORS... CLARKSON GREEN HEX 004e42, CLARKSON GOLD HEX ffcd00." These are updated values vs. the candidate''s old 2015 hexes (#03522B/#FFD204) -- corrected. White kept: the document explicitly states "Think of white as a third primary color; white space in a design is important..." -- a direct textual statement naming white as one of exactly three primaries, matching the no-neutral-append exception.'
    ),
    (
      'mercyhurst-university',
      '213987',
      array['#1C4037','#002E5F']::text[],
      'https://hurstathletics.com/',
      'medium',
      'Candidate''s citation is the PSAC conference''s own "Official Brand Identity" PDF (a third-party/off-domain conference document, not Mercyhurst''s own), and its Mercyhurst-specific page only names Pantone 655 and Pantone 561 with no hex/RGB anywhere -- converting those to hex would be an off-domain Pantone-table guess, disallowed at medium confidence. mercyhurst.edu has no public brand-guide page found. The official hurstathletics.com domain''s own site config gives primary_background #1c4037 (forest green), secondary_background #002e5f (navy) -- on-domain CSS/JS evidence, medium confidence. Corrected from candidate''s #0F4F44/#171E3A to these on-domain values; white dropped (only primary_text, not a named brand color).'
    ),
    (
      'mount-holyoke-college',
      '166939',
      array['#203861','#7FBCE5']::text[],
      'https://athletics.mtholyoke.edu/landing/index',
      'medium',
      'Citation resolved. No literal "our colors are..." text found, but the page''s own theme-color meta tag and mask-icon color are #203861 (exact match to candidate''s first value), and the site''s own stylesheet (styles.css on the same domain) uses #203861 as the dominant background/button color and #7fbce5/#7fbde8 (matching candidate''s third value almost exactly) as its paired accent border color throughout. On-domain CSS corroboration, not a printed statement -- medium confidence. Candidate''s white middle value dropped, not evidenced as a distinct named color.'
    ),
    (
      'susquehanna-university',
      '216278',
      array['#651C32','#FF6A14','#C1C6C8']::text[],
      'https://www.susqu.edu/wp-content/uploads/2025/04/River-Hawks-Brand-Guide.pdf',
      'high',
      'Candidate''s live.files citation 403s; recovered the current River Hawks Brand Guide from susqu.edu (same content also mirrored at suriverhawks.com). "color PALETTE" section states exactly three colors: SUSQUEHANNA maroon HTML 651C32 (matches candidate exactly), SUSQUEHANNA orange HTML FF6A14 (matches candidate exactly), RIVER HAWK grey HTML C1C6C8. Candidate''s white middle value corrected to grey -- the document''s actual third stated color is grey, not white; white does not appear in the color PALETTE section at all.'
    ),
    (
      'bellarmine-university',
      '156286',
      array['#752936']::text[],
      'https://www.bellarmine.edu/university-communication/brand-standard/university-colors.php',
      'high',
      'Candidate''s 2016 S3 athletics PDF 404s; found the current official University Colors page on bellarmine.edu. "Scarlet & Silver -- Bellarmine''s primary color is scarlet... HEX: #752936" (does not match candidate''s #660000, corrected). "Bellarmine''s secondary color is silver," represented by FOUR different tint options (30% grey #b3b3b3, 60% grey #808080, 80% grey #4d4d4d, White #ffffff) with no single canonical "the" silver hex -- rather than guess which grey tint or white belongs, reduced to the one unambiguous, directly-stated chromatic primary.'
    ),
    (
      'otterbein-university',
      '204936',
      array['#990000','#D5C296']::text[],
      'https://otterbeincardinals.com/',
      'medium',
      'Candidate citation was only the athletics homepage with no stated hex ("other" tier). No otterbein.edu brand/identity page with literal hex was found (site: search only returned handbooks). The otterbeincardinals.com domain''s own site config gives primary_background #990000, secondary_background #d5c296 (also set as the page''s theme-color meta) -- on-domain CSS/JS evidence, medium confidence. Corrected from candidate''s #E21B23/#CA9E5A (third-party team-color-code values) to these on-domain values.'
    ),
    (
      'university-of-montevallo',
      '101709',
      array['#49176D','#FFC425']::text[],
      'https://www.montevallo.edu/wp-content/uploads/2024/10/24brandingStandardsFINAL_ADA.pdf',
      'high',
      'Candidate''s 2014 assets-folder PDF 404s; recovered the current (revised August 2024) Branding Standards Guide from montevallo.edu. "University Colors" table gives HEX 49176D (purple, matches candidate exactly) and HEX FFC425 (gold). Note: the document''s own RGB line for gold (R255 G196 B35) mathematically converts to #FFC423, one digit off from its own printed "HEX FFC425" line -- an internal inconsistency in the source PDF; used the literal labeled HEX field per the brief''s instruction to store what the school publishes. White dropped -- not part of the 2-color University Colors section (only mentioned for a separate 1-color logo variant).'
    ),
    (
      'trinity-college',
      '130590',
      array['#004179','#F3C404']::text[],
      'https://www.trincoll.edu/branding/wp-content/uploads/sites/140/2022/08/Trinity-College-Brand-Guidelines-2022-1.pdf',
      'high',
      'Candidate''s 2013 AboutTrinity citation 404s; recovered the current (rev. 10/5/22) Brand Guidelines PDF via trincoll.edu/branding/. "Primary Colors -- Our primary palette consists of Trinity Blue and Trinity Gold... Trinity Blue PMS 541 C, HEX 004179; Trinity Gold PMS 7406 C, HEX F3C404." These supersede candidate''s older values (#00305C/#F7D117) -- corrected. White dropped, not part of the 2-color Primary Colors statement.'
    ),
    (
      'saint-peters-university',
      '186432',
      array['#003C71','#0072CE']::text[],
      'https://www.saintpeters.edu/wp-content/uploads/blogs.dir/98/files/2013/01/brand.pdf',
      'high',
      'Candidate''s S3 athletics-guidelines citation 404s; recovered the official Brand Standards PDF from saintpeters.edu. Document states the Two-Color Logo "only when a two-color printed piece prints using Pantone 541 and Pantone 285" -- these are the university''s own-declared two core logo colors. Digital section: Pantone 541 RGB 0/60/113, HEX #003C71 (matches candidate''s first value exactly); Pantone 285 RGB 0/114/206, HEX #0072CE. A broader 5-color "Primary color palette" also exists (541, Black, 285, 390, Warm Gray 6) for general communications, but the narrower, logo-specific two-color statement was used. Candidate''s white dropped -- white does not appear in either the Two-Color Logo spec or the 5-color Primary palette.'
    ),
    (
      'university-of-new-england',
      '161457',
      array['#163E70','#231F20','#9FA1A4']::text[],
      'https://www.une.edu/sites/default/files/2025-04/Communications_INSTITUTIONALBrandIdentityManual_04052025.pdf',
      'high',
      'Candidate''s 2019-dated une.edu PDF 404s; recovered the current (April 2025) Institutional Brand Identity Manual from the same domain. "PRIMARY Color Palette" gives exactly three swatches: Black HEX #231f20, Pantone 294 (Navy) HEX #163e70, Pantone 423 (Gray) HEX #9fa1a4. This corrects candidate''s blue and black (#003882/#000000, both approximations) and its white (which is not present in the actual Primary palette -- Gray is the third color, not white).'
    ),
    (
      'macalester-college',
      '173902',
      array['#01426A','#D44420']::text[],
      'https://www.macalester.edu/communications/visual-identity/colors/',
      'high',
      'Citation resolved and text-extracted cleanly. "The primary color palette consists of the two core Macalester colors MAC Blue (PMS 7694 C) and MAC Orange (PMS 1665 C) along with black, white and two gray values." Text table: Mac Blue HEX: 01426A (matches candidate exactly), Mac Orange HEX: D44420 (matches candidate exactly). Candidate''s white dropped -- the page explicitly frames Blue+Orange as "the two core colors," with black/white/two grays being additional neutrals in the wider primary palette, not core.'
    ),
    (
      'salve-regina-university',
      '217536',
      array['#002D58','#FFFFFF']::text[],
      'https://salve.edu/documents/marketing-and-communications-brand-guide',
      'high',
      'Candidate''s salve.edu/document/branding-guide citation 404s; recovered the current (2025) Brand Guidelines PDF from salve.edu. "PRIMARY COLOR" section shows exactly two labeled swatches: Pantone 295 HEX #002D58 and a second "PRIMARY COLOR" swatch, White HEX #ffffff. Corrected candidate''s navy (#00447C, does not match) and dropped candidate''s green (#005D55, which is close to but does not exactly match the document''s actual Secondary green #009457 -- and Secondary colors are not Primary). White kept, explicitly one of exactly two labeled PRIMARY COLOR swatches.'
    ),
    (
      'wheaton-college',
      '149781',
      array['#002856','#D25F15']::text[],
      'https://www.wheaton.edu/media/marcomm/brand-2020/20CCA034WheatonBrandStyleGuide-(2).pdf',
      'high',
      'IPEDS 149781 confirmed as Wheaton College, Illinois (not Wheaton College MA). The live wheaton.edu domain is fully Cloudflare-walled (curl and WebFetch both returned 403/"Just a moment..." for every URL tried, including a newer 2024 style guide found via search); retrieved an archived copy of the candidate''s own cited 2020 Brand Style Guide PDF via the Wayback Machine instead and text-extracted it directly. "Our primary brand palette is composed of two colors: Wheaton blue and Wheaton orange." Blue HEX #002856, Orange HEX #D25F15 -- both differ slightly from candidate''s #00447C/#D15E14 (which were third-party approximations); corrected to the archived official PDF''s literal values. White dropped, not part of the stated two-color primary palette.'
    ),
    (
      'shenandoah-university',
      '233541',
      array['#98002E','#002D62']::text[],
      'https://www.su.edu/wp-content/uploads/2025/06/Graphic-Guide_JUNE_2024.pdf',
      'high',
      'Candidate''s 2021-dated su.edu PDF 404s; recovered the current (June 2024) Graphic Guide from the same domain. "Primary Brand Colors -- UNIVERSITY RED PMS 202, RGB 152/0/46, Hex #98002E; UNIVERSITY BLUE PMS 282, RGB 0/45/98, Hex #002D62." Corrects candidate''s slightly-off hexes (#98012D/#002C62, third-party rounding drift). White dropped -- it appears only in the document''s separate "Secondary Brand Colors" section as "VIBRANT WHITE," not among the two named Primary Brand Colors.'
    ),
    (
      'saint-anselm-college',
      '183239',
      array['#193E5F','#FFFFFF','#7C8795']::text[],
      'https://static1.squarespace.com/static/567445f957eb8dfe033bbc42/t/672e63a788ca780eb68f4a08/1731093416385/Saint+Anselm_Brand+Guide+-+Nov+2024.pdf',
      'high',
      'Candidate''s anselm.edu Online-Style-Guide citation 404s/redirects to homepage; recovered the current (Nov 2024) Guidelines for Licensees PDF, administered jointly by the College and Athletics. "Color Standards: Deep Blue (Pantone 289) RGB 25/62/95; White; Athletic Grey (Pantone 430) RGB 124/135/149." No literal hex text, but RGB is explicitly stated for both chromatic colors, which counts as directly sourced -- RGB(25,62,95)=#193E5F and RGB(124,135,149)=#7C8795, correcting candidate''s approximated #143E5F/#CCD6DC. White kept, explicitly one of the three named Color Standards.'
    ),
    (
      'carleton-college',
      '173258',
      array['#003069','#FFD24F']::text[],
      'https://carleton-wp-production.s3.amazonaws.com/uploads/sites/158/2024/04/Carleton_StyleGuide_October-2023.pdf',
      'high',
      'Candidate''s apps.carleton.edu citation is now behind a reCAPTCHA wall; recovered the current (Oct 2023) Identity Guidelines from Carleton''s own S3-hosted production bucket. "The official colors of Carleton College are blue and maize... should be the primary colors used in all college-wide communications." PMS 294 Blue HEX 003069, PMS 120 Maize HEX FFD24F. Both differ from candidate''s #0B5091/#F3B61D (third-party approximations); corrected. Candidate''s white dropped, not part of the stated 2-color official palette.'
    ),
    (
      'valparaiso-university',
      '152600',
      array['#5C3000','#F5B80A']::text[],
      'https://www.valpo.edu/about/marcom/brand/brand-tool-kit/color-palettes/',
      'high',
      'Candidate''s citation URL redirects/403s; live valpo.edu also 403s for curl/WebFetch, so retrieved a Wayback Machine snapshot of the correct current URL path (valpo.edu/about/marcom/brand/brand-tool-kit/color-palettes/) and text-extracted it. "Primary Colors -- Our primary color palette, anchored in rich browns and radiant golds... Lead with brown and gold as your foundation." Table: Brown HEX 5C3000 (matches candidate exactly), Gold HEX F5B80A. Candidate''s third value #FFE300 is actually the document''s separate "Yellow" swatch, not "Gold" -- the guide explicitly names brown+gold (not brown+yellow) as the foundation pair; corrected. White dropped per the guide''s own framing ("allow designs to breathe with plenty of white space" -- descriptive, not a listed ink).'
    ),
    (
      'williams-college',
      '168342',
      array['#500082','#FFBE0A']::text[],
      'https://identity.williams.edu/',
      'high',
      'Candidate''s vp-finance.williams.edu citation is Cloudflare-walled (403 "Just a moment..."); found the official brand portal at identity.williams.edu instead, which text-extracted cleanly. Primary palette "made up of four colors": Purple HEX #500082, Gold HEX #FFBE0A, Black HEX #000000, White HEX #FFFFFF. Corrects candidate''s #512698/#FDCC09 (third-party approximations). Reduced to the two chromatic colors (Purple + Gold) per the brief''s when-in-doubt preference, since the palette is four colors rather than a tight 2-3 primary set; Purple alone is historically Williams'' sole official college color, with Gold added to differentiate from Amherst.'
    ),
    (
      'south-dakota-school-of-mines-and-technology',
      '219347',
      array['#002554','#B3A369','#FFFFFF']::text[],
      'https://brand.sdsmt.edu/visual-design/colors/',
      'high',
      'Candidate''s sdsmt.edu/Campus-Services citation 404s; recovered the current South Dakota Mines Brand Guidelines site at brand.sdsmt.edu. "University Colors" section lists exactly three: Mines Navy HEX #002554, Mines Old Gold HEX #B3A369 (matches candidate exactly), White HEX #FFFFFF. Candidate''s navy (#071D49) corrected to the stated #002554. White kept, explicitly one of exactly three named University Colors.'
    ),
    (
      'minot-state-university',
      '200253',
      array['#006242','#CF102D','#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/minotstate.sidearmsports.com/documents/2023/1/24/2023_Athletics_Brand_Guide.pdf',
      'high',
      'Citation resolved and text-extracted cleanly. "PRIMARY COLORS -- These four colors are the primary colors for Minot State Athletics": Pantone 186 RGB 207/16/45 (=#CF102D), Pantone 3425 RGB 0/98/66 (=#006242), Black, White. No literal hex text, but RGB is explicitly stated for each, counting as directly sourced; matches candidate''s green and red exactly. Reduced from the document''s 4 named primaries to the same 3 candidate already selected (green, red, white), dropping black to stay within the 3-hex max.'
    ),
    (
      'university-of-south-carolina-beaufort',
      '218654',
      array['#002D62','#E0C298']::text[],
      'https://uscbathletics.com/news/2022/8/9/general-usc-beaufort-alters-athletic-marks.aspx',
      'medium',
      'Citation resolved. The article text itself only says garnet was dropped as tertiary color in favor of "light blue" (no hex given), but the same uscbathletics.com page response embeds a USCB-specific site_colors config: primary_background #002d62 (matches candidate exactly), primary_text #ffffff, secondary_background #e0c298, secondary_text #002d62 -- on-domain CSS/JS evidence, medium confidence. Corrected candidate''s third value from #E0C398 to the config''s actual #E0C298 (one hex digit off in the candidate). White dropped, only present as primary_text metadata, not a named brand color.'
    ),
    (
      'tiffin-university',
      '206048',
      array['#154734','#DAAA00']::text[],
      'https://www.tiffin.edu/about/offices-departments/communications-public-relations/our-brand/',
      'medium',
      'Candidate''s citation path is stale (marketing-communications rather than the current communications-public-relations office); the current page loaded but its color swatches are an image only (tu_color_pallette.png), not extractable text -- per policy, not eyedropped. Retrieved the page via Wayback Machine instead and confirmed the same domain''s own CSS custom properties: --wp--preset--color--green:#154734 and --wp--preset--color--yellow:#daaa00, used pervasively throughout the live site''s navigation, headers, and buttons (not generic WordPress-preset noise) -- matches candidate''s green and gold exactly. On-domain CSS corroboration rather than printed swatch text, so medium confidence.'
    ),
    (
      'university-of-redlands',
      '121691',
      array['#7A2426','#FFFFFF','#666666']::text[],
      'https://sites.redlands.edu/globalassets/sites/university-communications/creative/ur-brand-identity-style-guide.pdf',
      'high',
      'Candidate''s live citation now 404s (also tried a redlands.edu/contentassets mirror, also 404); retrieved the same original file via a Wayback Machine snapshot and text-extracted it directly. "INSTITUTIONAL COLORS" table: PMS 1815C Maroon HEX 7A2426 (matches candidate exactly), PMS Cool Grey 10C HEX 666666 (matches candidate exactly), Black HEX 202121, White HEX FFFFFF. Later text: "our official logo colors: maroon, grey, black and white." Confirmed candidate''s exact selection (maroon, white, grey) of 3 of the 4 named official logo colors, dropping black to stay within the 3-hex max, matching the school''s own stated set.'
    ),
    (
      'union-college',
      '196866',
      array['#762334','#000000']::text[],
      'https://www.union.edu/communications/style-guide/colors',
      'high',
      'Candidate''s union.edu/offices/communications citation 404s (path restructured); recovered the current Colors page at union.edu/communications/style-guide/colors, which text-extracted cleanly. "Primary Colors -- Union Garnet: Pantone 202 (Print) / Pantone 7421 (Apparel), RGB 118/35/52, HEX #762334" (candidate''s #822433 corrected). Listed alongside without an "(Accent Color)" tag: Gate Black HEX #000000, Ramée Gray HEX #636569; two further garnet tints (Light/Dark) are explicitly tagged "(Accent Color)" and excluded. White is NOT present anywhere on this page -- candidate''s white was a mechanically-attached Wikipedia value with no basis on the official page; dropped in favor of the co-listed untagged primary, Gate Black.'
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
