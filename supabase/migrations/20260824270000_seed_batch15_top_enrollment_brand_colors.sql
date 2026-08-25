-- Batch 15 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given (all three chromatic/near-white
-- values matched the real official source, or the source explicitly names
-- all given values as one labeled Primary set): university-of-hartford,
-- seattle-university (current one-sheeter replacing a dead PDF link),
-- the-university-of-texas-permian-basin (image-based color chart, viewed
-- directly), university-of-nebraska-at-kearney (dropping a fabricated
-- white), shippensburg-university-of-pennsylvania (dropping a fabricated
-- white), university-of-south-carolina-upstate (dropping a fabricated
-- white).
--
-- Wrong-swatch / wrong-tier catches (candidate hex did not match the
-- school's own official source, or matched the wrong section of the right
-- page): samford-university (candidate's red was a near-miss; corrected
-- white to the real third Primary color, Gray), university-of-wisconsin-
-- river-falls (red corrected), midwestern-state-university (maroon
-- corrected, domain moved to msutexas.edu), worcester-state-university
-- (blue and yellow both corrected against a 2024-revision guide), merrimack-
-- college (gold corrected against a 2025-revision guide), pratt-institute-
-- main (yellow corrected; used the institute-wide guide since the athletics
-- citation had no style-guide PDF at all), bucknell (orange corrected),
-- loyola-university-maryland (candidate had swapped White into the palette
-- in place of the real second Primary color, Hounds Grey), thomas-jefferson-
-- university (both blues nudged to a corroborated secondary source),
-- wentworth-institute-of-technology (gold corrected; candidate's red did
-- not match anything in the Primary palette -- it is closer to a different-
-- valued Secondary "Ruby Red"), monmouth-university (blue corrected;
-- candidate's gray was wrong-tier, not part of the labeled Primary
-- blue+white pair), clark-atlanta-university (candidate had fabricated a
-- white/black pair; the page's own "Color Guides" line names only Red and
-- Grey with explicit hex), bradley-university (candidate had fabricated a
-- white/black pair; the real second official color is Kaboom Gray),
-- university-of-scranton (hex is a standard Pantone-269 conversion since
-- the source states Pantone only; corrected away from both the candidate's
-- guess and an off-Pantone secondary-source guess; dropped black, which is
-- not part of the document's explicit "purple and white" statement).
--
-- Fabricated-neutral / wrong-tier-neutral catches (candidate white/black/
-- gray had no support in the real source, or belonged to a different tier,
-- and was dropped or replaced): eastern-illinois-university,
-- winston-salem-state-university, united-states-air-force-academy
-- (Silver is explicitly Secondary, not Primary), shippensburg-university-
-- of-pennsylvania, university-of-south-carolina-upstate, roger-williams-
-- university (candidate's white/gold were both wrong-tier; real Primary
-- pair is Navy+Light Blue).
--
-- Dead-link / access-blocked recoveries (original citation 404/403'd, or
-- rendered nothing extractable; found the school's current official page,
-- a same-domain PDF, or a Wayback Machine capture instead):
-- university-of-wisconsin-river-falls (Wayback), winston-salem-state-
-- university, midwestern-state-university (domain moved to msutexas.edu),
-- seattle-university, university-of-south-carolina-upstate (Wayback),
-- roger-williams-university, worcester-state-university, merrimack-college,
-- the-university-of-texas-permian-basin, monmouth-university,
-- united-states-air-force-academy (Wayback), bucknell (Wayback),
-- clark-atlanta-university (still live), bradley-university.
--
-- Low/medium confidence flags (official primary source could not be
-- directly read, or hex was not itself stated in an otherwise-confirmed
-- official document): eastern-illinois-university and lewis-university
-- (both have official color pages that name Pantone/colors but render or
-- state no hex on-domain; used reputable secondary indices at low
-- confidence). grambling-state-university is low -- two separate official
-- gram.edu PDFs both give only Pantone/Madeira/RA, never a literal hex;
-- corroborated via a secondary index. roger-williams-university and
-- westfield-state-university are medium -- the official PDF gives only
-- Pantone/CMYK (RWU) or could not be downloaded intact despite a 200
-- status (Westfield, byte-truncated on every attempt); both corroborated
-- via a secondary index whose CMYK/Pantone matched the real official
-- document. suny-college-at-plattsburgh is medium -- plattsburgh.edu
-- blocks automated fetches; used a secondary index with SUNY-Plattsburgh-
-- specific internal color names (Hawkins Tower, Snow Goose, Cardinal)
-- strongly indicating direct sourcing from the real guide.
-- thomas-jefferson-university and university-of-mary-washington are low --
-- no on-domain hex found (Jefferson's athletics site has no style guide;
-- Mary Washington's brand toolkit is login-gated); both used
-- teamcolorcodes.com. university-of-scranton is medium -- the official
-- document states only a Pantone number, no hex; used a standard Pantone-
-- to-hex conversion. vermont-state-university is low and a genuinely
-- unusual case: the candidate cites the pre-2023 Castleton State College
-- (a predecessor institution merged out of existence in the 2023 VSU
-- unification), so the candidate hex is for a defunct brand entirely; no
-- current official VSU brand guide could be found, so a single red was
-- taken from vermontstate.edu's own named CSS custom properties
-- (--wp--preset--color--sunset, used functionally as the site's
-- interactive color) and a plausible-but-unconfirmable green was
-- deliberately left out rather than guessed. Flagging for human follow-up
-- once Vermont State University publishes an actual brand guide.
--
-- Ran every final hex list through production deriveInks()/glyphInks()
-- (web/src/lib/derive-inks.ts) via a throwaway vitest test file (deleted
-- before finishing). Every one of the 30 rows produced its own derived
-- plates (house=false) -- no school in this batch lost its chromatic
-- primary to the house forest/ochre fallback. See
-- data/brand-colors/batch-15-2026-08-24.jsonl for the full per-school
-- record.

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
      'samford-university',
      '102049',
      array['#0C2340','#BD1F2D','#C1C6C8']::text[],
      'https://www.samford.edu/departments/files/Marketing/Samford-Brand-Standards.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. Primary color palette: ''Samford''s school colors are navy, red and gray'' -- Navy PANTONE 289 HEX #0C2340, Red PANTONE 200 HEX #BD1F2D, Gray PANTONE 428 HEX #C1C6C8. Candidate''s navy matched exactly but its red (#BA0C2F) does not match anything in the doc -- corrected to the actual stated #BD1F2D. Corrected candidate''s fabricated white to the real third Primary color, Gray #C1C6C8 (white is not listed anywhere in the Primary or Secondary palettes).'
    ),
    (
      'university-of-wisconsin-river-falls',
      '240471',
      array['#BE0F34','#FFFFFF','#000000']::text[],
      'https://www.uwrf.edu/UCM/upload/5262_UWRF_GraphicsGuideFINAL.pdf',
      'medium',
      'Candidate URL now redirects to a generic students.uwrf.edu page (dead on live uwrf.edu); recovered the original PDF via Wayback Machine (web.archive.org, captured from this same uwrf.edu path). Graphics colors page: ''Primary Colors'' swatches are UWRF Red (Pantone 200, HEX be0f34) and White (HEX fffff, i.e. FFFFFF); Black is shown as a separate ''Secondary Colors'' swatch, but the accompanying prose states ''The three signature colors that comprise UW-River Falls'' identity within the registered marks are UWRF Red, White and Black'' -- treated all three as the real published set per that explicit statement. Corrected candidate''s red (#C80F2E, no match in doc) to the actual #BE0F34; confirmed white and black. Medium confidence because the source PDF is no longer live on uwrf.edu (only recoverable via Wayback) and a live successor page with the same content could not be found despite searching.'
    ),
    (
      'eastern-illinois-university',
      '144892',
      array['#004C97','#75787B']::text[],
      'https://www.brandcolorcode.com/eastern-illinois-university',
      'low',
      'Candidate URL (eiu.edu/marcom/branding.php) loads but its entire color content is rendered client-side through an embedded third-party brand-asset tool (Pickit, app.pickit.com) with no server-rendered text and no discoverable public read API -- confirmed by inspecting the page HTML, the Pickit embed, and its JS bundle; genuinely not text-extractable. Fell back to a reputable secondary index (brandcolorcode.com), which states ''Blue (#004C97), Gray (#75787B)'' as EIU''s 2 primary colors -- Blue matches the candidate exactly and Gray matches the candidate''s third value exactly. Dropped candidate''s white, which this source does not list at all (only 2 primary colors named). Low confidence: no official on-domain hex could be independently confirmed.'
    ),
    (
      'winston-salem-state-university',
      '199999',
      array['#C8102E','#FFFFFF']::text[],
      'https://www.wssu.edu/about/chancellors-office/division-of-strategic-communications/oimc/university-branding/_files/documents/wssu-brand-style-guide.pdf',
      'high',
      'Candidate PDF path (rev2, under the old chancellors-office/oimc path) 404s; found the current brand style guide at a live sibling path on the same domain. PDF loads and pdftotext''d cleanly: ''Primary'' Color Palette section shows exactly two swatches -- PMS 186 HEX #c8102e and PMS White HEX FFFFF (i.e. FFFFFF) -- confirming candidate''s red and white exactly. A separate ''Secondary'' section lists five more colors including Black (HEX 000000); corrected by dropping candidate''s black since the document''s own Primary/Secondary split places it outside Primary.'
    ),
    (
      'grambling-state-university',
      '159009',
      array['#EAA921','#000000','#FFFFFF']::text[],
      'https://www.gram.edu/aboutus/administration/advancement/licensing/docs/grambling_marks_07-14-21.pdf',
      'low',
      'PDF is image-based (an IMG College Licensing colors card); downloaded and viewed it directly (pdftotext yields nothing). It shows four color cards -- Gold (PANTONE 124C), Black (PANTONE Process Black C), White, and Red (explicitly labeled ''Accent Only'') -- giving Pantone/Madeira/RA values but no literal hex anywhere. A second official gram.edu PDF (GSU Style Guide.pdf, same licensing series) is identical in structure and also gives no hex. Corroborated the hex for Gold and Black via teamcolorcodes.com (''Grambling Tigers primary colors are gold and black'' -- Gold Hex #eaa921, Black Hex #000000), which matches the same Pantone 124/Process-Black-family values as the official cards. White is real (explicitly one of only 3 non-accent color cards, not a mechanical append) but carries no distinct hex beyond FFFFFF -- Pantone has no white reference, same pattern seen at other schools. Dropped candidate''s ordering slightly (gold leads both official cards) and dropped Red, which the official document explicitly demotes to ''Accent Only,'' not part of the primary/institutional trio. Low confidence: hex itself is not stated on the official document, only corroborated off-domain.'
    ),
    (
      'university-of-hartford',
      '129525',
      array['#DA1A32','#FFFFFF','#000000']::text[],
      'https://issuu.com/universityofhartford/docs/uhart_brandguide_web',
      'high',
      'Issuu''s reader is JS-rendered, but its page images are directly fetchable (reader3 JSON manifest -> per-page JPGs); downloaded and viewed the printed page 39 (''Primary Palette'') directly rather than trusting any auto-summary. It states: ''Our primary palette consists of UHart Red, white, and black'' with explicit swatches -- UHart Red HEX DA1A32, White HEX FFFFFF, Black HEX 000000. Candidate matches exactly; confirmed as-is with no corrections.'
    ),
    (
      'united-states-air-force-academy',
      '128328',
      array['#003594','#FFFFFF']::text[],
      'https://s3.amazonaws.com/goairforcefalcons.com/documents/2022/3/12/AF_Athletics_Style_Sheet.pdf',
      'high',
      'S3 PDF 403s directly; recovered via Wayback Machine capture of the same URL. PDF loads and pdftotext''d cleanly: color palette is explicitly tiered -- PRIMARY: Academy Blue HEX 003594 and Academy White HEX FFFFFF; SECONDARY: Academy Silver HEX B2B4B2; TERTIARY: Academy Dark Blue HEX 002554. Candidate''s blue and white match the stated PRIMARY tier exactly. Dropped candidate''s silver/gray, which the document explicitly places in the SECONDARY tier, not Primary.'
    ),
    (
      'university-of-nebraska-at-kearney',
      '181215',
      array['#004D86','#E4A115']::text[],
      'https://www.unk.edu/ccr/marketing-advertising/branding-and-identity-marks/color-specifications.php',
      'high',
      'Page loads and states plainly: Primary Color = Pantone 294, HTML #004D86; Secondary Color = Pantone 131, HTML #E4A115. No white or any other color is named anywhere on the page. Candidate''s blue and gold match exactly; dropped candidate''s fabricated white, which has no support on this page.'
    ),
    (
      'midwestern-state-university',
      '226833',
      array['#840028','#EAAC00']::text[],
      'https://msutexas.edu/web-guidelines/graphic-standards.php',
      'high',
      'Candidate mwsu.edu URL 404s -- the institution''s domain moved to msutexas.edu. Found the current Graphic Standards page there: ''Maroon and Gold are the official colors of MSU Texas... MSU Texas Maroon #840028, MSU Texas Gold #EAAC00,'' plus separately labeled ''complementary shades of gray'' (#737373, #9CA3AF, #F5F5F5, #333333) used only for web templates, not core colors. Corrected candidate''s maroon (#862633, no match) to the real #840028 and gold (#EAAA00) to the real #EAAC00; dropped candidate''s fabricated white, which is not listed as an official or complementary color anywhere on the page.'
    ),
    (
      'shippensburg-university-of-pennsylvania',
      '216010',
      array['#EE373D','#001541']::text[],
      'https://www.ship.edu/globalassets/marketing/su_identityguide.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. ''The official colors of Shippensburg University are: red (PMS 185) and navy blue (PMS 289)'' -- Primary Colors swatch table gives exactly two hex values, red EE373D and navy 001541, with no white swatch in either the Primary or Secondary Colors sections. Candidate''s navy and red both matched exactly; dropped candidate''s fabricated white, which the identity guide''s own ''official colors'' sentence explicitly limits to just the two.'
    ),
    (
      'seattle-university',
      '236595',
      array['#AA0000','#FFFFFF','#000000']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/goseattleu.com/documents/2025/4/29/Seattle_U_Athletics_One_Sheeter.pdf',
      'high',
      'Candidate goseattleu.com/fls/... PDF path 404s; found the current ''Brand Guide One Sheeter'' via a live goseattleu.com/brand-guidelines page and pdftotext''d it cleanly. Its ''Color Scheme'' section states ''Our primary color is our most significant identifier... SU Red CMYK: 3-100-70-12 / RGB: 170-0-0 / HEX: #AA0000'' followed immediately by White (HEX FFFFFF) and Black (HEX 000000) with real stated hex for each (Grey is given only as tint percentages, no hex, and was excluded). Confirmed candidate exactly as-is; all three values have real on-domain stated hex.'
    ),
    (
      'university-of-south-carolina-upstate',
      '218742',
      array['#00833E','#000000']::text[],
      'https://s3.amazonaws.com/upstatespartans.com/documents/2021/4/26/_4_21_BrandStandardsGuide_PAGES.pdf',
      'high',
      'S3 PDF 403s directly; recovered via Wayback Machine capture of the same URL. PDF loads and pdftotext''d cleanly: ''PRIMARY COLORS'' section shows exactly two swatches -- Upstate Green (PMS 348, Hex 00833e) and Black (Hex 00000, i.e. 000000). A separate ''SECONDARY COLORS'' section lists three grays (Slate Gray, Gray, Cool Gray); no white swatch appears in either section (a design tip says ''begin with white'' but white is never itemized as a palette color). Confirmed candidate''s green and black exactly; dropped candidate''s fabricated white.'
    ),
    (
      'lewis-university',
      '146612',
      array['#C22033','#000000']::text[],
      'https://www.brandcolorcode.com/lewis-university',
      'low',
      'Candidate lewisu.edu PDF (Part1_GraphicsGuide.pdf) 404s. Checked several current lewisu.edu graphics-standards pages (university logo usage, administrative materials, mascot) -- all consistently state the official colors are ''Lewis burgundy (PMS 202)'' and black, but none of them give a literal hex anywhere, only Pantone. The candidate''s red (#ED174D) is a bright magenta-red that does not match Lewis Burgundy at all -- it appears to actually be from Lewis Athletics'' 2023 rebrand red (PMS 199/192C, per news coverage of the new Flyers identity), a different, newer color family than the university''s institutional PMS 202 burgundy the cited PDF was about. Used a reputable secondary index (brandcolorcode.com) for the PMS 202 hex conversion: Burgundy #C22033, Black #000000. Dropped candidate''s fabricated white, which is not named as an official color anywhere. Low confidence: hex not stated anywhere on lewisu.edu itself.'
    ),
    (
      'roger-williams-university',
      '217518',
      array['#003865','#A4C8E1']::text[],
      'https://www.rwu.edu/sites/default/files/downloads/marcomm/rwustandards_facultystudents052314.pdf',
      'medium',
      'Candidate URL (rwu.edu/.../logo-and-guidelines) 403s; found RWU''s official Graphic Standards PDF instead, which pdftotext''d cleanly. It shows a ''Primary Colors'' section with exactly two swatches -- PANTONE 2955 (CMYK 100/60/10/53) and PANTONE 543 (CMYK 41/11/0/0) -- and a separate ''Secondary Colors'' section with one swatch, PANTONE 124 (gold). The PDF gives no literal hex, only Pantone/CMYK. Cross-referenced brandcolorcode.com, whose Navy CMYK (100,60,10,53) matches the official PDF''s Primary Navy exactly, giving Navy #003865 and Light Blue #A4C8E1 (Pantone 543) -- used these as the two real Primary colors. Corrected candidate''s navy (#003D6E, no match) and dropped candidate''s white (not a swatch in either section) and gold (explicitly Secondary, not Primary), replacing gold with the actual second Primary color, Light Blue. Medium confidence: hex itself corroborated off-domain rather than stated directly in the official PDF.'
    ),
    (
      'worcester-state-university',
      '168430',
      array['#003087','#FFFFFF','#FFB81C']::text[],
      'https://webcdn.worcester.edu/wp-content/uploads/2024/06/2024_SummerRev_Worcester-State-University-Visual-Identity-Guidelines.pdf',
      'high',
      'Candidate DownloadAsset.aspx URL 404s; found the current (Summer 2024 revision) Visual Identity Guidelines PDF and pdftotext''d it cleanly. ''PRIMARY COLORS'' section states plainly: ''Worcester State''s primary brand colors are blue, white, and yellow'' with named swatches -- Woo State Blue HEX #003087, Snow Day White HEX #FFFFFF, Lancer Yellow HEX #FFB81C -- all three explicitly the labeled Primary trio, not a mechanical append. Corrected candidate''s blue (#003896, near-miss) and yellow (#F0E07D, a pale color far from the actual vivid Lancer Yellow); white confirmed exact.'
    ),
    (
      'merrimack-college',
      '166850',
      array['#003767','#FFDD00']::text[],
      'https://www.merrimack.edu/wp-content/uploads/visual-identity-guidelinespdf.pdf',
      'high',
      'Candidate live-files URL 403s; found the current ''UPDATED 2025'' Visual Identity Guidelines PDF and pdftotext''d it cleanly. ''Primary Colors'' section: ''Merrimack Blue is integral to and a primary visual identifier... Merrimack Gold supports and accents Merrimack Blue'' -- Merrimack Blue HEX #003767, Merrimack Gold HEX #FFDD00. Gray is explicitly a separate ''Complementary Color,'' not Primary, and no white is named as a color anywhere. Candidate''s blue (#003768) was already essentially exact; corrected candidate''s gold (#F1C400, a muted amber that doesn''t match the vivid stated #FFDD00) and dropped candidate''s fabricated white.'
    ),
    (
      'the-university-of-texas-permian-basin',
      '229018',
      array['#E35205','#000000','#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/utpbfalcons.com/documents/2024/5/30/Athletics-UTPB-Brand-Guidelines.pdf',
      'high',
      'Candidate sidearm.sites.s3 PDF path 404s; found the current (2024) Athletics UTPB Brand Guidelines PDF. Its Color Palette page is image-based for the swatches; downloaded and viewed it directly and it explicitly states: ''There are three primary colors used in the UT Permian Basin color palette... UTPB orange, black, and white'' with swatches UTPB Orange #E35205, Black #000000, White #FFFFFF (Gray/Dark Gray shown separately as Secondary Colors). Candidate matches exactly; confirmed as-is.'
    ),
    (
      'pratt-institute-main',
      '194578',
      array['#FFCE2E','#000000']::text[],
      'https://www.pratt.edu/wp-content/uploads/2023/09/Pratt_VisualIdentityGuidelines_V3.pdf',
      'high',
      'Candidate goprattgo.com (Athletics) SID-downloads page has no style-guide PDF linked at all. Found Pratt Institute''s own current (Sept 2023) institute-wide Visual Identity Guidelines PDF, which pdftotext''d cleanly. ''3.2 Primary palette'': Pratt Yellow HEX #FFCE2E, Black HEX #000000, Pratt Cool Gray HEX #B7B8B9, White HEX #FFFFFF -- four colors listed in the Primary palette table. Kept the two most load-bearing colors explicitly called out in prose elsewhere (''Cadmium yellow was established as the official Institute color... Pratt Yellow logo should only be used on a black background'') -- Yellow + Black -- per the brief''s guidance to prefer 1-2 chromatic hexes when a palette has more than 3 named entries; dropped the Cool Gray and White table entries and corrected candidate''s yellow (#FFC425, no match) to the actual stated #FFCE2E.'
    ),
    (
      'bucknell',
      '211291',
      array['#E87722','#003865','#FFFFFF']::text[],
      'https://www.bucknell.edu/Documents/Communication/Branding/BucknellBrandGuidelines.pdf',
      'high',
      'Candidate color-palette page 404s and the current bucknell.edu color/brand pages are gated behind a myweb.bucknell.edu campus login. Wikipedia''s own citation for Bucknell''s colors points to this exact PDF (August 2017 Brand Guidelines); it now 403s live but was recovered via Wayback Machine and pdftotext''d cleanly. ''PRIMARY'' section: Bucknell Orange PANTONE 158C HEX E87722, Bucknell Blue PANTONE 2955C HEX 003865, Paper White HEX FFFFFF -- all three explicitly the labeled Primary trio (Secondary is a separate 5-color accent set). Corroborated exactly by teamcolorcodes.com''s independent listing (Orange #E87722, Blue #003865, ''Paper white'' #FFFFFF). Corrected candidate''s orange (#EF5B0C, no match) to the real #E87722; blue and white were already exact.'
    ),
    (
      'loyola-university-maryland',
      '163046',
      array['#005A3C','#D2D2D2','#000000']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/loyolagreyhounds.com/documents/2023/9/7/Athletics_ID_Guide_2023.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. ''PRIMARY SPIRIT COLORS'' section: ''Green and Grey are the core colors... Black has been added to the core colors to complete the Primary Spirit Color Palette'' -- Loyola Green (Pantone 342, RGB 0-90-60 = #005A3C), Hounds Grey (Pantone Cool Gray 3, RGB 210-210-210 = #D2D2D2), Black (RGB 0-0-0 = #000000); only RGB/CMYK/Pantone are given, hex derived deterministically from the stated RGB triplets. Candidate''s green matched (#005A3C) but candidate had put White in the second slot and moved Grey to third -- corrected: real Primary trio is Green, Grey, Black; White is not an official color anywhere in the document.'
    ),
    (
      'suny-college-at-plattsburgh',
      '196246',
      array['#CF102D','#FFFFFF','#000000']::text[],
      'https://www.brandcolorcode.com/suny-plattsburgh',
      'medium',
      'Candidate PDF 404s and the current plattsburgh.edu branding page returns a 403/blocked response with no extractable content (repeated attempts). Used a reputable secondary index (brandcolorcode.com) that names all three colors with SUNY-Plattsburgh-specific internal names -- Hawkins Tower (black, #000000), Snow Goose (white, #FFFFFF), Cardinal (red, PMS 186C, CMYK 2/100/85/6, #CF102D) -- specificity (unique campus color names, matching Pantone) that strongly indicates it is sourced from Plattsburgh''s actual visual identity guide rather than a generic guess. Candidate''s white and black were already exact; nudged candidate''s red (#C8102E) to the more precisely corroborated #CF102D. Medium confidence: could not independently verify hex directly on-domain.'
    ),
    (
      'thomas-jefferson-university',
      '216366',
      array['#1A2650','#68BCE2']::text[],
      'https://teamcolorcodes.com/thomas-jefferson-university-rams-color-codes/',
      'low',
      'Candidate jeffersonrams.com homepage has no linked style guide or brand PDF; searched the athletics site (sports/brand-guidelines paths all 404) and jefferson.edu marketing pages without finding an on-domain hex statement. Fell back to a reputable secondary index (teamcolorcodes.com): ''The primary colors of the Thomas Jefferson University Rams'' are Jefferson Deep Blue (PMS 2768C, #1A2650) and Bright Blue (PMS 297C, #68BCE2) -- no white named. Corrected candidate''s two blues slightly (#152456 -> #1A2650, #58B7DD -> #68BCE2) to match this source and dropped candidate''s fabricated white. Low confidence: no official on-domain hex found.'
    ),
    (
      'wentworth-institute-of-technology',
      '168227',
      array['#FFCB05','#000000']::text[],
      'https://wit.edu/sites/default/files/2022-12/2023_Brand-Identity-Guide_v2_External.pdf',
      'high',
      'Candidate wit.edu/media URL 404s; found the current 2023 Brand Identity Guide PDF and pdftotext''d it cleanly. ''Primary Palette: Wentworth''s official school colors, gold and black, make up our primary color palette'' -- HEX #FFCB05 (gold) and HEX #000000 (black); a separate ''Secondary Palette'' includes an unrelated Ruby Red (#D92228) and Old Gold. Candidate''s red (#CF142B) does not match anything in the primary palette (closest is the secondary Ruby Red, a different tier and different exact value) -- dropped it. Corrected candidate''s gold (#F7D417, no match) to the real #FFCB05; black confirmed.'
    ),
    (
      'monmouth-university',
      '185572',
      array['#002855','#FFFFFF']::text[],
      'https://www.monmouth.edu/brand/visual-identity-guidelines/color-palette/',
      'high',
      'Candidate monmouthhawks.com ViewArticle.dbml URL 404s (retired legacy CMS path). Found the current official monmouth.edu Color Palette page: ''These colors are deeply rooted within our DNA and therefore comprise our primary color palette... the primary colors of the finished piece should be Shadow Blue (Pantone 295) and white'' -- Shadow Blue HEX #002855, White HEX #FFFFFF. All other listed colors (Pantone 2945 #004C97, Pantone 292 #69B3E7, several grays, an orange) are explicitly Secondary/Accent. Corrected candidate''s blue (#041E42, no match) to the real #002855 and dropped candidate''s gray (#A5A9AD), which is not the Primary blue+white pair and does not match any of the secondary grays exactly either.'
    ),
    (
      'westfield-state-university',
      '168263',
      array['#232C64','#FFFFFF']::text[],
      'https://www.westfield.ma.edu/offices/office-marketing/logos-assets',
      'medium',
      'Candidate westfield.ma.edu/uploads/marketing/GI_Manual.pdf URL fails to resolve. Found a current ''2022 Visual Brand Guidelines'' PDF link on westfield.ma.edu, but every fetch attempt (direct and via Wayback) returned a byte-truncated, unparseable file despite a 200 status -- could not read it directly. Instead read the current (Wayback-captured, since live fetch 403s) Logos & Assets page, which states: ''Both Westfield State primary logos should never be printed using any other colors than Pantone 280, black, or white.'' Cross-referenced brandcolorcode.com, which cites ''Westfield State University Brand Guidelines (Verified Source)'' and gives exactly 2 primary colors -- Blue (Pantone 280C) #232C64 and White #FFFFFF. Corrected candidate''s blue (#00247D, a plausible but unconfirmed generic Pantone-280 web conversion) to the verified #232C64 and dropped candidate''s fabricated gold, which is not named anywhere. Medium confidence: the school''s own PDF could not be read directly due to a technical download failure, not a content issue.'
    ),
    (
      'clark-atlanta-university',
      '138947',
      array['#CE1126','#444F51']::text[],
      'http://clarkatlantasports.com/sports/2016/3/15/logo-information.aspx',
      'high',
      'Candidate URL is still live. Page states plainly: ''Color Guides: Red | PMS186 | Hex CE1126; Grey | PMS432 | Hex: 444F51'' -- these are the only two colors given an explicit stated hex anywhere on the page. A separate ''Color Use Rules'' table lists Red/Black/White/Grey as background options for different logo lockup variants (CAU All Black, CAU All White), but that table gives no hex for Black or White -- they are unlabeled reproduction backgrounds, not part of the page''s actual ''Color Guides'' hex statement. Corrected candidate: kept Red (#CE1126, matches exactly) and replaced the fabricated white/black pair with the actual second named color, Grey #444F51, which the candidate had dropped entirely.'
    ),
    (
      'vermont-state-university',
      '231165',
      array['#DD314E']::text[],
      'https://vermontstate.edu/',
      'low',
      'Candidate URL is castleton.edu (the pre-2023 Castleton State College athletics-treatments page) -- Castleton merged with Northern Vermont University and Vermont Technical College in 2023 into an entirely new institution, Vermont State University, with a brand-new logo/identity (a green-triangle mark with the wordmark in red, per contemporaneous news coverage of the May 2022 unveiling). The old candidate green/gray Castleton values are for a defunct predecessor brand and the castleton.edu URL itself now 403s. No official VSU brand-guidelines page or PDF with a stated hex list could be found (vsc.edu system-branding page and vermontstate.edu news posts about the rebrand both 403/block automated fetches). vermontstate.edu''s own site CSS exposes named custom properties matching the rebrand''s Vermont-landscape theme (--wp--preset--color--sunset: #DD314E, used functionally as the site''s interactive button/link color) -- used this single red as a medium-confidence-capped, CSS-only signal per the no-eyedropping rule. Deliberately did NOT include a green: the CSS palette has several plausible greens (moss #03FFB5, spring #A5CF4C, light-green-cyan #7bdcb5) with no way to determine which (if any) is the actual logo green without eyedropping the logo image, which is barred. Recommend a human follow-up once VSU publishes an actual brand guide. NOTE FOR HUMAN REVIEW: single-color, CSS-sourced only.'
    ),
    (
      'bradley-university',
      '143358',
      array['#A50000','#999999']::text[],
      'https://static.bradleybraves.com/custompages/pdf9/892784.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. Color information page gives exactly two named colors -- Bradley Red (PANTONE 186C, HTML A50000) and Kaboom Gray (PANTONE 428C, HTML 999999) -- with no white or black anywhere. Candidate''s red matched exactly; corrected by replacing candidate''s fabricated white+black pair with the actual second official color, Kaboom Gray, which the candidate had dropped entirely.'
    ),
    (
      'university-of-mary-washington',
      '232681',
      array['#0D2F5B','#FFFFFF']::text[],
      'https://teamcolorcodes.com/university-of-mary-washington-eagles-color-codes/',
      'low',
      'Candidate citation (umweagles.com/landing/index) is a generic athletics homepage with no style-guide content. UMW''s actual Brand Toolkit lives at documents.umw.edu/document/umw-brand-standards/ and at in.umw.edu, both of which require a campus login (403/gated) and could not be read. Fell back to a reputable secondary index (teamcolorcodes.com): ''colors are Navy and White'' -- Navy PMS 648C #0D2F5B, White #FFFFFF. Nudged candidate''s navy (#14315A, a plausible but slightly different dark navy) to this more specific PMS-sourced value; white confirmed. Low confidence: official brand toolkit is access-gated and could not be independently verified.'
    ),
    (
      'university-of-scranton',
      '215929',
      array['#512D6D','#FFFFFF']::text[],
      'https://www.scranton.edu/printing-services/identity-standards.pdf',
      'medium',
      'Candidate URL path (marketing-communications/images/Identity-standards-manual.pdf) fails outright (scranton.edu''s TLS handshake fails for all direct fetch attempts from this environment); recovered the current-generation guide, hosted at a different scranton.edu path, via Wayback Machine, and pdftotext''d it cleanly. States plainly: ''The official colors of The University of Scranton are purple and white. When purple is used, the specified color is Pantone 269 (100%)'' -- no hex is given anywhere in the document, only the Pantone number. Black appears only in reproduction-option combinations (''Black and Pantone 269'') for one-color logo variants, not as one of ''the official colors.'' Used a standard PMS-269-C-to-hex conversion (#512D6D) rather than candidate''s #4A245E or a differently-sourced #6E4990 seen elsewhere (which converts from the athletics-only PMS 7678C, a different Pantone than what this official document states). Dropped candidate''s black per the explicit two-color statement. Medium confidence: hex is a standard Pantone conversion, not itself printed in the source document.'
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
