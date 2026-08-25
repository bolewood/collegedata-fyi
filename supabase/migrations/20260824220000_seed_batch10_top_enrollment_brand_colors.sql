-- Batch 10 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Most candidate citation URLs had rotted (dead sidearm/S3 PDFs -- often
-- resolvable by swapping the S3 bucket region from us-east-1 to
-- us-east-2, which fixed several -- restructured .edu paths, image-only
-- or client-rendered pages with zero extractable static text, Cloudflare-
-- gated domains, and one Issuu viewer whose only "colors" are Issuu's own
-- app-shell theme). Every school below was re-sourced against the school's
-- own current official domain where possible, verified by downloading
-- PDFs and running pdftotext -layout (never trusting a fetch-tool summary
-- of a PDF), or by reading the raw HTML/CSS text of an official page (via
-- direct fetch, WebFetch as a fallback for one Cloudflare-gated page
-- cross-checked against an independent Wayback re-extraction, or -- where
-- a domain had reorganized or a live page 500'd -- a Wayback Machine
-- capture of the exact same official URL).
--
-- Wrong-swatch catches (candidate hex did not match the school's own
-- official source, exactly the risk this batch is built to guard
-- against): carnegie-mellon (candidate #990000 is not CMU's actual
-- Carnegie Red, #C41230), southern-methodist-university (candidate's red
-- and blue were both wrong -- #354CA1 turned out to be a Sidearm CMS theme
-- color on the same page, not a documented SMU swatch; real Official
-- Colors are #D70000 red / #0033A1 blue), american-university (candidate's
-- #005099/#C4122E belong to the page's "Highlight Colors" section --
-- Embassy Blue and Tenleytown red -- not the "Official logo colors"
-- section, #E0263C/#004FA2), the-university-of-montana (candidate did not
-- match the verified official Heritage/primary palette at all).
--
-- Primary-vs-secondary corrections (candidate mechanically included a
-- white/black that the real source marks as secondary, or missed the
-- section literally labeled primary): harvard, austin-peay-state-
-- university (both: white kept because it's one of exactly two labeled
-- PRIMARY colors; a secondary black dropped), georgetown, the-university-
-- of-texas-at-tyler (both: white dropped -- explicitly secondary in the
-- source, not primary), uchicago (white dropped -- secondary palette;
-- single chromatic primary kept), university-of-alaska-anchorage,
-- university-of-central-arkansas, university-of-minnesota-duluth,
-- marquette-university, university-of-northern-iowa, university-of-west-
-- georgia, university-of-wisconsin-stevens-point, nova-southeastern-
-- university, the-college-of-new-jersey (white/extra dropped or, for
-- TCNJ, the institution-wide Official Colors section chosen over the
-- Official Athletics Colors section the candidate had actually cited --
-- flagged for human review as a judgment call between two equally
-- official pairs in the same document).
--
-- Confirmed as-is (candidate hex matched the verified official source
-- exactly, including the narrow case where white/black really is one of
-- only 2-3 labeled primary colors): university-of-idaho, saint-louis-
-- university, marshall-university, vanderbilt, brown.
--
-- Left null: central-connecticut-state-university -- the candidate's
-- cited PDF was checked against Wayback's full capture history (2011-2013)
-- and never once served a real PDF (always text/html), meaning the link
-- was broken from the start; no official CCSU identity/brand page with a
-- stated hex could be found on ccsu.edu or the athletics domain within
-- scope. A generic Sidearm CMS theme-color meta tag was deliberately not
-- treated as a stated brand color.
--
-- Flagged for human review (real uncertainty remains after best-effort
-- resolution -- see full rationale in the jsonl): university-of-dayton
-- (current official "Primary Colors" section is two blues with no red at
-- all, surprising for a red/blue school; a "Logo Colors" pair closer to
-- common expectation exists in the same document), pace-university
-- (only a live, real, but dated 2014 PDF was reachable; the current 2024
-- Brand Toolkit is SharePoint-gated), emory (live brand.emory.edu/color
-- .html 500'd on every attempt; a Wayback capture's "Primary Palette" has
-- seven blue/gold variants with no single unambiguous pair), belmont-
-- university (page text confirms Belmont Blue/Red as primary/secondary,
-- but the actual swatch values live in a CloudFront-blocked SVG that
-- could not be independently text-verified; corroborated only by a web
-- search summarizing the same page), stockton-university (the official
-- page's own prose is internally inconsistent about which colors are
-- "official" vs. "primary"), the-university-of-montana and the-college-
-- of-new-jersey (see above).
--
-- Ran every final hex list through production deriveInks()/glyphInks()
-- (web/src/lib/derive-inks.ts) via a throwaway vitest scratch file
-- (deleted before finishing). No case lost a real chromatic primary to
-- the house-ink fallback -- every non-null school below produced its own
-- derived plates. Several schools with an official gray/silver alongside
-- one chromatic (e.g. idaho-state-university, marshall-university,
-- vanderbilt, nova-southeastern-university, saint-louis-university) fall
-- into deriveInks' single-ink path because the algorithm correctly treats
-- true near-neutral grays as non-chromatic -- expected behavior, not a
-- bug, and consistent with those schools' own "gray"/"silver" labeling.
-- See data/brand-colors/batch-10-2026-08-24.jsonl for the full per-school
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
      'central-connecticut-state-university',
      '128771',
      null::text[],
      null::text,
      null::text,
      'Candidate citation (ccsubluedevils.com CCSU_ID_MANUAL_May2011.pdf) is dead -- resolves to the athletics site''s live HTML shell, not a PDF. Checked Wayback CDX for this exact URL across 2011-2013: every capture returned mimetype text/html, meaning this link never actually served a real PDF even historically -- it was broken from the start. The athletics site''s own page declares theme-primary-color #0e529a / theme-secondary-color #d2d5d9 in a meta tag (CMS theme config, not a documented brand swatch). Checked ccsu.edu homepage for a /brand or /identity page -- none found in top-level nav. No official CCSU identity guide with a stated hex could be located within scope. Left null rather than treat a generic CMS theme-color meta tag as a stated brand color.'
    ),
    (
      'university-of-central-arkansas',
      '106704',
      array['#582C83', '#7C878E']::text[],
      'https://uca.edu/toolkit/official-colors/',
      'high',
      'Candidate''s sidearm S3 PDF is dead (NoSuchKey). Found and read UCA''s official colors page directly: ''The two official colors of the University of Central Arkansas are purple and gray.'' Official purple HEX #582C83, official gray HEX #7C878E -- both stated explicitly, matching the candidate''s purple/gray exactly. Dropped candidate''s white: only two colors are named official, no white swatch on the page.'
    ),
    (
      'university-of-idaho',
      '142285',
      array['#F1B300', '#191919', '#808080']::text[],
      'https://web.archive.org/web/20180716024932/https://www.uidaho.edu/brand-resource-center/visual-style-guide/color-identity',
      'medium',
      'Candidate URL is now a client-rendered Next.js shell with no color data in the static HTML or embedded __NEXT_DATA__ (curl and WebFetch both got an effective 404). Used a Wayback Machine capture of the exact same official URL (2018) instead: page body reads ''Gold, Silver, Black and White are the primary colors for the University of Idaho... Our main gold is Pride Gold.'' Stated hexes: Pride Gold #F1B300, Silver #808080, White #FFFFFF, Black #191919 -- all four explicitly labeled primary. Candidate''s three (gold/black/silver) are confirmed exactly; kept as-is, dropping white to stay under the 3-hex cap since gold/black/silver was already the candidate''s choice. Medium confidence because the live page could not be independently re-verified today (site now client-renders) -- worth a re-check next time the site is reachable.'
    ),
    (
      'university-of-dayton',
      '202480',
      array['#141B4D', '#0200D1']::text[],
      'https://web.archive.org/web/2023/https://udayton.edu/brand/colors.php',
      'medium',
      'Candidate URL now redirects live to udayton.edu''s generic error_page.php (confirmed via curl -w url_effective). Used a Wayback capture of the exact same URL instead. Page structure: Brand Guide > Colors, with three explicit sections -- ''Primary Colors'' (Glow Navy #141B4D, Glow Blue #0200D1), ''Accent Colors'' (Glow Turquoise #4BDEFB, Glow Red #E4002B), and ''Logo Colors'' (Flyers Blue #003087, Red Scare #CE0037, ''foundational colors used in the institutional logo''). Candidate''s hex (#002F87/#D70036) approximates neither section exactly. Per the brief''s instruction to prefer the section literally labeled Primary, used Glow Navy + Glow Blue -- correcting away from the candidate and away from the more red-inclusive Logo Colors pair. Flagged for human review: surprising that UD''s current ''Primary Colors'' section contains no red at all for a red-and-blue school; the Logo Colors pair (#003087 navy / #CE0037 red) is the closer match to common expectation and may be the better choice for a glyph -- worth a second opinion.'
    ),
    (
      'pace-university',
      '194310',
      array['#214277', '#FDC12D']::text[],
      'https://www.pace.edu/sites/default/files/files/ITS/Pace%20Style%20Guide%202_13.pdf',
      'medium',
      'Candidate''s cited StyleGuide_July2015.pdf 404s (redirects to pace.edu/page-not-found). Found and pdftotext''d a different, still-live Pace style guide PDF (dated Feb 2014): ''Primary Colors: The primary blue and gold are established by Pace University''s logo... Identity Base Color'' HEX 214277 (blue), HEX fdc12d (gold) -- stated directly, not eyedropped. Current live pace.edu/university-relations/marketing-and-communications/brand-standards page has no textual hex (theme CSS only); the 2024 Brand Toolkit PDF linked from it is SharePoint-gated and not publicly fetchable. Medium confidence: source is real and directly stated but is an older (2014) document; current values could not be independently confirmed. Dropped candidate''s white (not part of the stated primary pair) and corrected the hex values, which did not match the 2014 PDF''s stated Identity Base Color.'
    ),
    (
      'marquette-university',
      '239105',
      array['#003366', '#FFCC00']::text[],
      'https://www.marquette.edu/marketing-communication/color-palette.php',
      'high',
      'Candidate''s gomarquette.com athletics page is a generic ''Communications'' directory page with no brand color content (only Sidearm CMS theme config in a JS payload). Found and read Marquette''s official university Color Palette page instead: ''Primary brand colors... Marquette Blue HEX 003366... Marquette Gold HEX FFCC00.'' Matches candidate exactly minus white, which is not part of the stated primary pair.'
    ),
    (
      'harvard',
      '166027',
      array['#A31F36', '#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/gocrimson.com/documents/2021/7/27/Harvard_Athletics_Brand_Identity_Guide.pdf',
      'high',
      'Candidate''s original S3 URL (sidearm.sites bucket, us-east-1 default) returned AccessDenied; found the working us-east-2 bucket path for the same document and pdftotext''d it directly. PDF states explicitly: ''PRIMARY: CRIMSON HTML A31F36, WHITE HTML FFFFFF -- The primary colors of Harvard Athletics are Crimson and white.'' A separate ''SECONDARY'' section gives Black HTML 2C2A29 and Anthracite HTML 373A36. Candidate included the secondary black as a third color; dropped it since only Crimson+White are labeled PRIMARY (exactly the narrow case where white belongs -- it''s one of only 2 labeled primaries).'
    ),
    (
      'idaho-state-university',
      '142276',
      array['#F47920', '#000000']::text[],
      'https://www.isu.edu/brand/design/colors/',
      'high',
      'Live page confirms: ''The official ISU colors are Roarange and Bengal Black.'' Print table: Roarange RGB(244,121,32) = #F47920, Bengal Black RGB(0,0,0) = #000000. Web-colors table separately restates Roarange as #f47920 ''(accent color)''. Candidate''s duplicated black entry collapsed to one; matches exactly otherwise.'
    ),
    (
      'georgetown',
      '131496',
      array['#041E42', '#AFA9A0']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/guhoyas.com/documents/2019/9/18/Athletics_Brand_and_Visual_Identity.pdf',
      'high',
      'Candidate''s original bucket path returned AccessDenied; the us-east-2 bucket path for the same filename resolved and was pdftotext''d directly. PDF states: ''The official colors of the Georgetown University Athletics Department are blue and gray with the use of white and black as needed.'' Table gives Blue HEX 041E42, Gray HEX AFA9A0, White #FFFFFF, Black #000000. Corrected: kept only the two colors actually called ''official'' (blue, gray); candidate''s white is explicitly ''as needed'' usage, not one of the two official colors, so it was dropped rather than kept.'
    ),
    (
      'uchicago',
      '144050',
      array['#800000']::text[],
      'https://bpb-us-w2.wpmucdn.com/voices.uchicago.edu/dist/1/2295/files/2023/09/Brand-Guidelines.pdf',
      'high',
      'Candidate''s news.uchicago.edu citation 404s. Found and pdftotext''d the current UChicago Brand Identity Guidelines PDF (10.2022 edition). ''PRIMARY PALETTE: Maroon should always be the dominant color, with Greys used as accents'' -- Maroon HEX #800000, plus three named greys (Light Greystone #D9D9D9, Greystone #A6A6A6, Dark Greystone #737373). White/Black are in a separate SECONDARY PALETTE table, not primary. Corrected: dropped candidate''s white (it''s secondary, not primary) and kept just the one chromatic primary (Maroon); the primary-palette greys are neutral accents, not a second chromatic, consistent with the prefer-1-2-chromatic guidance.'
    ),
    (
      'austin-peay-state-university',
      '219602',
      array['#C41E3A', '#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/apsugovernors.com/documents/2019/5/30/APSU_Governors_Brand_Identity.pdf',
      'high',
      'Candidate''s original bucket path 404''d; us-east-2 bucket path for the same file resolved. PDF: ''PRIMARY PALETTE: GOVERNORS RED HTML #C41E3A, WHITE HTML #FFFFFF.'' A separate ''SECONDARY PALETTE'' lists Black #000000, Silver Gray #ADAFAA, Azalea Pink #EF60A3. Corrected: dropped candidate''s black -- it''s secondary, not primary; Red+White are the only two labeled PRIMARY colors (again the narrow case where white belongs).'
    ),
    (
      'stockton-university',
      '186876',
      array['#79BDE9', '#FFC423']::text[],
      'https://stockton.edu/relations/brand-guide/brand-colors.html',
      'medium',
      'Candidate''s general_info_sept2016_web.pdf 404s. Found and read Stockton''s current Brand Colors page, which is internally inconsistent: prose says ''The official colors of Stockton University are black and white, with accent colors of blue (PMS 292) and yellow (PMS 123),'' but the page''s own ''Primary Color Palette'' table lists all four (Blue #79BDE9, Yellow #FFC423, Black #000000, White #FFFFFF) under one ''Primary'' heading, and the accessibility-guidance section separately calls blue/yellow ''our primary blue and yellow.'' Chose the two chromatic colors (blue, yellow) per the prefer-1-2-chromatic default, correcting the candidate''s blue (#80BCEC, imprecise) to the page''s stated #79BDE9 and dropping black/white. Flagged for human review given the source page''s own contradictory language about which colors are ''official'' vs ''primary.'''
    ),
    (
      'university-of-northern-iowa',
      '154095',
      array['#500778', '#FFB500']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/uni.sidearmsports.com/documents/2021/5/6/Style_Guide.pdf',
      'high',
      'Candidate URL resolved directly (us-east-2 bucket). PDF (3-page style guide) shows exactly two colors on its cover swatch: Pantone 2607C #500778 (purple) and Pantone 7549C #FFB500 (gold) -- no third color anywhere in the document. Dropped candidate''s white; the source has only these two.'
    ),
    (
      'university-of-west-georgia',
      '141334',
      array['#0033A1', '#DB1A21']::text[],
      'https://www.westga.edu/assets-opentext/assetsADV/ucm/Visual-Brand-Identity-Guide-2016.pdf',
      'high',
      'Candidate URL resolved and was pdftotext''d directly. PDF states: ''The university''s official colors are blue (PMS 286) and red (PMS 185)... Blue is the primary color, and red is used as an accent... Gray (PMS 429) is a secondary color... Light blue (PMS 284) is an additional accent.'' No hex is printed, only RGB (Blue R0 G51 B161, Red R219 G26 B33) -- converted deterministically to #0033A1 / #DB1A21, matching the candidate exactly. Dropped candidate''s white (not mentioned anywhere in the document) and the gray/light-blue extras (explicitly secondary/additional, not the two official colors).'
    ),
    (
      'the-university-of-montana',
      '180489',
      array['#70002E', '#F9423A', '#ED8B00']::text[],
      'https://www.umt.edu/brand/colors.php',
      'high',
      'Candidate''s gogriz.com athletics FAQ page redirects to a generic FAQ, not a color guide (any hex present there is Sidearm CMS theme config, not documented brand color). Found and read UM''s official Brand Guidelines > University Colors page instead: ''Heritage Colors'' table, explicitly headed ''primary color values for print and screen'': Griz Maroon HEX #70002e, Sunset Red HEX #F9423A, Copper Climb HEX #ED8B00 -- followed by a separate ''Secondary Colors'' table (Wheat, etc.). Also checked: ''Snowbowl Silver'' is a defined Photoshop gradient (Glacier Sky to White), not a flat swatch, so it was not usable as a single hex. Flagged for human review: this is a large correction from the candidate (#5E001D/#6B6B6B did not match the verified official page at all); all three Heritage/primary colors kept since the source explicitly caps its primary set at exactly these three.'
    ),
    (
      'the-university-of-texas-at-tyler',
      '228802',
      array['#002F6C', '#CB6015']::text[],
      'https://www.uttyler.edu/offices/marketing/files/ut-tyler-athletic-brand-guide-2023.pdf',
      'high',
      'Candidate''s uttyler.edu/marketing/... path 404s; found the working path under /offices/marketing/files/... for the same filename and pdftotext''d it. PDF: ''PRIMARY COLORS FOR ATHLETICS: PANTONE 159 HEX #CB6015 (orange), PANTONE 294 HEX #002F6C (navy), PANTONE 428 HEX #C1C6C8 (light gray).'' A separate ''SECONDARY COLORS FOR ATHLETICS'' section lists White #FFFFFF and two greys. Corrected: dropped candidate''s white -- it''s secondary, not primary -- and kept the two chromatic primaries (navy, orange); the primary-palette light gray was dropped per prefer-1-2-chromatic.'
    ),
    (
      'university-of-minnesota-duluth',
      '174233',
      array['#7A0019', '#FFCC33']::text[],
      'https://umpr.d.umn.edu/brand/brand-standards/colors',
      'high',
      'Candidate''s d.umn.edu/external-affairs/... URL 404s (site reorganized). Found and read the current University Marketing and Public Relations colors page: ''Main Colors: Maroon and gold must be prominent in all designs... Electronic colors: Gold: R255 G204 B51 (#ffcc33), Maroon: R122 G0 B25 (#7a0019).'' Matches candidate exactly; dropped candidate''s white, which is not part of the stated main-colors pair.'
    ),
    (
      'university-of-wisconsin-stevens-point',
      '240480',
      array['#512698', '#FFC82E']::text[],
      'https://www.uwsp.edu/university-communications-and-marketing/wp-content/uploads/sites/69/2026/02/communication-standards-manual.pdf',
      'high',
      'Candidate''s uwsp.edu/ucm/Documents/... URL is dead (redirects to WordPress homepage shell). Found and pdftotext''d the current (Feb 2026) Communication Standards Manual instead: ''Primary colors... Gold-PMS 123: RGB 255,200,46; Purple-PMS 267: RGB 81,38,152'' (also restated identically in a later Canva-colors chart as HEX #512698 / #ffc82e). Corrected: candidate''s hexes (#59178A/#FCC917) did not match the verified official values; used the document''s own stated hex. Dropped candidate''s white (not part of the primary pair).'
    ),
    (
      'carnegie-mellon',
      '211440',
      array['#C41230']::text[],
      'https://www.cmu.edu/brand/brand-guidelines/visual-identity/colors.html',
      'high',
      'Candidate''s cmu.edu/marcom/... URL 404s. Found and read the current CMU Brand Standards colors page: ''Core Colors... Carnegie Red should be a standout color in your designs'' -- Carnegie Red HEX #C41230, plus Black #000000, Iron Gray #6D6E71, Steel Gray #E0E0E0, White #FFFFFF, all five listed under one ''Core Colors'' heading. Wrong-swatch catch: candidate''s hex #990000 does not match CMU''s actual Carnegie Red (#C41230) at all -- corrected. Since Core Colors has 5 members (not a clean 2-3 primary set) and only Carnegie Red is chromatic, kept just the one chromatic per prefer-1-2-chromatic, dropping candidate''s white and the greys.'
    ),
    (
      'emory',
      '139658',
      array['#012169', '#F2A900']::text[],
      'https://web.archive.org/web/20241105034508/https://brand.emory.edu/color.html',
      'medium',
      'Candidate''s communications.emory.edu PDF 404s; live brand.emory.edu/color.html currently 500s (stale web-login redirect) on repeated attempts. Used a 2024 Wayback capture of the exact official URL: ''Primary Palette: The traditional Emory colors are the foundation'' lists seven swatches -- Emory Blue #012169 (PMS 280), Dark Blue #0c2340, Medium Blue #0033a0, Light Blue #007dba, Yellow #f2a900 (PMS 130), Gold #b58500, Metallic Gold #84754e -- with no single unambiguous ''the two'' called out among them. Chose the eponymous ''Emory Blue'' plus ''Yellow'' as the most defensible chromatic pair. Flagged for human review: source page currently down for live re-verification, and the primary palette has too many blue/gold variants to cleanly pick two without judgment.'
    ),
    (
      'southern-methodist-university',
      '228246',
      array['#D70000', '#0033A1']::text[],
      'https://smumustangs.com/sports/2016/6/8/ot-smu-licensing-html.aspx',
      'high',
      'Candidate URL resolved live. Page text: ''SMU Brand Guidelines - Official Colors: Red PANTONE 186C HEX #D70000, Blue PANTONE 286C HEX #0033A1'' -- exactly two official colors, no white. Wrong-swatch catch: candidate''s hexes (#CC0035 red, #354CA1 blue) do not match either official value; #354CA1 appears elsewhere on the same page only as a Sidearm CMS ''secondary_background'' theme color, not a documented SMU brand swatch. Corrected to the stated Official Colors values.'
    ),
    (
      'saint-louis-university',
      '179159',
      array['#003DA5', '#FFFFFF', '#C8C9C7']::text[],
      'https://www.slu.edu/marcom/branding-and-identity/colors-fonts.php',
      'high',
      'Candidate URL resolved live. Page states: ''Primary Color Palette... SLU Blue PMS 293C HEX 003DA5... College Church Gray PMS Cool Gray 3C HEX C8C9C7... Iris White HEX FFFFFF'' -- all three explicitly under one ''Primary Color Palette'' heading (a genuine 3-color primary set, distinct from the following ''Secondary Color Palette''). Matches candidate exactly; confirmed as-is.'
    ),
    (
      'american-university',
      '131159',
      array['#E0263C', '#004FA2']::text[],
      'https://www.american.edu/ucm/creative-style-guide.cfm',
      'high',
      'Candidate''s american.edu/ucm/resources/... path 404s; live american.edu/ucm/creative-style-guide.cfm is behind a Cloudflare bot wall for curl. Cross-verified via two independent routes: WebFetch''s rendered read, and (per constraint) my own pdftotext-equivalent extraction of a March-2026 Wayback capture of the exact live URL -- both agree. Page: ''Official logo colors: Red PANTONE 186 HEX #E0263c... Blue PANTONE 072 HEX #004FA2.'' Wrong-swatch catch: candidate''s hexes (#005099, #C4122E) both belong to a different section of the same page (''Highlight Colors'' -- Embassy Blue #005099 and Tenleytown red #C4122E), not the ''Official logo colors.'' Corrected to the actual official pair; dropped candidate''s white.'
    ),
    (
      'marshall-university',
      '237525',
      array['#00B140', '#FFFFFF', '#27251F']::text[],
      'https://www.marshall.edu/brandservices/files/2023/08/Marshall_University_Brand_Guidelines-1.pdf',
      'high',
      'Candidate URL resolved and was pdftotext''d directly. PDF: ''OUR COLORS - PRIMARY PALETTE... Our signature color palette, consisting of Marshall green (PMS 354), black, and white'' -- Marshall Green HEX #00b140, Black HEX #27251f, White HEX #ffffff, all three explicitly the primary/signature trio. Matches candidate exactly; confirmed as-is (this is the narrow case where white/black belong -- exactly 3 labeled primary colors).'
    ),
    (
      'nova-southeastern-university',
      '136215',
      array['#003893', '#7C858C']::text[],
      'https://www.nova.edu/brand/colors.html',
      'high',
      'Candidate''s nova.edu/brand/identity/colors.html 404s; found the correct current path (nova.edu/brand/colors.html) and read it live. ''Print - Primary Colors: the university''s primary colors are NSU Blue (PMS 287C) and Main Gray (PMS 430C)'' -- print-table hex differs slightly (#002A84), but the page''s separate ''Web - Primary Colors'' section states ''NSU Blue Hex: #003893... Main Gray Hex: #7c858c,'' matching the candidate exactly for web use. Dropped candidate''s white (not part of the named primary pair in either table).'
    ),
    (
      'brown',
      '217156',
      array['#4E3629', '#FFFFFF', '#C00404']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/brownuni.sidearmsports.com/documents/2022/6/17/BrownAthletics_StyleGuide_RGB_June_8_22.pdf?timestamp=20220617054650',
      'high',
      'Candidate''s brownbears.com and default S3 bucket paths both dead (one served an HTML shell, the other NoSuchKey); the us-east-2 bucket path for the same file resolved as a real PDF and was pdftotext''d. ''COLOR PALETTE - Primary Colors... Our color palette leans heavily on the primary brown, please use the red and white judiciously.'' BROWN HEX #4e3629, RED HEX #c00404, WHITE HEX #ffffff -- all three explicitly labeled Primary Colors. Matches candidate exactly; confirmed as-is (narrow case: exactly 3 labeled primaries, white included).'
    ),
    (
      'university-of-alaska-anchorage',
      '102553',
      array['#00583D', '#FFC425']::text[],
      'https://www.uaa.alaska.edu/about/university-advancement/university-relations/brand/_documents/uaa-brandingstyle-guide_2016.pdf',
      'high',
      'Candidate URL resolved and was pdftotext''d directly. PDF: ''UAA PALETTE - PRIMARY COLORS... UAA GREEN Hex: 00 58 3D, UAA GOLD Hex: FF C4 25... UAA green and gold are to be the predominate colors.'' A separate ''SUPPORTING COLORS'' section gives two grays, and logos ''may also be solid black or reversed (white)'' -- white is a usage note, not a labeled primary color. Corrected: dropped candidate''s white; only green+gold are PRIMARY.'
    ),
    (
      'vanderbilt',
      '221999',
      array['#000000', '#FFFFFF', '#CFAE70']::text[],
      'https://brand.vanderbilt.edu/athletics/',
      'high',
      'Candidate URL resolved live. Page''s ''Core Colors'' section for Athletics gives five swatches: Flat Gold HEX CFAE70, Rich Black HEX 000000, White HEX FFFFFF, Black HEX 1C1C1C, Dark Gray HEX 777777. Candidate''s three (black/white/gold) match three of the five exactly (Rich Black, White, Flat Gold); kept as the candidate had it since it''s within the 3-hex cap and Flat Gold is the sole chromatic ''core'' color -- confirmed as-is, dropping the duplicate Black variant and Dark Gray.'
    ),
    (
      'belmont-university',
      '219709',
      array['#00205B', '#C8102E']::text[],
      'https://www.belmont.edu/umac/brand/visual/colors.html',
      'medium',
      'Candidate''s issuu.com link only serves Issuu''s own app shell (no document content, and Issuu''s own brand colors like #ff5a47 would be a false match if trusted). Found and read Belmont''s official Brand Colors page instead: ''The primary color for Belmont University is Belmont Blue... The secondary color for Belmont University is Belmont Red.'' However, the actual swatch values are rendered as SVG images (digital-brand-colors.svg) that returned 403 (CloudFront/hotlink-protected) on every direct fetch attempt, including with a referer header -- could not independently pdftotext-equivalent them. A web search corroborated Belmont Blue = #00205B (matching the original candidate) from what it represented as the same official page. Medium confidence and flagged for human review: color names/pairing confirmed directly from the official page text, but the exact hex values could not be independently text-verified due to the blocked SVG asset -- worth a follow-up with browser-rendered access.'
    ),
    (
      'the-college-of-new-jersey',
      '187134',
      array['#293F6F', '#A67A00']::text[],
      'https://web.archive.org/web/20230620202335/https://brand.tcnj.edu/wp-content/uploads/sites/11/2019/10/TCNJ_GraphicStandardsGuide_v2.pdf',
      'high',
      'Candidate''s live PDF URL is behind a Cloudflare bot wall (403) for direct fetch; a Wayback capture of the exact URL is a real, complete PDF (40 pages) and was pdftotext''d directly. Document has two distinct color sections: ''OFFICIAL COLORS -- These official colors establish TCNJ''s brand identity in all communications'' (TCNJ Blue hex 293F6F, TCNJ Gold hex a67a00), and separately ''OFFICIAL ATHLETICS COLORS'' (TCNJ Athletics Blue hex 154A7C, TCNJ Athletics Yellow hex FCBC15 -- this second pair is what the candidate actually cited). Chose the institution-wide Official Colors over the athletics-specific pair since this is a general school-identity glyph, not a sports property. Flagged for human review: this is a judgment call between two equally well-sourced, equally ''official'' pairs in the same document -- worth a second opinion on which is more appropriate for the product.'
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
