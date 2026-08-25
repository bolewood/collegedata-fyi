-- Batch 16 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given: colgate-university (all three
-- hexes matched the official athletics style guide exactly, recovered via
-- Wayback).
--
-- Wrong-swatch / wrong-tier catches (candidate hex did not match the
-- school's own official source, or matched the wrong section of the right
-- page): pepperdine-university (both blue and orange corrected against the
-- official IMC page), oral-roberts-university (Navy/Gold confirmed, white
-- was fabricated), biola-university (red corrected against the school's
-- current brand page; candidate cited a bot-walled 2015 athletics PDF),
-- lander-university (both blue and gold corrected against the March 2025
-- official brand guide; the document's own "Golden Claw Exception" note
-- demotes candidate's third value out of primary use), university-of-the-
-- pacific (orange and black nudged to the official institutional brand
-- page's stated values; white demoted to the document's own Neutral tier),
-- abilene-christian-university (purple/white confirmed exactly per an
-- explicit "official colors" statement; fabricated gray dropped),
-- bryant-university (gold and black corrected against the school's 2024
-- Creative Brand Guidelines PDF), point-loma-nazarene-university (gold
-- corrected; green already exact), the-catholic-university-of-america
-- (red fully corrected and a fabricated black replaced with the real
-- second Primary color, Catholic Blue), rider-university (cranberry
-- corrected by reading the printed text in the official "Institutional
-- Colors" chart image; fabricated gray dropped), western-oregon-university
-- (red/white confirmed via stated RGB; black demoted -- document's own
-- Secondary tier), fort-lewis-college (navy and gold corrected against the
-- official color page; a second official blue was not carried in to stay
-- within budget -- flagged below), minnesota-state-university-moorhead
-- (red and gray corrected against the current, May-2025 official PDF;
-- white confirmed as one of an explicit 3-color Primary Palette),
-- missouri-southern-state-university (green and gold nudged to the
-- current, Oct-2025-revised Brand Guide's precise hex), davenport-
-- university (candidate's athletics-site colors replaced entirely with the
-- university's own official 4-color primary list), endicott-college (minor
-- hex nudges; white confirmed as 1 of 3 explicit official colors),
-- eastern-new-mexico-university-main-campus (green corrected; also caught
-- a wrong-institution near-miss, see below), bemidji-state-university
-- (fabricated white/black replaced with the real second official color,
-- Blue, recovered via Wayback).
--
-- Fabricated-neutral / wrong-tier-neutral catches (candidate white/black/
-- gray had no support in the real source, or belonged to a different tier,
-- and was dropped or replaced): pepperdine-university, western-connecticut-
-- state-university, oral-roberts-university, lander-university, eastern-
-- new-mexico-university-main-campus, cuny-medgar-evers-college,
-- university-of-the-pacific, abilene-christian-university, point-loma-
-- nazarene-university, the-catholic-university-of-america, plymouth-state-
-- university (black dropped -- the official 2-color statement is "Green
-- and White" only), bemidji-state-university, davenport-university,
-- rider-university, western-oregon-university, fort-lewis-college,
-- college-of-the-holy-cross (candidate's white/black had no support in the
-- source at all; reduced to the single clearly-stated core color, Holy
-- Cross Purple), wesleyan-university.
--
-- Dead-link / access-blocked recoveries (original citation 404/403'd or
-- was bot-walled, or rendered nothing extractable; found the school's
-- current official page, a same-domain PDF, or a Wayback Machine capture
-- instead): winthrop-university (Wayback), oral-roberts-university
-- (Wayback), biola-university (bot-walled on both live and every Wayback
-- capture; used the school's current brand page instead), lander-
-- university, university-of-the-pacific (bot-walled; used the
-- institutional brand page), abilene-christian-university, bryant-
-- university, point-loma-nazarene-university (bot-walled; used the
-- current identity-standards page), colgate-university (Wayback), the-
-- catholic-university-of-america, plymouth-state-university, bemidji-
-- state-university (Wayback of the actual PDF, not the site shell),
-- davenport-university (bot-walled; used the institutional brand page),
-- college-of-the-holy-cross, rider-university, western-oregon-university,
-- st-olaf-college, fort-lewis-college, minnesota-state-university-
-- moorhead, missouri-southern-state-university.
--
-- Wrong-institution catch: eastern-new-mexico-university-main-campus's
-- search surfaced a real, live PDF (ruidoso.enmu.edu's 2025 style guide)
-- that on inspection turned out to be ENMU-RUIDOSO's own separate branch-
-- campus identity system ("royal blue and orange"), not the main campus's
-- green/gray -- correctly rejected rather than used.
--
-- Low/medium confidence flags (official primary source could not be
-- directly read, or hex was not itself stated in an otherwise-confirmed
-- official document): siena-college is medium -- siena.edu's official
-- colors page is entirely client-rendered with no extractable text;
-- corroborated the candidate's exact green/gold via a same-institution
-- athletics-site functional theme config (window.site_colors). york-
-- college-of-pennsylvania is medium -- three different sources (the
-- site's own theme config, a secondary index, and the candidate) each
-- give a slightly different green, with no on-domain "official colors"
-- statement found and the brand asset store login-gated; kept candidate's
-- green as the value already corroborated by the school's own site
-- config. eastern-new-mexico-university-main-campus is low -- enmu.edu is
-- entirely client-rendered with zero server-side text; used a reputable
-- secondary index. molloy-college is medium -- no molloy.edu institutional
-- brand page exists at all; corroborated via the athletics site's own
-- functional theme color, which disagrees somewhat with an independent
-- secondary index. plymouth-state-university is medium -- the official
-- library FAQ names "Green and White" but gives no hex; hex corroborated
-- via a secondary index. wesleyan-university is medium -- the official
-- visual-style page names "Cardinal Red and Black Squirrel" but gives no
-- hex anywhere (checked linked CSS for named custom properties too); hex
-- corroborated via a secondary team-color index. st-olaf-college is
-- medium -- two separate official stolaf.edu PDFs both give only Pantone
-- (PMS 131), never a literal hex; used a standard Pantone-to-hex
-- conversion.
--
-- Human-review flag: fort-lewis-college's official Primary Palette
-- actually contains two blues (Bright Blue #0074B8 and Dark Blue #004B8D);
-- only Dark Blue was carried in to stay within the 2-3 hex budget favoring
-- chromatic pairs. Revisit if the brighter blue is judged more
-- representative.
--
-- Left null: southwestern-oklahoma-state-university. Candidate's swosu.edu
-- citation 404s; no marketing/brand page or style-guide PDF could be found
-- anywhere on the domain (checked the homepage, site CSS, and several web
-- searches). The only source with a hex value explicitly states it was
-- eyedropped from an SVG logo rather than stated as text, so it was
-- rejected per the never-eyedrop rule rather than used at low confidence.
--
-- Ran every final hex list through production deriveInks()/glyphInks()
-- (web/src/lib/derive-inks.ts) via a throwaway vitest test file (deleted
-- before finishing). Every one of the 29 populated rows produced its own
-- derived plates (house=false) -- no school in this batch lost its
-- chromatic primary to the house forest/ochre fallback. See
-- data/brand-colors/batch-16-2026-08-24.jsonl for the full per-school
-- record, including the null Southwestern Oklahoma State entry.

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
      'pepperdine-university',
      '121150',
      array['#1E2859','#E65526']::text[],
      'http://community.pepperdine.edu/imc/resources/style-guide/official-colors/',
      'high',
      'Page loads and states plainly: "Pepperdine University is represented in print by Pantone 281 blue and 166 orange... Pepperdine Blue Pantone 281 #1e2859, Pepperdine Orange Pantone 166 #e65526." Corrected candidate''s blue (#00205C, no match) and orange (#EE7624, close but not the stated value) to the actual stated hexes. Dropped candidate''s fabricated white -- the Primary Colors section lists exactly two colors; White appears only inside the Secondary palette list with no hex given at all.'
    ),
    (
      'winthrop-university',
      '218964',
      array['#660000','#F0B323']::text[],
      'https://s3.amazonaws.com/sidearm.sites/winthropeagles.com/documents/2019/9/10/Art_Sheet.pdf',
      'high',
      'S3 PDF 404s directly; recovered via Wayback Machine capture of the same URL. PDF loads and pdftotext''d cleanly: "UNIVERSITY COLORS" table gives exactly two swatches with full Pantone/RGB/HTML data -- PMS 188C HTML 660000 and PMS 7409C HTML F0B323. A third row header "Process Black" appears in the table but its hex/RGB columns did not extract, and no white swatch appears anywhere. Confirmed candidate''s maroon and gold exactly; dropped the fabricated white and did not carry over the unconfirmed Process Black.'
    ),
    (
      'southwestern-oklahoma-state-university',
      '207865',
      null::text[],
      null,
      null,
      'Candidate URL (swosu.edu/administration/pr-m/index.aspx) 404s. Checked swosu.edu homepage and site CSS for a marketing/brand/style-guide page or named color CSS custom property -- none found; the domain has no discoverable public brand page. Searched for an official SWOSU style-guide PDF (several query variants) -- none found. The only external source with a hex value (usteamcolors.com, "Navy Blue and White", #1E3D69) explicitly states its hex was "confirmed by the SVG logo," i.e. eyedropped from the logo rather than stated as text -- rejected per the never-eyedrop rule. Left null; recorded the search so a future pass can pick this up if SWOSU publishes a real style guide.'
    ),
    (
      'western-connecticut-state-university',
      '130776',
      array['#002856','#FF4D00']::text[],
      'https://www.wcsu.edu/communications-marketing/color-palette/',
      'high',
      'Page loads and states plainly: "University Color Palette / STARBURST ORANGE Pantone PMS 1655 ... HEX #ff4d00 / DEEP BLUE Pantone PMS 295 ... HEX #002856", followed by a separate "Secondary Colors" section. Confirmed candidate''s blue and orange exactly; dropped candidate''s fabricated white, which does not appear anywhere on the page (not even in Secondary).'
    ),
    (
      'oral-roberts-university',
      '207582',
      array['#002462','#DAC792']::text[],
      'https://s3.amazonaws.com/oruathletics.com/documents/2021/8/20/2021_22_ORU_Athletics_Style_Guide.pdf',
      'high',
      'S3 PDF 403s directly; recovered via Wayback Machine capture of the same URL. PDF loads and pdftotext''d cleanly: "Our primary colors are Navy and Vegas Gold... PRIMARY COLORS: Navy PANTONE 282, hex #002462; Vegas Gold PANTONE 4525, hex #dac792", followed by a separate "ACCENT COLORS -- NEEDS WRITTEN APPROVAL FOR USAGE" section. Confirmed candidate''s navy and gold exactly; dropped candidate''s fabricated white, which is not listed anywhere as Primary or Accent.'
    ),
    (
      'biola-university',
      '110097',
      array['#CC1122','#000000','#FFFFFF']::text[],
      'https://www.biola.edu/brand/toolkits-standards/visual-design',
      'high',
      'Candidate''s 2015 athletics PDF is bot-walled on both live fetch and Wayback (every capture is the JS-rendered site shell, never the raw PDF); also tried a newer 2018 athletics style-guide path found on the same page, same bot-wall result. Found Biola''s current official brand page instead: "Biola Red has been central to the university''s visual identity for decades. This particular shade of red, along with black and white, serve as Biola''s official colors... Biola Red Pantone 186, HEX #CC1122... Black HEX #000000... White HEX #FFFFFF." Corrected candidate''s red (#E51636, no match anywhere) to the real, explicitly-named #CC1122; confirmed black and white, which the page explicitly names as 2 of only 3 official colors alongside red.'
    ),
    (
      'siena-college',
      '195474',
      array['#006B54','#FCC917']::text[],
      'https://sienasaints.com/news/2023/8/9/general-siena-refreshes-and-unifies-colleges-visual-identity.aspx',
      'medium',
      'Candidate''s siena.edu design-center colors page loads (200) but its entire body, including any color swatches, is client-side rendered -- static HTML extraction yields no color content at all. Recovered a same-institution corroboration instead: sienasaints.com''s 2023 visual-identity-refresh news article embeds a functional site-wide theme config in its page script, window.site_colors = {"primary_background":"#006B54",..."secondary_background":"#FCC917",...}, which exactly matches the candidate''s green and gold. This is a site-wide functional color value (not labeled prose text), so capped at medium confidence. Dropped candidate''s fabricated white, which has no support in this config and does not appear in a secondary teamcolorcodes.com index either.'
    ),
    (
      'lander-university',
      '218229',
      array['#003599','#F6B800']::text[],
      'https://www.lander.edu/about/_files/documents/style-guide/The-Lander-Blueprint-Colors-3-2025.pdf',
      'high',
      'Candidate''s landerbearcats.com/athletics/Bearcat_Logo page 404s. Found Lander''s current (March 2025) official "Lander Blueprint" brand guide PDF instead, which pdftotext''d cleanly. "Lander''s color palette defines the University''s visual identity, leading with Legacy Blue and Medallion Gold. These colors are the foundation of our brand identity..." Primary Palette table gives Legacy Blue WEB 003599, Medallion (gold) WEB F6B800, and Golden Claw WEB FDDB32 -- but the same page adds an explicit "Golden Claw Exception: Although Golden Claw is featured within the primary palette, this color is almost always treated as a secondary color." Corrected candidate''s blue (#235782, no match) and gold (#F8E463, no match) to the true leading pair; dropped Golden Claw per the document''s own exception note, and dropped candidate''s fabricated white (not part of the primary palette at all).'
    ),
    (
      'eastern-new-mexico-university-main-campus',
      '187648',
      array['#166936','#A7A9AC']::text[],
      'https://teamcolorcodes.com/eastern-new-mexico-greyhounds-color-codes/',
      'low',
      'Candidate''s my.enmu.edu document_library PDF link resolves to the portal''s JS-rendered app shell, not the file. enmu.edu itself is entirely client-side rendered on its new CMS with no server-side text at all -- genuinely not text-extractable. Found and downloaded a real PDF at ruidoso.enmu.edu''s 2025 style guide, but on reading it this is ENMU-RUIDOSO''s own separate branch-campus identity guide ("royal blue and orange... collegiate colors") -- a different institution''s colors, correctly rejected as a wrong-school pull. Fell back to a reputable secondary index (teamcolorcodes.com): "Green PMS 349 C Hex #166936, Gray PMS Cool Gray 6 C Hex #A7A9AC." Corrected candidate''s green (#006633, no match) to the corroborated #166936; confirmed gray exactly; dropped candidate''s fabricated white. Low confidence: no official on-domain hex could be independently confirmed.'
    ),
    (
      'york-college-of-pennsylvania',
      '217059',
      array['#009844','#231F20','#FFFFFF']::text[],
      'https://ycpspartans.com/',
      'medium',
      'Candidate citation is only the athletics homepage (no dedicated colors page found; ycp.edu''s brand resource center is gated behind a login-only Brandworks asset store). The live site''s own functional theme config gives two slightly different greens (#00853E, #009844); a teamcolorcodes.com secondary index instead lists Black #231F20, Green #008350, White #FFFFFF as the "primary colors" -- a third, still-different green. All three sources agree closely on black and white and roughly on a kelly-green, but no single source''s exact green could be independently confirmed against the others; kept candidate''s green as a value already corroborated by the school''s own site config, and confirmed black/white which match the secondary index exactly. Medium confidence given the unresolved green discrepancy and no explicit on-domain "official colors" statement.'
    ),
    (
      'cuny-medgar-evers-college',
      '190646',
      array['#231F20','#FDD044']::text[],
      'https://mecathletics.com/sports/2019/4/18/logo-downloads-and-official-colors.aspx',
      'high',
      'Page loads and states plainly, in static HTML: "The official school colors of Medgar Evers College are black and gold. Below are the specific shades of black and gold that Medgar Evers College officially uses: MEC Black ... #231F20, MEC Gold ... #FDD044." Confirmed candidate''s black and gold exactly; dropped candidate''s fabricated white, which is not mentioned anywhere on the page (the official statement names exactly two colors).'
    ),
    (
      'university-of-the-pacific',
      '120883',
      array['#FF671D','#0F0F0F']::text[],
      'https://publications.pacific.edu/pacific-brand-identity/colors.html',
      'high',
      'Candidate''s pacifictigers.com athletics PDF is bot-walled on both live fetch and every Wayback capture (an alternate cached-document path also 404s). Found Pacific''s official institutional brand-identity page instead: "Pacific''s primary color palette consists of orange and black... PACIFIC ORANGE Pantone 165 C, WEB: #FF671D... PACIFIC BLACK Pantone 419 C, WEB: #0F0F0F", with a separate Secondary section (gold etc.) and a further Neutral section holding White (#FFFFFF). Corrected candidate''s orange (#F47920) and black (#000000) to the true stated primary pair; dropped candidate''s fabricated white, which the page places in the Neutral tier, not Primary.'
    ),
    (
      'abilene-christian-university',
      '222178',
      array['#4F2170','#FFFFFF']::text[],
      'https://acu.edu/wp-content/uploads/2024/10/ACU_Branding-and-Editorial-style-guide.pdf',
      'high',
      'Candidate''s Widen collective embed URL 404s. Found ACU''s current branding PDF at a live acu.edu path instead, which pdftotext''d cleanly: "Color is one of the most important elements of the ACU brand and graphic identity program. Purple (Pantone or PMS 268) and white are the university''s official colors." ACU PURPLE HEX #4F2170; WHITE HEX #FFFFFF. A separate Secondary section lists Aqua and Gray, and Black/Silver appear only as seal/embroidery options, not part of the 2-color official statement. Confirmed candidate''s purple and white exactly; dropped candidate''s fabricated gray (#C4C6C8, no match anywhere in the document).'
    ),
    (
      'bryant-university',
      '217165',
      array['#A98F42','#000000','#FFFFFF']::text[],
      'https://info.bryant.edu/sites/info/files/docs/Bryant_Brand_Guide_7_29.pdf',
      'high',
      'Candidate''s bryantbulldogs.com athletics info-hub page has no colors content. Found Bryant''s current (7/29/24) institutional Creative Brand Guidelines PDF instead: "The logos should only appear in white, black, or Bryant Gold and with sufficient contrast..." and a full palette breakdown naming the base swatch "Bryant Gold" / "Gold 400" at HEX #A98F42 (PANTONE 872), with the ramp''s terminal shade confirming pure Black #000000. Corrected candidate''s gold (#B09863, no match) and dark neutral (#231F20, no match) to the true stated hexes; confirmed white, all three matching the document''s own "white, black, or Bryant Gold" usage rule.'
    ),
    (
      'point-loma-nazarene-university',
      '121309',
      array['#0E553F','#9B8542']::text[],
      'https://www.pointloma.edu/offices/marketing-office/brand-center/identity-standards',
      'high',
      'Candidate''s plnusealions.com athletics PDF is bot-walled (JS shell on both live fetch and every Wayback capture). Found PLNU''s current official Identity Standards page instead: "It is preferred that the logo appear in two colors: Point Loma Green PMS 343 and Point Loma Gold PMS 4505... Point Loma Green HEX: #0E553F... Point Loma Gold HEX: #9B8542." Confirmed candidate''s green exactly; corrected candidate''s gold (#FDB827, no match anywhere) to the true stated #9B8542. Dropped candidate''s fabricated white (not part of the stated 2-color preferred logo pair).'
    ),
    (
      'colgate-university',
      '190099',
      array['#821019','#FFFFFF','#000000']::text[],
      'https://s3.amazonaws.com/gocolgateraiders.com/documents/2020/10/14/Colgate_Guidelines_Final_LR.pdf',
      'high',
      'S3 PDF 403s directly; recovered via Wayback Machine capture of the same URL. PDF loads and pdftotext''d cleanly: "Presented here is the approved color palette of Colgate Athletics... COLGATE MAROON PMS 202 C, RGB 130/16/25, HEX/HTML 821019" plus a matching Black/White pair, HEX/HTML 000000 and HEX/HTML FFFFFF. Confirmed candidate''s maroon, white, and black exactly as given -- all three have real stated hex in the approved palette.'
    ),
    (
      'molloy-college',
      '193292',
      array['#960423','#FFFFFF']::text[],
      'https://molloylions.com/',
      'medium',
      'Candidate citation is only the athletics homepage; no molloy.edu institutional brand guide or dedicated colors page could be found anywhere. The live molloylions.com site''s own functional theme config gives primary_background #960423, matching the candidate''s maroon exactly. A teamcolorcodes.com secondary index instead lists a visibly different Pantone-derived "Cerise" #992F39 + White as the team''s primary colors. Kept candidate''s #960423 (the site''s own live functional color) and confirmed white, which both sources agree on. Medium confidence: only a functional site-wide color value corroborates the maroon, and it disagrees with the secondary index by a visible amount.'
    ),
    (
      'the-catholic-university-of-america',
      '131283',
      array['#B21F2C','#0A3255']::text[],
      'https://brand.catholic.edu/color/',
      'high',
      'Candidate''s www.catholic.edu/styleguide/identity-standards2.html 403s (as does the communications.catholic.edu mirror). Found CUA''s current, separate brand.catholic.edu guidelines site instead: a "Primary" section listing exactly two swatches, "Catholic Red HEX: #b21f2c" and "Catholic Blue HEX: #0a3255" (a "Secondary" section immediately below holds Bright Red and Bright Blue). Corrected candidate''s red (#990000, no match anywhere in the guide) to the real stated Catholic Red; replaced candidate''s fabricated black with the true second Primary color, Catholic Blue (black/white belong to a separate Neutral tier, not Primary).'
    ),
    (
      'plymouth-state-university',
      '183080',
      array['#135841','#FFFFFF']::text[],
      'https://libanswers.plymouth.edu/faq/26405',
      'medium',
      'Candidate''s campus.plymouth.edu/graphics-resources/logos/ URL redirects to a generic communications-marketing landing page with no color content (client-rendered). Plymouth''s own Lamson Library FAQ states plainly: "What are the school colors for Plymouth State University? ... Green and White." A brandcolorcode.com secondary index''s schema metadata independently states "PSU Green (#135841), White (#FFFFFF), Black (#000000), etc.", matching the candidate''s green and white exactly (a teamcolorcodes.com page for the same team instead lists only Black/Gray/White with no green at all, an inconsistent source not used). Confirmed candidate''s green and white; dropped candidate''s black, which the plymouth.edu FAQ''s own "Green and White" statement does not include.'
    ),
    (
      'bemidji-state-university',
      '173124',
      array['#004D44','#002144']::text[],
      'https://www.bemidjistate.edu/offices/communications_marketing/design/visual_identity_standards/visual_identity_standards.pdf',
      'high',
      'Candidate PDF 404s on live bemidjistate.edu (confirmed via CDX search: the same path was a real hosted PDF from 2010-2016 and started 404ing after a later site migration); recovered a 2016 Wayback capture of the actual PDF file. PDF loads and pdftotext''d cleanly: "University Color Palette / BSU logo Colors / PMS Green 3305 ... RGB: R00-G77-B68 (#004d44) / PMS Blue 289 ... RGB: R0-G33-B68 (#002144)". Confirmed candidate''s green exactly; corrected candidate''s fabricated white/black to the real second official color, Blue #002144 (a separate "BSU Beaver Icon Colors" section with a brown/tan swatch is specific to the beaver mascot icon, not the University Color Palette).'
    ),
    (
      'davenport-university',
      '169479',
      array['#EE3124','#2D2A26','#54565B']::text[],
      'https://www.davenport.edu/branding/colors',
      'high',
      'Candidate''s dupanthers.com athletics PDF is bot-walled (JS shell on both live fetch and every Wayback capture). Found Davenport''s official institutional brand page instead: "There are four primary colors at the forefront of Davenport University -- red, black, dark gray, light gray... Red PMS 485 HEX ee3124, Black PMS Black HEX 2d2a26, Dark gray PMS Cool Gray 11 HEX 54565b, Light gray PMS Cool Gray 3 HEX C8C7C7." Corrected candidate''s red (#D5160C) and black (#000000) to the real stated hexes; dropped candidate''s fabricated white and, to stay within the 3-value cap, dropped the fourth-ranked Light Gray in favor of the top three officially-named primary colors.'
    ),
    (
      'endicott-college',
      '165699',
      array['#00325D','#007C57','#FFFFFF']::text[],
      'https://www.endicott.edu/about/key-offices-departments/communications-and-marketing/communications-and-marketing-policies-guidelines/branding-guidelines',
      'high',
      'Page loads and states plainly: "Brand Colors / Primary Core Palette / Navy, green, and white are the official colors of Endicott College... Navy Blue PMS 540 HEX #00325D... Green PMS 341 HEX #007C57... White HEX #FFFFFF", followed by a separate Expanded Core Palette explicitly not meant to replace the core three. Nudged candidate''s navy (#00325B) and green (#007C5A) to the exactly-stated hexes; confirmed white, which the page explicitly names as one of only 3 official colors.'
    ),
    (
      'college-of-the-holy-cross',
      '166124',
      array['#602D89']::text[],
      'https://brand.holycross.edu/color',
      'high',
      'Candidate''s holycross.edu identity-style-guidelines page is a general landing page with no color content; found the college''s actual brand.holycross.edu color page instead, which embeds its full page-builder data (including hex) in inline JSON: "The primary palette consists of the core colors that define our identity. It builds on the established value of Holy Cross Purple and expands the range to include additional neutrals and a deep purple." -- Holy Cross Purple hex #602D89 (PMS 2607U/268C), explicitly the singular defining brand color; Deep Purple, White, and green/blue/yellow "expanded" tints are named neutrals/expansion, not a second Primary chromatic partner. Dropped candidate''s white and black entirely (white is only a generic design-tool default with no stated brand role; black doesn''t appear as a named swatch) in favor of the single, clearly-stated core color.'
    ),
    (
      'rider-university',
      '186283',
      array['#9D2235','#000000','#FFFFFF']::text[],
      'https://www.rider.edu/about/offices-services/university-marketing-communications/policies-guides-manuals/graphic-standards-manual',
      'high',
      'Candidate''s old news-graphic_standards_manual.pdf URL 404s. Found Rider''s current Graphic Standards Manual page instead; its "Institutional Colors" section embeds an image (not text) of the color chart, so downloaded and viewed the image directly. The image''s own printed text reads: "RIDER CRANBERRY / PANTONE 201 C / HEX# 9D2235", "BLACK / PANTONE BLACK 6 C / HEX# 000000", "WHITE / HEX# FFFFFF" -- read from the printed labels, not eyedropped from the swatch fills. Corrected candidate''s cranberry (#981E32, no match) to the real printed #9D2235; confirmed black and white as the complete 3-color set. Dropped candidate''s fabricated gray (#6C6F70, not part of this set).'
    ),
    (
      'western-oregon-university',
      '210429',
      array['#E31837','#FFFFFF']::text[],
      'https://wou.edu/marcom/files/2017/03/Identity_Guide.pdf',
      'high',
      'Candidate''s original institutional_identity_guide.pdf path 404s; found the current identity guide at a live sibling wou.edu/marcom path. PDF loads and pdftotext''d cleanly: "PRIMARY COLORS / The colors directly below are the official primary colors... PMS 186 (WOU red) RGB 227 24 55 / White RGB 255 255 255", followed by a separate "SECONDARY COLORS" section holding "Black (WOU black) RGB 35 31 32". RGB(227,24,55) converts exactly to candidate''s stated #E31837; confirmed white. Dropped candidate''s black (which does match the document''s RGB exactly) because the document itself explicitly places it in the Secondary tier, not Primary.'
    ),
    (
      'st-olaf-college',
      '174844',
      array['#000000','#CC8A00']::text[],
      'https://pages.stolaf.edu/wp-content/uploads/sites/1119/2017/08/Identity-System.pdf',
      'low',
      'CORRECTED DURING QA: downgraded medium -> low. Candidate''s original pages.stolaf.edu URL 500s; recovered the current version of the same document at wp.stolaf.edu/communications/files/2021/06/Identity-System_21.pdf. It states: "The logo should appear in black and gold whenever possible... The following are the one-color options approved for the logo and text: PMS 131, black and white" -- but gives no literal hex or RGB anywhere in 25 pages, only Pantone. Cross-checked a second official document (Typography-and-Color.pdf), whose extended color system independently confirms "Manitou Heights" as PMS 131 (the same gold) -- also Pantone-only. #CC8A00 is a third-party Pantone-to-hex conversion, not a hex the college itself states -- per the brief''s own source-priority tiers, an off-domain secondary-reference hex is tier 4 (reputable secondary index), which is low confidence, not medium; the original pass miscalibrated this. Black (#000000) is confirmed as the plain, unqualified "black" named alongside gold in the official document.'
    ),
    (
      'fort-lewis-college',
      '127185',
      array['#004B8D','#FDBB2D']::text[],
      'https://www.fortlewis.edu/module/style/color',
      'high',
      'Candidate''s fortlewis.edu/Portals/119/Docs/supclr.pdf 404s. Found FLC''s current color page instead (an oddly-named CMS URL, but the real, live official page): "Primary Palette / The blues and gold of Fort Lewis College''s primary color palette are an important feature of the school''s brand... Bright Blue PMS285 #0074B8 / Dark Blue PMS288 #004B8D / Gold PMS1235 #FDBB2D / White #ffffff / Black #000000", followed by a separate Secondary Palette. Corrected candidate''s navy (#000066) to the real stated Dark Blue #004B8D, and gold (#FFCC33) to the real stated #FDBB2D. Dropped candidate''s fabricated white, and did not carry over the document''s second official blue (Bright Blue #0074B8) to stay within a 2-hex chromatic pair -- flagging this second blue for human review.'
    ),
    (
      'minnesota-state-university-moorhead',
      '174358',
      array['#C8102E','#FFFFFF','#544F47']::text[],
      'https://www.mnstate.edu/contentassets/f3eaf0b8fcae421394300e163caef547/moorhead-brand-guide.pdf',
      'high',
      'Candidate''s issuu.com/msumoorhead/docs/visual_identity is an old scan; found MSUM''s current (May 2025) official Visual Identity and Graphic Standards PDF instead, hosted directly on mnstate.edu. It states: "The primary color for Moorhead is RED... Pantone PMS 186, Web #c8102e" and, more fully, "PRIMARY COLOR PALETTE / The primary color palette contains the three colors in the Minnesota State Moorhead visual system: primarily White, Red and Gray" with an explicit web-colors table: "White: #ffffff; Red: #c8102e; Gray: #544f47." Corrected candidate''s red (#A6192E) and gray (#2D2926) to the exactly-stated hexes; confirmed white, one of an explicit 3-color Primary Color Palette.'
    ),
    (
      'wesleyan-university',
      '130697',
      array['#D72331','#1A1919']::text[],
      'https://www.wesleyan.edu/communications/styleguide/visualstyle.html',
      'medium',
      'Page loads and states "COLOR PALETTE / Our primary colors are Cardinal Red and Black Squirrel," but gives no hex or RGB anywhere on the page (checked linked site CSS files for a named "cardinal"/"squirrel" custom property too -- none found). Corroborated via teamcolorcodes.com: "Wesleyan University Cardinals Primary Colors ... BLACK PMS Black 6 C Hex #1A1919 ... RED PMS 1795 C Hex #D72331." Nudged candidate''s red (#D72121) and black (#000000) to the corroborated values; dropped the secondary index''s near-white and kept the genuine 2-color pair matching the official page''s own statement (only two colors named, no white). Medium confidence: official page names the colors but states no hex.'
    ),
    (
      'missouri-southern-state-university',
      '178341',
      array['#006937','#F6CE3D']::text[],
      'https://www.mssu.edu/university-relations-marketing/MSSU_BrandGuide.pdf',
      'high',
      'Candidate''s June-2021 brand-guide URL 404s; found the current (revised 10-23-25) MSSU Brand Guide at a live sibling mssu.edu path. PDF loads and pdftotext''d cleanly: "COLOR PALETTE / COLOR BREAKDOWNS / GREEN GOLD WHITE GRAY BLACK ... Hex# 006937 f6ce3d ffffff c8c8c8 171717." A companion MSSU brand policy PDF independently defines the "MSSU official color palette" as exactly these five colors with no further primary/secondary split. Corrected candidate''s green (#006338) and gold (#F6CF3F) to the precisely-stated hexes. Dropped white/gray/black to stay within a 2-chromatic pair (green and gold are the pairing the school''s own wordmark description leads with).'
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
