-- Batch 14 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given: jackson-state-university (the hex
-- table is only in an embedded page image, not text -- downloaded and
-- viewed it directly to confirm), washburn-university, western-illinois-
-- university, ithaca-college (used the athletics-specific colors page,
-- which lists all three candidate values including the third-value gray
-- that the general brand-colors page omits).
--
-- Wrong-swatch / wrong-tier catches (candidate hex did not match the
-- school's own official source, or matched the wrong section of the right
-- page -- exactly the risk this batch is built to guard against):
-- morehead-state-university (candidate's blue was the page's separately
-- listed "Accent Blue," not the official MSU Blue), christopher-newport-
-- university (candidate's blue was a much brighter wrong-hue value; real
-- CNU Blue is a muted navy), delaware-state-university (both chromatic
-- hexes wrong), university-of-southern-maine (both chromatic hexes wrong --
-- candidate did not match the official page at all), texas-a-and-m-
-- university-kingsville (the official PDF is internally inconsistent
-- between an RGB row and its own "HEX (HTML)" field; used the explicitly
-- labeled hex, which differs from the candidate), clayton-state-university
-- (orange was a near-miss shade), suffolk-university (both hexes were
-- near-misses), butler-university (candidate's gray did not match the
-- official Cool Gray swatch at all), pennsylvania-college-of-technology
-- (candidate's white was fabricated; the real third color is a near-black
-- "Process Black," not pure white), providence-college (candidate's third
-- value was a secondary-tier silver/gray; the official guide's Primary
-- section is only Black + White), bentley-university (used the Athletics
-- Brand Colors group, which has a gray+black the candidate's white doesn't
-- match), and university-of-alaska-fairbanks (both chromatic hexes wrong,
-- though white confirmed as legitimately one of 3 named School Colors).
--
-- Fabricated-neutral catches (candidate white/black had no support in the
-- real source and was dropped, keeping the actually-stated 1-2 chromatic
-- colors): east-stroudsburg-university-of-pennsylvania (white/black have no
-- hex at all in the source, only "---"), northeastern-state-university,
-- washburn n/a (confirmed), dartmouth (white/black are explicitly
-- Secondary, not Primary), mercer-university (also corrected black from
-- pure #000000 to the actually-stated #222222), united-states-naval-
-- academy, university-of-the-incarnate-word, northwest-missouri-state-
-- university (also dropped a "Support Color" gray the candidate carried as
-- primary), creighton-university, xavier-university, and pittsburg-state-
-- university.
--
-- Dead-link recoveries (original citation 404/403/soft-404'd; found the
-- school's current official page or PDF instead): university-of-new-haven,
-- northeastern-state-university, texas-a-and-m-university-kingsville
-- (tamuk.edu/marcomm/documents path served an actual HTML 404 disguised
-- with a .pdf extension and a 200 status), nicholls-state-university,
-- morehead-state-university, dartmouth (S3 PDF blocked by Incapsula),
-- mercer-university (styleguide.mercer.edu domain retired), university-of-
-- the-incarnate-word, western-illinois-university (goleathernecks.com PDF
-- served the Sidearm app shell, not a PDF, despite a 200 status),
-- northwest-missouri-state-university, christopher-newport-university
-- (styleguide.cnu.edu retired), clayton-state-university, butler-university
-- (butlersports.com PDF also served the Sidearm app shell), suffolk-
-- university, ithaca-college, providence-college (found a real current
-- Brand Guidelines PDF to replace a 2002 press release that was never a
-- color-spec source), university-of-southern-maine, and xavier-university.
--
-- Low/medium confidence flags (official primary source could not be
-- directly read): university-of-new-haven and nicholls-state-university --
-- both have official pages that name colors in prose but state no hex
-- anywhere on-domain (Nicholls: "official colors...are red and gray," no
-- Pantone/hex given); fell back to reputable secondary team-color indices
-- at low confidence. stevens-institute-of-technology is medium -- the real
-- Brand Guidelines PDF requires Stevens SharePoint credentials; used the
-- on-domain theme-color/msapplication-TileColor meta tag value instead and
-- dropped the unconfirmable white/gray. salem-state-university is medium --
-- no brand/color page could be found on salemstate.edu at all (the
-- candidate citation was a Web Use Policy PDF, unrelated to colors); used
-- the two most heavily-used colors in the site's own compiled CSS instead
-- of an explicit named-color statement.
--
-- Ran every final hex list through production deriveInks()/glyphInks()
-- (web/src/lib/derive-inks.ts) via a throwaway vitest test file (deleted
-- before finishing). One case loses all school-specific ink to the house
-- fallback: providence-college's confirmed pair (#000000 + #FFFFFF) is
-- fully achromatic, so deriveInks() treats it as "no usable brand colour"
-- and falls back to house forest/ochre -- Providence's glyph will render
-- identically to a school with brand_colors=null even though real official
-- data is now on file. This is expected behavior for a genuinely-achromatic
-- school identity, not a sourcing error, but is worth a human look. Every
-- other populated row produced its own derived plates (house=false). See
-- data/brand-colors/batch-14-2026-08-24.jsonl for the full per-school
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
      'university-of-new-haven',
      '129941',
      array['#004B8D','#FFC423']::text[],
      'https://teamcolorcodes.com/new-haven-chargers-color-codes/',
      'low',
      'Candidate PDF (unh-branding-guidelines.pdf) 404s. Current brand page (newhaven.edu/about/departments/marketing-communications/brand/) covers the 2023 ''Power On'' rebrand story but states no hex; a linked Issuu ''Power On Campaign Guidelines'' doc is image-based and not safely text-extractable. No on-domain hex found after searching brand page, athletics domain, and PDF paths. Fell back to a reputable secondary index (teamcolorcodes.com, citing PMS 7686C/123C) which matches the candidate blue exactly and is 2 units off the candidate gold; used its stated values. Dropped candidate''s white -- no source lists it. Low confidence: no official hex statement found.'
    ),
    (
      'east-stroudsburg-university-of-pennsylvania',
      '212115',
      array['#DB0436','#B3B9BD']::text[],
      'http://static.esuwarriors.com/custompages/General/ESU_Athletics_Visual_Identity_Guide_092017.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. Color section (p.56) gives two swatches with real hex: Pantone 199 HTML DB0436 (red) and Pantone 429 HTML B3B9BD (grey). White and Black are shown as separate swatches with CMYK/RGB but their HTML/hex fields are literally ''---'' (not given) -- the guide never states a hex for them. Corrected candidate''s fabricated white/black third+second values to the actual stated grey.'
    ),
    (
      'northeastern-state-university',
      '207263',
      array['#008265','#4A4A30']::text[],
      'https://offices.nsuok.edu/communicationsmarketing/StandardsGuides/ColorPalettes.aspx',
      'high',
      'Candidate PDF (_resources/documents/Graphic-Standards.pdf) 404s. Found the current Color Palettes page: ''Our two primary colors are NSU Green and NSU Gray... NSU Green HEX: #008265... NSU Gray HEX: #4a4a30.'' Green matches candidate exactly; corrected candidate''s neutral grey (#999999) to the actual dark olive NSU Gray, and dropped candidate''s fabricated white -- only two primary colors are named.'
    ),
    (
      'texas-a-and-m-university-kingsville',
      '228705',
      array['#003399','#FCC10F']::text[],
      'https://www.tamuk.edu/marcomm/_files_marcom/branding/graphic_standards.pdf',
      'high',
      'Candidate PDF path (marcomm/documents/graphic_standards_compressed.pdf) now serves a 404 page (confirmed via curl+file, not just status code -- title tag literally says ''404 Page Not Found''). Found the current ''GRAPHIC STANDARDS UPDATED 6/2025'' PDF at a new path and pdftotext''d it. It is internally inconsistent: the Colors table gives RGB 0/93/170 (=#005DAA, matching the candidate) directly above a ''HEX (HTML)'' field that instead reads ''Blue: #003399''; an earlier page separately states ''For web: Blue #003399, Gold #ffcc00.'' Two of three mentions in the document agree on Blue=#003399, so used the explicitly labeled HEX field rather than the RGB-derived value. Gold: the labeled HEX field reads ''#FCC10F'' (closest of three candidate values found in-doc: ''For web'' says #ffcc00, RGB row converts to #FFC425); used the labeled HEX field for consistency with the blue decision. No white is stated anywhere in either color section.'
    ),
    (
      'nicholls-state-university',
      '159966',
      array['#AE132A','#72808A']::text[],
      'https://www.nicholls.edu/branding/',
      'low',
      'Candidate URL 403s with default UA, 404s with a browser UA -- dead. Current /branding/ page (loads with a browser UA) states ''The official colors for Nicholls are red and gray. The Pantone Matching System can be used for color specifications'' but gives no hex or Pantone numbers anywhere on-domain, and no colors sub-page or PDF is linked. No hex found on nicholls.edu after checking the branding page and searching for an athletics style guide. Used a reputable secondary index (teamcolorcodes.com / brandcolorcode.com, converging on PMS 187C #AE132A and PMS 430C #72808A) as a last resort. Candidate''s #C41230/#B2B2B2 do not match this or any other source found. Low confidence: no official hex statement located.'
    ),
    (
      'jackson-state-university',
      '175856',
      array['#002147','#FFFFFF','#008ED6']::text[],
      'http://www.jsums.edu/styleguide/jsu-color-scheme/',
      'high',
      'Page text states ''navy blue -- Pantone 282 and white'' as the signature colors plus a limited-use ''highlight'' blue (Pantone 2925), but the actual hex table is embedded as an image (JSUmanualPg13.jpg), not text -- pdftotext-style extraction alone would have missed it. Downloaded and viewed the image directly: it explicitly lists ''Web applications: Navy Blue Hex - 002147, White Hex - FFFFFF, Hightlight Blue Hex - 008ED6.'' Confirmed candidate exactly as-is; white is legitimately one of only 3 official colors shown in that table.'
    ),
    (
      'morehead-state-university',
      '157386',
      array['#0033A0','#FFCF00']::text[],
      'https://moreheadstate.edu/about-msu/leadership/administration/communications-marketing/brand-style-guide/',
      'high',
      'Page text: ''Morehead State''s official colors are Pantone 286 Blue and Pantone 116 Gold'' -> ''MSU Blue Pantone 286 #0033A0'' and ''MSU Gold Pantone 116 #FFCF00.'' Candidate''s blue (#005EB8) is actually the page''s separately-listed ''Accent Blue Pantone 300'' -- a permitted accent, not one of the two official colors. Corrected to the real MSU Blue and dropped candidate''s fabricated white (White/Gray/Black are listed as ''other colors...permitted as accents,'' not official).'
    ),
    (
      'washburn-university',
      '156082',
      array['#002E5E','#FFFFFF']::text[],
      'https://www.washburn.edu/about/public-relations/licensing/files/Washburn-Brand-Book.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. ''The foundations of the Washburn brand are blue and white'' -- the Primary Colors block lists four swatches (dark blue #002E5E PMS 648C, mid blue #598DB6, light blue #B9CFE2, white #FFFFFF PMS WHITE) as one family, but the prose foundation statement names only blue+white. Confirmed candidate as-is: darkest/main blue plus white, which is explicitly named as one of the primary swatches (not a mechanical append).'
    ),
    (
      'dartmouth',
      '182670',
      array['#00693E']::text[],
      'https://communications.dartmouth.edu/visual-identity/design-elements/color-palette',
      'high',
      'Candidate S3 PDF (dartmouthsports.com) 403s (Incapsula-style block). Found the current official Office of Communications color-palette page instead: ''Primary Color: Dartmouth Green PMS 349 ... #00693e.'' Green matches candidate exactly, but White and Black are explicitly listed under a separate ''Secondary Colors'' heading on the same page, not Primary -- dropped both per the no-neutral-append rule (they are not part of the labeled 2-3 primary set; there is only one labeled Primary Color).'
    ),
    (
      'mercer-university',
      '140447',
      array['#F76800','#222222']::text[],
      'https://www.mercer.edu/university-branding/typography-and-colors/',
      'high',
      'Candidate URL (styleguide.mercer.edu/2-color/) refuses connection -- domain appears retired. Found the current ''Typography and Colors'' page on mercer.edu: ''Primary Mercer Orange ... HEX #f76800'' and, in a ''Black and Grays'' block described as ''a large part of the primary color palette,'' ''Black HEX #222222.'' Corrected candidate''s orange (#CB5307, no match anywhere) to the real #F76800 and corrected pure #000000 to the actually-stated #222222; dropped white, which is just one of six generic grayscale utility tones on the page, not a named primary color.'
    ),
    (
      'united-states-naval-academy',
      '164155',
      array['#00225B','#B5A67C']::text[],
      'https://navysports.com/sports/2022/12/21/logos-style-sheet.aspx',
      'high',
      'Page states: ''Official Colors of the Naval Academy Athletic Association ... Navy Blue 282C ... #00225B ... Vegas Gold 4525C ... #B5A67C.'' Exactly two official colors are listed, no white. Confirmed both candidate chromatic values as-is; dropped candidate''s fabricated white.'
    ),
    (
      'bentley-university',
      '164739',
      array['#1B5FAA','#88898A','#000000']::text[],
      'https://www.bentley.edu/files/pdf/Bentley_Athletic_Brand_Style_Guide-FINAL.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. Page 5 shows two color groups: ''Athletics Brand Colors'' (PMS 2935 #1B5FAA, PMS 424 #88898A, Black #000000) and a separate ''Academic Core Brand Colors'' (PMS 3005 #0075BE, PMS 295 #365375, PMS 7542 #B3C4CC, Black). Candidate''s blue matches Athletics Brand Colors exactly. Used the Athletics group since the cited document is specifically the athletics brand guide -- all three (blue, grey, black) are explicitly grouped under that one heading, so black is not a mechanical append here. Corrected candidate''s fabricated white to the actual stated grey.'
    ),
    (
      'pennsylvania-college-of-technology',
      '366252',
      array['#0071CE','#231F20','#B2B3B2']::text[],
      'https://www.pct.edu/sites/default/files/2021-04/2268%20Wildcat%20Visual%20Guidelines.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly, but no hex text is printed directly -- only Pantone/CMYK/RGB. Color Breakdowns section gives PANTONE 285C RGB 0/113/206 (=#0071CE, matches candidate exactly), PROCESS BLACK C RGB 35/31/32 (=#231F20, a near-black not pure #000000), and PANTONE 421C RGB 178/179/178 (=#B2B3B2, matches candidate exactly). No white appears in the color breakdown at all -- corrected candidate''s fabricated white to the actual stated Process Black.'
    ),
    (
      'university-of-the-incarnate-word',
      '225627',
      array['#CB333B','#000000']::text[],
      'https://www.uiw.edu/style-guide/colors.html',
      'high',
      'Candidate S3 PDF 404s. The logo-colors page (my.uiw.edu/styleguide) names ''Pantone 1797 (red) and black'' but gives no hex. Found the web style guide''s Colors page instead: ''UIW Red #cb333b ... Black #000000'' (plus Digital Red, Dark Red, Dark Gray, Gray -- none of which are white). Confirmed candidate''s red and black as-is; dropped candidate''s fabricated white, which is not listed anywhere.'
    ),
    (
      'western-illinois-university',
      '149772',
      array['#663399','#FFFFFF','#FFCC00']::text[],
      'https://www.wiu.edu/brand_guidelines/visual_identity.php',
      'high',
      'Candidate PDF (goleathernecks.com) returns HTTP 200 but the body is the Sidearm Sports app shell, not a PDF -- dead link. Found the current official Visual Identity page instead: ''PURPLE GOLD WHITE ... Hex #663399 Hex #FFCC00 Hex #FFFFFF'' with the prose ''WIU Purple should be balanced with equal parts white.'' All three are explicitly the labeled primary trio -- confirmed candidate exactly as-is.'
    ),
    (
      'delaware-state-university',
      '130934',
      array['#004D74','#D51C28','#009CDB']::text[],
      'https://www.desu.edu/sites/flagship/files/document/31/dsu_style_guide.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. ''Primary logo colors'': Pantone P114-16C #004D74 (blue), Pantone P48-16C #D51C28 (red), Pantone 299C #009CDB (bright blue) -- three explicitly-labeled primary colors, no white among them (''Other colors used in marketing'' lists a separate darker blue/light-blue/pale-blue trio). Neither candidate chromatic value matched anything on the page (candidate''s #EE3124 and #0099CC are both wrong shades) -- corrected all three values and dropped the fabricated white.'
    ),
    (
      'northwest-missouri-state-university',
      '178624',
      array['#006A4E','#FFFFFF']::text[],
      'https://www.nwmissouri.edu/marketing/pdf/design/AthleticsGraphicStandards.pdf',
      'high',
      'Candidate PDF (sidearm S3 path) 404s. Found the current graphic standards PDF on the university''s own marketing domain and pdftotext''d it: ''The Primary Palette: Bearcat Green and White are the official colors for Northwest Missouri State Bearcat Athletics'' -- Bearcat Green Hex #006A4E, confirmed candidate exactly. Bearcat Gray (#BABBBC, matching candidate''s third value) is explicitly described as an optional ''Support Color,'' not part of ''The Primary Palette'' -- dropped it, keeping the stated Green+White primary pair.'
    ),
    (
      'christopher-newport-university',
      '231712',
      array['#1B386D','#84888B']::text[],
      'https://cnu.edu/brand/colors.html',
      'high',
      'Candidate URL (styleguide.cnu.edu) refuses connection -- domain retired. Found the current brand colors page: ''Primary Colors: CNU Blue Pantone 288 ... Hex #1b386d ... This is the signature color... CNU Silver Pantone 877 ... Hex #: 84888b.'' Candidate''s silver matches exactly, but candidate''s blue (#0039A6) is a much brighter, wrong-hue blue that does not match the actual muted CNU Blue -- corrected. Dropped candidate''s fabricated white; only Blue and Silver are labeled Primary Colors.'
    ),
    (
      'creighton-university',
      '181002',
      array['#005CA9','#00235D']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/creighton.sidearmsports.com/documents/2022/6/9/Creighton_Guide_Logos_Website_1_.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. ''The official colors of Creighton University Athletics are CU Blue, CU Navy Blue, CU Light Blue, CU Gray and CU Light Gray'' with a web-hex row: CU Blue #005CA9, CU Navy #00235D, CU Light Blue #6CADDE, CU Gray #828282, CU Light Gray #C8C8C8. Candidate''s two blues match exactly; white is not part of the five official colors anywhere -- dropped the fabricated white.'
    ),
    (
      'clayton-state-university',
      '139311',
      array['#092C74','#FC6D23']::text[],
      'https://www.clayton.edu/marcomm/brand-toolkit/visual-identity.php',
      'high',
      'Candidate URL (clayton.edu/MarComm/Visual-Identity) 404s. Found the current brand-toolkit color page: ''The official University school colors are Laker Blue and Georgia Clay ... Primary Colors: Laker Blue Hex: #092c74, Georgia Clay Hex: #fc6d23'' (Secondary/Tertiary colors listed separately). Blue matches candidate exactly; corrected the orange from candidate''s #FC6719 to the actually-stated #FC6D23 and dropped the fabricated white -- only two colors are labeled Primary.'
    ),
    (
      'butler-university',
      '150163',
      array['#13294B','#00A3E0']::text[],
      'https://epics.butler.edu/wp-content/uploads/2020/02/bu-brandguidelines2019-web.pdf',
      'high',
      'Candidate PDF (butlersports.com/documents/2020/11/29) returns HTTP 200 but the body is the Sidearm Sports app shell, not a PDF -- dead. Found the same style guide document mirrored on Butler''s own epics.butler.edu subdomain and pdftotext''d it: ''PRIMARY BRAND COLORS: In addition to the two primary tones of Butler blue... Butler Blue Pantone 2767C Web:13294B, Bright Blue Pantone 299C Web:00A3E0, Cool Gray Pantone 621C Web:D1E0D7.'' Candidate''s Butler Blue matches exactly. Used the two named ''primary tones of Butler blue'' rather than also including the near-white Cool Gray swatch, and dropped candidate''s fabricated white and mismatched grey (#75787B does not match the actual Cool Gray #D1E0D7).'
    ),
    (
      'salem-state-university',
      '167729',
      array['#00205B','#D24700']::text[],
      'https://www.salemstate.edu/',
      'medium',
      'Candidate citation URL was a Web Use Policy PDF (404, and clearly not a brand/color document even when live). No official brand-guide page or PDF could be found after searching salemstate.edu/marketing-and-creative-services and web search for a visual-identity guide. Pulled the site''s own compiled CSS (sites/default/files/css/...) and found #00205B (navy, 111 occurrences) and #D24700 (burnt orange, 89 occurrences) as by far the dominant on-domain colors, consistent in family with widely-reported Salem State navy+orange but at different exact shades than any third-party aggregator. Medium confidence: on-domain CSS usage, not an explicit named-color statement. Candidate''s #212F5E/#F37C2F (from an unrelated color-palette page) were close in hue but not confirmed anywhere official -- not used.'
    ),
    (
      'suffolk-university',
      '168005',
      array['#15284B','#BC912C']::text[],
      'https://www.suffolk.edu/-/media/suffolk/documents/about/directory/office-of-marketing-and-communication/online-resources/suffolk-visual-guidelines_refresh2025.pdf',
      'high',
      'Candidate PDF path 404s. Found the current (updated 3/26/25) Brand Identity Guidelines PDF and pdftotext''d it: ''Our Institutional Palette: Suffolk Blue PMS 2767 C/U #15284b, Suffolk Gold PMS 8642 C (metallic) / PMS 118C-117U (non-metallic) #bc912c.'' Corrected both candidate hexes (#142F53 and #C6A141, neither an exact match) and dropped the fabricated white -- only two colors form the Institutional Palette.'
    ),
    (
      'ithaca-college',
      '191968',
      array['#003B71','#FFBB00','#9C9C9C']::text[],
      'https://www.ithaca.edu/brand-guide/athletics/official-athletics-colors',
      'high',
      'Candidate URL (graphic-standards/color) 404s. The institutional Brand Colors page names only two ''Core Brand Colors'' (IC Blue #003B71, IC Gold #FFBB00), but the separate Official Athletics Colors page lists all three: ''IC Blue HEX #003b71 ... IC Gold HEX #ffbb00 ... Gray HEX #9c9c9c'' (PMS-C Cool Gray 11). Confirmed candidate exactly as-is using the athletics-specific page, which is the closer match to the original citation''s intent.'
    ),
    (
      'providence-college',
      '217402',
      array['#000000','#FFFFFF']::text[],
      'https://web-services.providence.edu/wp-content/uploads/sites/180/2024/08/OptimizedAccessiblePDF-1.pdf',
      'high',
      'Candidate citation (friars.com genrel-091202aaa) is a 2002 logo-unveiling press release, not a color spec page -- it says ''traditional black and white colors, which symbolize... the Dominican Order of Preachers, with silver (PMS 877) being a new color added,'' but states no hex for silver. Found the current official Providence College Brand Guidelines PDF and pdftotext''d it: p.38 ''PRIMARY: Providence Black HEX #000000, White HEX #ffffff'' -- explicitly the only two Primary colors. ''Cool Gray HEX #a3a19e (PMS 877 Metallic)'' and ''Providence Gold HEX #bd9e5e'' are explicitly SECONDARY, not primary. Dropped candidate''s third value (silver/grey) as wrong-tier; kept the two labeled Primary colors. NOTE FOR HUMAN REVIEW: deriveInks() treats an all-neutral pair as ''no usable brand colour'' and falls back fully to house forest/ochre inks -- Providence''s glyph and school-page ink will render identically to a school with brand_colors=null, even though real official data is now on file. This is a known edge case in the derive pipeline, not a data error.'
    ),
    (
      'stevens-institute-of-technology',
      '186867',
      array['#A32638']::text[],
      'https://www.stevens.edu/brandguide',
      'medium',
      'The public brandguide page and its linked ''Branding Resources'' page are navigation/resource hubs with no printed color spec text -- the actual Brand Guidelines PDF lives on a Stevens SharePoint site requiring institutional credentials and could not be accessed. #A32638 is confirmed as the school''s own on-domain value via the <meta name=''theme-color''> and <meta name=''msapplication-TileColor''> tags used consistently across stevens.edu and stevens.edu subpages, and matches the color used for the Stevens ''S'' logo mark in inline SVGs on the same pages. No hex could be confirmed on-domain for white or grey (candidate''s #9A989A does not match any on-domain color found; a nearby SVG logo fill uses #7f7f7f instead, unconfirmed as a named brand color). Medium confidence, single chromatic value only.'
    ),
    (
      'university-of-southern-maine',
      '161554',
      array['#002752','#F5A800']::text[],
      'https://usm.maine.edu/office-of-marketing-and-strategic-communications/brand-guidelines-and-visual-identity/color-standards/',
      'high',
      'Candidate PDF (office-of-marketing-and-brand-management/athstyleguide.pdf) 404s. Found the current Color Standards page: ''Primary color palette: The university''s primary brand colors are blue and gold... USM Blue Pantone 648C HEX: #002752... USM Gold Pantone 130C HEX: #F5A800.'' Both candidate chromatic values were wrong (candidate''s #1E3B78 and #FFCC00 do not match either official shade) -- corrected both, and dropped the fabricated white; only blue and gold are named as primary.'
    ),
    (
      'pittsburg-state-university',
      '155681',
      array['#CC0C2F','#FCD116']::text[],
      'https://www.pittstate.edu/office/university-marketing/docs/psu-brand-guide.pdf',
      'high',
      'PDF loads and pdftotext''d cleanly. ''Official Brand Colors: The official colors of Pittsburg State University are crimson and gold... PMS 186 HEX CC0C2F (web use)... PMS 116 HEX FCD116 (web use).'' Both candidate chromatic values confirmed exactly as-is; dropped the fabricated white -- only crimson and gold are named official colors.'
    ),
    (
      'xavier-university',
      '206622',
      array['#0C2340','#9EA2A2']::text[],
      'https://www.xavier.edu/brand/brand-graphic-identity/',
      'high',
      'Candidate PDF path (xavier-brand-standards.pdf) 404s. Found the current Design Elements / Brand Graphic Identity page instead: ''Our colors, led by Xavier Blue... Xavier Blue HEX: #0C2340 PMS: 289; Xavier Grey HEX: #9EA2A2 PMS: 422'' (a third color, ''Running Man Blue'' #0033A0, is tied to a specific logo variant, not the general palette). Both candidate chromatic values confirmed exactly as-is; dropped the fabricated white, which is not listed on this page.'
    ),
    (
      'university-of-alaska-fairbanks',
      '102614',
      array['#236192','#FFCD00','#FFFFFF']::text[],
      'https://alaskananooks.com/sports/2021/6/7/sports-information.aspx',
      'high',
      'Candidate citation (a 2009 GEN_0901095624.aspx page) 200s but redirects to a generic current-roster page with a ''Logo and Colors, click here'' link. Followed it to the current Sports Information page: ''SCHOOL COLORS Pantone Plus 647C ... Pantone Plus 116C ... White ... Hex: 236192 Hex: FFCD00 Hex: FFFFFF'' -- three explicitly labeled School Colors including white. Corrected both candidate chromatic hexes (#1E59AE and #FCD006, neither matching the actual stated values) and confirmed white is legitimately official here (explicitly one of only 3 named School Colors, not a mechanical append).'
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
