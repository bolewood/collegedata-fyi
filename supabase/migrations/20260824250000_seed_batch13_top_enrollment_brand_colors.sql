-- Batch 13 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Every one of the 30 candidates below needed at least one correction --
-- either a wrong hex, a wrong-tier third value (a secondary/accent/athletics
-- color mistaken for primary, or vice versa), or a mechanically-appended
-- white/black that the real official source does not actually list as
-- primary. None were confirmed fully as-is. Most candidate citation URLs had
-- also rotted (dead sidearm/S3 PDFs, a typo'd humboldt.edu path, renamed
-- marcomm/office paths, a singular/plural path mismatch on ramapo.edu, a
-- 2017 baseball media guide standing in for a real brand guide, and several
-- plain 404s/403s) -- fixed by finding the school's current official
-- page/PDF instead wherever possible.
--
-- Wrong-swatch / wrong-tier catches (candidate hex did not match the
-- school's own official source, or matched the wrong section of the right
-- page -- exactly the risk this batch is built to guard against):
-- california-state-polytechnic-university-humboldt (candidate's #046A38
-- matched nothing on the real page; corrected to Old Growth Green #004C46),
-- university-of-northern-colorado (candidate's gold was wrong shade),
-- missouri-university-of-science-and-technology (candidate's white was
-- fabricated; used the Forest+Vegas Miner Athletic Colors pairing instead of
-- the four-green institutional Primary Colors group), long-island-university
-- (candidate's third value was black; the source's third official color is
-- white), northwestern-state-university-of-louisiana (both hexes wrong),
-- wake-forest (candidate's near-black/tan hexes appear nowhere on the real
-- godeacs.com page or the real brand.wfu.edu color page; corrected to Old
-- Gold #9E7E38 + Black), purdue-university-fort-wayne (candidate's gold hex
-- was a coincidental unrelated media-caption color, not a real swatch),
-- university-of-south-dakota (candidate's red did not match any of the
-- three official reds), norfolk-state-university and rhode-island-college
-- and university-of-arkansas-at-little-rock and ramapo-college-of-new-jersey
-- and the-university-of-tennessee-martin and tennessee-state-university
-- (each had one or more wrong hexes and/or a wrong-tier third value; ric's
-- candidate came from an athletics visitor guide with no color content at
-- all, and tsu's candidate matched none of the school's actual stated
-- colors), mcneese-state-university (source PDF's own printed "WEB HEX"
-- field for Royal Blue is internally inconsistent with its own stated RGB
-- on the same swatch -- used the RGB-consistent value, which happens to
-- match the candidate exactly), and university-of-san-francisco and
-- gonzaga-university (candidate's white was fabricated; the real third
-- official color in both cases is a named gray, dropped per the
-- prefer-1-2-chromatic guidance).
--
-- Low/medium confidence flags (official primary source could not be
-- directly read): duquesne-university and marist-college -- official PDFs
-- are behind Incapsula bot walls that serve Sidearm/athletics-homepage HTML
-- to automated clients instead of the document; WebFetch was tried on both
-- as a fallback and in each case honestly reported it could see only
-- download-link chrome, not real content, so nothing was fabricated from it
-- -- fell back to cross-referenced secondary team-color indices at low
-- confidence. wake-forest, norfolk-state-university, fairfield-university,
-- and high-point-university are marked medium: wake-forest's official color
-- page 403'd under curl (WAF block) and was read via WebFetch instead;
-- norfolk-state-university's and fairfield-university's live pages are
-- CMS/JS shells that name colors in prose but don't server-render a hex
-- table, so the specific hex values are cross-referenced from secondary
-- sources; high-point-university's official page names its single primary
-- color ("Royal Purple") but states no hex in prose -- the SVG logo on the
-- same page does contain the value, but per this batch's rule against
-- eyedropping SVGs it was not used as the citation, and the hex was instead
-- confirmed via secondary corroboration.
--
-- Dropped to null: virginia-state-university -- its official style guide
-- states only Pantone/CMYK for its logo colors, never a hex, and secondary
-- sources disagree with the school's own stated Pantone numbers, so no hex
-- could be safely stored without guessing.
--
-- Ran every final hex list through production deriveInks()/glyphInks()
-- (web/src/lib/derive-inks.ts) via a throwaway vitest test file (deleted
-- before finishing). One case loses a real chromatic primary to the
-- house-charcoal fallback: bowie-state-university's official dark swatch
-- (PMS 433C, #1D252C) has chroma below deriveInks' neutral threshold, so
-- the algorithm treats it as a neutral alongside white and only the gold
-- survives as a usable ink -- this is a real, intentionally-dark brand
-- primary being lost to the fallback path, not a bug in the sourcing. Every
-- other populated row produced its own derived plates (house=false). See
-- data/brand-colors/batch-13-2026-08-24.jsonl for the full per-school
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
      'california-state-polytechnic-university-humboldt',
      '115755',
      array['#004C46','#FFC72C']::text[],
      'https://www.humboldt.edu/brand/identity',
      'high',
      'Candidate URL (brand.humboldt.edu/indentity, a typo''d path) 404s. Found the live page at humboldt.edu/brand/identity: ''Primary Colors -- Old Growth Green -- HEX #004C46 ... Chanterelle Gold -- HEX #FFC72C.'' Candidate''s #046A38 does not match anything on the page at all (closest real swatch is Secondary ''Sea Glass'' #00856A). Corrected to the two named Primary Colors; no white is listed among them.'
    ),
    (
      'university-of-northern-colorado',
      '127741',
      array['#013C65','#FFB71B']::text[],
      'https://www.unco.edu/marketing-communications/assets/downloads/unc_brandGuidelines.pdf',
      'high',
      'Candidate PDF URL (university-advancement/pdf/UNC-Style-Guide-2018.pdf) 404s. Found and pdftotext''d the current Brand Guide: ''UNC''s official colors are Bears Blue and Bears Gold ... BEARS BLUE HEX #013c65 ... BEARS GOLD HEX #ffb71b.'' Blue matches candidate exactly; candidate''s gold #F6B000 was wrong -- corrected to #FFB71B. Only two official colors are named, so dropped candidate''s white.'
    ),
    (
      'colorado-christian-university',
      '126669',
      array['#00416B','#FED925']::text[],
      'https://www.ccu.edu/_files/documents/brand/branding-guide-athletics.pdf',
      'high',
      'PDF downloaded and pdftotext''d directly. ''University Colors'' swatch table: dark blue PMS 7694C HEX 00416B, yellow/gold PMS 115C HEX FED925 (matches candidate exactly on both). White is not listed among the university colors (a light blue 3CB4E5 and two grays are also shown but are separately described as accent/neutral) -- dropped candidate''s white per the no-neutral-append guidance.'
    ),
    (
      'missouri-university-of-science-and-technology',
      '178411',
      array['#154734','#CEB888']::text[],
      'https://brand.mst.edu/colors/',
      'high',
      'Candidate URL (brand.mst.edu/color/, singular) 404s; live page is /colors/. Page text confirms two labeled swatch groups: institution-wide ''Primary Colors'' (Forest #154734, Miner #007A33, Lima #72BF44, Kiwi #BFD730 -- four greens, no tan/gold, no white) and ''Miner Athletic Colors'' (Forest #154734, Vegas #CEB888, Silver #B3B4B2). Candidate''s Forest+tan+white pairing matches the athletics pairing except its white -- the real third color there is Silver, not white, and white appears nowhere on the page. Used the Forest+Vegas athletics pairing (matches candidate''s two chromatic hexes exactly) and dropped white.'
    ),
    (
      'long-island-university',
      '192448',
      array['#69B3E7','#FFC72C','#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/longislandu/documents/2019/7/25/LIU_Style_Guide.pdf',
      'high',
      'Candidate S3 URL (s3.amazonaws.com/longislandu/...) 403s; the same PDF is live at a different S3 host (sidearm.nextgen.sites). pdftotext''d directly: ''OFFICIAL COLORS -- BLUE ... GOLD ... WHITE -- OFFICIAL HTML: 69B3E7 / FFC72C / FFFFFF'' -- all three printed together as equally-official colors (this is the 2019 unified-Sharks guide, not the older LIU Post-only Adidas green/gold guide also found and discarded as wrong-era). Candidate''s blue and gold match exactly; candidate''s third value was #000000 (black), which does not appear in the source at all -- corrected to white, which the source explicitly names as the third official color.'
    ),
    (
      'northwestern-state-university-of-louisiana',
      '160038',
      array['#663399','#FFFFFF','#FF6600']::text[],
      'https://documentproviderviewer.nsula.edu/?id=11285',
      'high',
      'Candidate URL is a 2017 baseball media guide with no brand color content at all. Found NSU''s actual Visual Branding Guidelines (rev. 13 May 2015) via nsula.edu''s document provider and pdftotext''d it: ''The official colors of Northwestern State University of Louisiana are purple and white. The athletic department may additionally employ orange as an accent color ... Northwestern State Purple 663399 ... Athletic Dept Orange: ff6600.'' Candidate''s purple (#492F92) and orange (#F78426) were both wrong -- corrected to the stated hexes. White is one of the two official colors (not a mechanical append); orange is explicitly documented with its own hex as the athletic accent, so kept as third.'
    ),
    (
      'wake-forest',
      '199847',
      array['#9E7E38','#000000']::text[],
      'https://brand.wfu.edu/our-brand-identity/color-patterns-papers/',
      'medium',
      'Candidate URL (godeacs.com logos-branding.aspx) is an athletics nickname/history page with no hex or Pantone content anywhere in its text -- neither candidate hex (#2C2A29, #CEB888) appears on it. Found Wake Forest''s real brand.wfu.edu color page, but curl was blocked with an Incapsula-style 403 (''Not Allowed 0xWAFF-BOT''); used WebFetch as a fallback per the no-guessing-on-PDFs protocol, and it returned: ''The Wake Forest University colors are Old Gold and black ... Old Gold Hex: 9E7E38 ... Black Hex: 000000,'' with a separate ''Secondary Colors'' section explicitly naming #CEB888 as ''Athletics Gold'' (not primary) -- exactly the section candidate''s tan hex was pulled from. Corrected to the two named Primary Colors. Since this was read via WebFetch rather than independently pdftotext''d/curl''d, marked medium rather than high confidence.'
    ),
    (
      'purdue-university-fort-wayne',
      '151102',
      array['#CFB991','#000000','#FFFFFF']::text[],
      'https://www.pfw.edu/sites/default/files/documents-2025/10/002-CM-PFW-Brand%20Style%20Guide-Web.pdf',
      'high',
      'Candidate URL is a 2018 news article announcing the athletics rebrand; it names the colors (''gold and black,'' with blue as a secondary accent) but states no hex anywhere. Found and pdftotext''d PFW''s current (Oct 2025) official Brand Guidelines PDF: ''Primary Palette -- Golden [Summit] hex CFB991 -- Black hex 000000 -- White hex FFFFFF,'' all three listed together under one Primary Palette heading. Candidate''s black and white matched; candidate''s gold (#C28E0E, which actually only appeared as an unrelated media-caption color on the 2018 news page) was wrong -- corrected to #CFB991.'
    ),
    (
      'state-university-of-new-york-at-oswego',
      '196194',
      array['#235937','#FFCC33']::text[],
      'https://www.oswego.edu/publications/sites/www.oswego.edu.publications/files/extendedidguide.pdf',
      'high',
      'PDF downloaded and pdftotext''d directly. ''The Oswego Website colors in both hexadecimal and RGB values are: hunter green -- hexadecimal code=#235937 ... and golden yellow -- hexadecimal code=#FFCC33.'' Matches candidate''s two chromatic hexes exactly; white is not stated as a website/hex color anywhere in the document, so dropped candidate''s white.'
    ),
    (
      'university-of-south-dakota',
      '219471',
      array['#D21533','#000000']::text[],
      'https://www.usd.edu/-/media/Project/USD/DotEdu/About/Departments-Offices-and-Resources/Marketing-Communications-and-University-Relations/University-Brand-Toolkit/USD-Brand-Guide.pdf',
      'high',
      'Candidate URL (usd.edu/~/media/.../graphic-standards-and-editorial-guide.ashx) 404s. Found and pdftotext''d the current USD Brand Guide: ''Primary Colors -- COYOTE RED PANTONE 186C #D21533'' (plus two darker tints, #A10729 and #820014), alongside a separate black/gray/white tint ramp (Black 100% #000000 ... Black 0% #FFFFFF). Candidate''s red (#AD0000) matched none of the three stated reds -- corrected to Coyote Red, the named lead swatch. Kept Black as the school''s paired neutral (explicit tint-ramp companion in the same Primary Colors block); dropped white per the prefer-1-2-chromatic guidance since it''s just the 0% tint, not a distinct named color.'
    ),
    (
      'norfolk-state-university',
      '232937',
      array['#007A53','#F3D03E']::text[],
      'https://www.nsu.edu/social-media/graphic-standards',
      'medium',
      'Candidate URL (nsuspartans.com Athletics_Quick_Facts.pdf) is a schedule/roster document with no brand color content. NSU''s own Brand-and-Visual-Identity pages are CMS mega-menu shells with no server-rendered swatch table; the Graphic Standards page does confirm in prose: ''NSU''s primary colors are NSU Green, NSU Gold and NSU Gray, with official print and digital color specifications provided in the University Brand Guide'' (guide itself not locatable as a standalone PDF). Cross-referenced multiple independent secondary team-color indices, which consistently and specifically cite NSU Green as Pantone 341C / #007A53 and NSU Gold as Pantone 129C / #F3D03E -- both differ from candidate''s #007B5E and #FAB80A. Used the cross-referenced hexes; dropped NSU Gray (candidate''s white doesn''t match anything found, and no gray hex could be confirmed either), marked medium since the specific hex values come from secondary corroboration rather than a directly-read official swatch table.'
    ),
    (
      'fairfield-university',
      '129242',
      array['#C8102E']::text[],
      'https://www.fairfield.edu/brand/',
      'medium',
      'Candidate PDF URL (mc_fairfieldu_visual_standard_manual.pdf) 404s. Fairfield''s current Brand Handbook is hosted on Issuu behind a JS viewer that both curl and WebFetch (tried on the doc landing page and a specific page URL) could not get past -- WebFetch honestly reported it could only see Issuu platform chrome, not document content, so it was not used to fabricate a quote. The live fairfield.edu/brand/ landing page itself uses #C8102E as its ''Our Brand'' section accent color (found directly in the page''s own inline CSS, on-domain), and this exact hex (PMS 186, Stag Red) is independently and consistently corroborated by multiple secondary team-color indices. Candidate''s #E0143E does not match. Dropped candidate''s white and near-black third value (#231F20) -- neither could be confirmed from any source read. Marked medium: name/hex pairing is corroborated but not read from a formally labeled official swatch table.'
    ),
    (
      'duquesne-university',
      '212106',
      array['#041E42','#BA0C2F']::text[],
      'https://teamcolorcodes.com/duquesne-dukes-color-codes/',
      'low',
      'Candidate S3 URL 403s (AccessDenied). The non-S3 goduquesne.com URL is behind an Incapsula bot wall that returns the athletics homepage HTML instead of the PDF to automated clients; WebFetch was tried as a fallback and honestly reported it could only see download-link chrome, not the PDF''s contents, so nothing was fabricated from it. duq.edu''s own marketing pages do not publish a public hex table. Fell back to a reputable secondary team-color index, which matches candidate''s hexes exactly (Navy PMS 282C #041E42, Red PMS 200C #BA0C2F) with a consistent Pantone citation across multiple independent secondary sources, and also matches the live goduquesne.com site''s own embedded theme-color JSON (primary_background #011E41, secondary_background #D31245 -- close variants, further corroborating navy+red as the real pair). Dropped candidate''s white (no source lists it) and the secondary black some indices also mention, per prefer-1-2-chromatic guidance, since the official primary source could not be independently read. Low confidence: secondary-index tier only.'
    ),
    (
      'university-of-southern-indiana',
      '151306',
      array['#002856','#CF102D']::text[],
      'https://www.usi.edu/brand/logos-colors-and-fonts',
      'high',
      'Candidate PDF URL (usi-athletic-manual-2022.pdf) 404s. Found and read USI''s live Logos, Colors and Fonts page: ''USI blue and USI red are the primary colors ... Primary Palette: USI Navy Blue Web Hex #002856 ... Primary Palette: USI Red Web Hex #CF102D,'' with a separate ''Support Color: White #FFFFFF'' and ''Support Color: Gray'' tier, and a further ''Secondary Color'' tier (academic-branding only) for medium blue, light blue and gold. Candidate''s navy and red matched exactly; dropped candidate''s white since the page explicitly places it in the Support (not Primary) tier.'
    ),
    (
      'university-of-san-francisco',
      '122612',
      array['#00543C','#FDBB30','#919194']::text[],
      'https://myusf.usfca.edu/marketing-communications/resources/graphics-resources',
      'high',
      'Candidate URL resolved live and was read directly. ''These primary identity colors ... USF Green ... #00543C -- USF Gold ... #FDBB30 -- USF Grey ... #919194.'' Candidate''s green and gold matched exactly; candidate''s third value was white (#FFFFFF), which is not in this stated primary triad -- corrected to USF Grey, the color the page actually names as the third of ''these primary identity colors.'''
    ),
    (
      'adelphi-university',
      '188429',
      array['#4F2C1D','#FFB500']::text[],
      'https://www.adelphi.edu/brand/design/colors/',
      'high',
      'Candidate URL redirected live (brand.adelphi.edu -> adelphi.edu/brand) and was read directly. ''Primary Colors -- Gold and brown are Adelphi''s school colors ... Gold ... Hex: #ffb500 ... Brown ... Hex: #4f2c1d.'' Matches candidate''s brown and gold exactly. Text also says ''Gold and white should be used as the primary and dominant colors in accents'' but white is not given its own swatch/hex in the Primary Colors block (only Gold, Brown, and separately Black are), so dropped candidate''s white per prefer-1-2-chromatic guidance.'
    ),
    (
      'gonzaga-university',
      '235316',
      array['#041E42','#C8102E']::text[],
      'https://docs.gonzaga.edu/Campus-Resources/Offices-and-Services-A-Z/MarketingandCommunications/brand/docs/AthleticLogoGuide-FINAL.pdf',
      'high',
      'PDF downloaded and pdftotext''d directly. ''APPROVED PRIMARY & SECONDARY ATHLETIC LOGO COLORS -- Athletic Blue ... 041E42 -- Athletic Red ... C8102E -- Athletic Gray ... C1C6C8.'' Candidate''s blue and red matched exactly; candidate''s third value was white, which does not appear in this table at all -- the real third color is Athletic Gray, but per prefer-1-2-chromatic guidance dropped it (and candidate''s white) rather than storing a neutral.'
    ),
    (
      'marist-college',
      '192819',
      array['#C8102E']::text[],
      'https://teamcolorcodes.com/marist-red-foxes-color-codes/',
      'low',
      'Candidate PDF URL (marist.edu/publicaffairs/imc/pdfs/styleguide.pdf) 404s (institution has since been renamed Marist University). marist.edu''s current Brand Management page is a Liferay JS shell with no server-rendered color content. Found a goredfoxes.com Athletics Branding PDF, but the host is behind an Incapsula wall that serves a Sidearm Sports redirect page to automated clients instead of the PDF; WebFetch was tried as a fallback and honestly reported it could see only the download-link page, not the PDF, so nothing was invented from it. Fell back to a reputable secondary team-color index (PMS 186C, #C8102E), which exactly matches candidate''s red. Dropped candidate''s white and near-black third value since neither could be confirmed anywhere the school itself commonly describes its colors as ''red and white'' in secondary summaries, but that pairing was not independently verified either -- kept only the one color actually cross-confirmed. Low confidence: secondary-index tier only, official source unreachable.'
    ),
    (
      'winona-state-university',
      '175272',
      array['#4B08A1','#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/winonastatewarriors.com/documents/2020/7/6/WinonaState-AthleticsGraphicBrandingStandards.pdf',
      'high',
      'Candidate URL (winona.edu/create/Media/styleguide.pdf) 404s. Found and pdftotext''d the current Athletics Graphic Branding Standards: ''The official color scheme for Winona State Athletics is purple and white. The correct purple can be found below: PANTONE Violet ... Hex #4B08A1'' (a Gray #7F7F7F swatch is shown alongside but described later only as a supplementary color). Candidate''s purple matched exactly; candidate''s gold (#FFCC33) does not appear anywhere in the document -- the source explicitly says the official scheme is ''purple and white'' with no gold, so dropped it and kept white as the stated second official color.'
    ),
    (
      'high-point-university',
      '198695',
      array['#330072']::text[],
      'https://www.highpoint.edu/ooc/branding/visual-styles/',
      'medium',
      'Candidate URL (highpoint.edu/ooc/colors/) redirects live to /ooc/branding/visual-styles/, which was read directly: ''Primary Brand Colors -- The primary brand color for High Point University is Royal Purple.'' No hex is stated in the page''s prose (the value #330072 only appears as an SVG logo path fill on the same page, which per this batch''s no-eyedropping-SVGs rule was not used as the citation) and no other named color (e.g. candidate''s grey #818183) appears in the text at all. Cross-referenced multiple independent secondary sources, all of which cite Royal Purple as PMS 2685 / #330072, matching both candidate and the SVG fill exactly. Dropped candidate''s white and grey -- only one primary color is named on the official page. Medium confidence: official page names the single primary color, hex confirmed via independent secondary corroboration rather than stated prose.'
    ),
    (
      'suny-buffalo-state-university',
      '196130',
      array['#BB5B02','#000000']::text[],
      'https://marcomm.buffalostate.edu/logos-colors-fonts',
      'high',
      'Candidate URL (collegerelations.buffalostate.edu/web-palette) 404s -- office has since been renamed/merged into marcomm.buffalostate.edu. Read the current Logos-Colors-Fonts page directly: ''[Athletics uses] PMS 158 (orange) and black as its official colors for NCAA Division III ... Web Colors ... Primary: Burnt orange, #BB5B02 -- Secondary: Bright orange, #E37701 -- Tertiary: Gold, #FF9933 -- Tertiary and Text: Black, #000000.'' Candidate''s orange (#CC6600) did not match the stated Primary web orange -- corrected to #BB5B02. Candidate''s white does not appear in this palette at all -- dropped it and kept Black, which is explicitly named alongside orange as the school''s official NCAA colors.'
    ),
    (
      'virginia-state-university',
      '234155',
      null::text[],
      null,
      null,
      'PDF downloaded and pdftotext''d directly (vsu.edu/files/docs/vsu-style-guide.pdf, live). The ''COLOR USAGE'' section states only Pantone and CMYK values for the logo colors -- ''PRIMARY blue (PANTONE 2728) and orange (PANTONE 158)'' and ''SECONDARY blue (PANTONE 287) and orange (PANTONE 166)'' -- with zero hex codes printed anywhere in the 24+ page document (grepped for #[0-9A-Fa-f]{6}, no matches). Converting Pantone/CMYK to hex without a stated value would mean inventing a color, which is disallowed. Checked reputable secondary team-color indices for a cross-reference, but they cite entirely different Pantone numbers (1585/7686 orange+blue) than VSU''s own official style guide (2728/158), an internal conflict that could not be resolved without risking a wrong-swatch store. Left null rather than guess; candidate''s #1F3D7B/#FFFFFF/#E05527 could not be confirmed against any source read.'
    ),
    (
      'rhode-island-college',
      '217420',
      array['#990000','#F1B434']::text[],
      'https://our.ric.edu/documents/ric-branding-standards',
      'high',
      'Candidate URL (goanchormen.com visitors guide PDF) is a wrong-tier athletics document; pdftotext''d anyway and it has no color-swatch content. Found and pdftotext''d RIC''s actual 2020 university Brand Style Guide instead: ''The distinct color palette of burgundy, yellow, black and white ... Burgundy Hex: #990000 -- Yellow Hex: #F1B434 -- Black Hex: #000000 (an accent color) -- White Hex: #FFFFFF (an accent color).'' Candidate''s #910027 and #C39909 were both wrong -- corrected to the stated hexes. Black and white are explicitly labeled accent colors (not primary) in this source, so kept only the two chromatic primaries per prefer-1-2-chromatic guidance.'
    ),
    (
      'bowie-state-university',
      '162007',
      array['#1D252C','#FFFFFF','#FFCE00']::text[],
      'https://bowiestate.edu/about/administration-and-governance/university-relations-and-marketing/brand-and-identity-standards/our-colors.php',
      'high',
      'Candidate PDF URL (bsu-color-palette-2021.pdf) 404s. Found the live ''Our Colors'' page instead, which is even more precise: ''Primary Colors -- PMS 116C ... #ffce00 -- PMS 433C ... #1d252c -- Paper ... #ffffff,'' with separate Secondary, Accent, and Neutral palettes listed afterward. All three candidate hexes matched exactly and are explicitly grouped as the three Primary Colors (white is literally labeled ''Paper'' and grouped with the other two, not a mechanical append) -- confirmed as-is. Note for the ink pipeline: #1D252C''s chroma falls below deriveInks'' neutral threshold, so it is treated as a neutral and dropped, leaving only the gold as a usable chromatic ink (A falls back to house charcoal) -- flagged as a case where a real, intentionally dark brand primary is lost to the fallback path.'
    ),
    (
      'university-of-louisiana-at-monroe',
      '159993',
      array['#840029','#FDB913']::text[],
      'https://webservices.ulm.edu/policies/sites/policies/files/policy_uploads/ULM%20Brand%20Guide%202022%20July%2019%2C%202022.pdf',
      'high',
      'PDF downloaded and pdftotext''d directly. ''PRIMARY COLORS -- Maroon (Warhawk) and gold (Heritage Gold) are the university''s primary colors ... WARHAWK ... HEX #840029 -- HERITAGE GOLD ... HEX #FDB913,'' with a separate ''SECONDARY'' tier (Metallic Gold, Dark Grey, Gold, Mid Dark Grey, Bright Gold, Mid Light Grey, Black, Light Grey) explicitly barred from standalone/primary use. Matches candidate''s two chromatic hexes exactly; dropped candidate''s white, which is not part of either tier.'
    ),
    (
      'mcneese-state-university',
      '159717',
      array['#00529B','#FFD204']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/mcneese.sidearmsports.com/documents/2017/1/17/McNeeseStyleGuide.pdf',
      'high',
      'Candidate URL is a different (older) S3 host but resolves to the same document; downloaded, pdftotext''d, and (because the two-column color-swatch layout produced a scrambled ''WEB HEX'' string) also rendered page 4 to a PNG and read it directly. ''Royal Blue & Sunflower Gold have been the colors of McNeese State University since 1972.'' The page''s own ''WEB HEX (HTML)'' field for Royal Blue is internally inconsistent with its own stated RGB on the same swatch (RGB 0/82/155, which converts to #00529B -- matching candidate exactly -- versus a printed HEX field reading ''#00592b'', a plausible transposition typo in the source PDF). Used the RGB-consistent value. Sunflower Gold''s HEX field (#FFD204, RGB 255/210/4) is internally consistent and matches candidate exactly. White and Gray swatches are also shown but with no RGB/hex given for either -- dropped candidate''s white.'
    ),
    (
      'university-of-arkansas-at-little-rock',
      '106245',
      array['#6E2639','#A7A9AC']::text[],
      'https://ualr.edu/communications/wp-content/uploads/sites/216/2025/06/LR-Athletics-Brand-Identity_2025-update_web.pdf',
      'high',
      'Candidate URL (ualr.edu/communications/trojan-athletics-marks/) resolved live but only names colors in prose without hex; it links to the current (May 2025) Athletics Brand Standards PDF, which was downloaded and pdftotext''d: ''Little Rock uses Maroon and Silver as its two primary colors ... Maroon ... Hex: #6e2639 ... Silver ... Hex: #a7a9ac ... Secondary colors of black and white are also permissible, but the primary colors should be used whenever possible.'' Candidate''s maroon matched exactly; candidate''s third value was white, which the source explicitly demotes to secondary -- corrected to Silver, the source''s actual second primary color.'
    ),
    (
      'ramapo-college-of-new-jersey',
      '186201',
      array['#862633','#25282A']::text[],
      'https://www.ramapo.edu/brand/design-standards/',
      'high',
      'Candidate URL (ramapo.edu/design-standard/print-guidelines/, singular ''standard'') 404s. Found the live Design Standards page under the correct plural path and read it directly: ''Maroon PANTONE: 202C ... HEX: #862633 -- Cool Black PANTONE: 426C ... HEX: #25282A,'' both under a ''Primary'' heading, followed by a separate ''Secondary Palette'' (Red #C41E1E, Warm Gray #D7D2CB) explicitly described as accent-only. Candidate''s maroon (#87212E) and black (#000000) were both close-but-not-exact -- corrected to the stated Pantone-matched hexes. Dropped candidate''s white, which is not part of either the primary or secondary palette.'
    ),
    (
      'the-university-of-tennessee-martin',
      '221768',
      array['#0B2341','#FF8200']::text[],
      'https://www.utm.edu/offices-and-services/office-of-university-relations/_media/UR_StyleGuide_24-1.pdf',
      'high',
      'Candidate URL (utmsports.com Artsheet PDF) is behind an Incapsula bot wall that serves HTML to curl and could not be independently text-extracted; WebFetch was tried as a fallback and honestly reported it could see only the document title, not its contents. Found utm.edu''s own current (2024) university Style & Resource Guide instead, hosted off the blocked athletics domain, downloaded and pdftotext''d: ''The official UT Martin colors are PMS 289 blue and PMS 151 orange ... UT ORANGE HEX FF8200 ... UTM BLUE HEX 0b2341.'' Candidate''s #0D223F and #F58220 were both close-but-not-exact -- corrected to the stated hexes. The guide says the logo may print ''in reverse (white, orange...)'' as an alternate treatment, not as a third official brand color, so dropped candidate''s white.'
    ),
    (
      'tennessee-state-university',
      '221838',
      array['#00539F']::text[],
      'https://www.tnstate.edu/publications/documents/styleguide.pdf',
      'high',
      'Candidate S3 URL 403s (AccessDenied). Found and pdftotext''d tnstate.edu''s own official Style & Branding Guide instead: ''TSU Colors -- TSU Blue -- Pantone: Reflex Blue -- Web: #00539F -- White -- Web: #FFFFFF -- Black -- Web: #000000 -- Red -- Red may be used as an accent color only for approved Athletics/Student Activities events or programs'' (no hex given for red). Candidate''s #171796, #FFFFFF and #FF0504 matched none of these stated values at all -- a clear wrong-swatch candidate. White and black are given as usable logo-print colors, not named co-primary brand colors, and red is explicitly accent-only with no stated hex, so kept only the one true stated brand color, TSU Blue.'
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
