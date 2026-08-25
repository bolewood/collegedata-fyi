-- Batch 7 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Most candidate citation URLs had rotted (dead S3/sidearm/wixstatic PDFs,
-- 403/404s, retired subdomains, JS-rendered brand portals) or turned out to
-- be image-only PDFs with no extractable text. Every school below was
-- re-sourced against the school's own current official domain where
-- possible, verified by downloading PDFs and running pdftotext -layout
-- (never trusting a fetch-tool summary of a PDF), or by reading the raw
-- HTML/CSS/SVG text of an official page.
--
-- Real, non-trivial hex corrections (official value differs meaningfully
-- from the Wikipedia candidate, not just a formatting fix): florida-gulf-
-- coast-university (green and blue both drifted to the current 2026 brand
-- guide's values), university-of-north-florida (Osprey Blue and Osprey Gray
-- both corrected), university-of-memphis (Memphis Blue corrected; gray
-- confirmed near-exact), bowling-green-state-university-main-campus
-- (orange corrected from FF7300 to the university's own policy-stated
-- FD5000; brown confirmed exact), university-of-vermont (Catamount Green
-- and Gold both corrected -- the candidate's green, #005710, turned out to
-- be a plausible-looking but wrong hex; the real Catamount Green, #154734,
-- was independently found to be candidate PSU's WRONG swatch, see below),
-- loyola-university-chicago (maroon and gold both corrected to the current
-- official values), university-of-miami (orange corrected; green
-- confirmed exact), university-of-nebraska-at-omaha (red corrected from
-- D71920 to the on-domain SVG's own D72027; black confirmed as the
-- explicitly-named primary color), and northern-illinois-university (red
-- and black both corrected from off-shade candidate values; white
-- confirmed via an explicit "foundation of our palette" statement).
--
-- Wrong-school / wrong-swatch pulls caught this batch (the candidate hex
-- was real, but for a DIFFERENT institution than the one it was attached
-- to): cuny-new-york-city-college-of-technology (candidate cited
-- ccny.cuny.edu -- City College of New York, a different CUNY college
-- entirely -- not City Tech's own site; corrected to City Tech's real
-- blue/orange), new-mexico-state-university-main-campus (candidate's hex
-- #7E141B is literally Middle Tennessee State's crimson swatch from the
-- same Conference USA multi-school PDF, printed on the immediately
-- preceding page; corrected to NMSU's own Aggie Crimson, #8C0B42, from
-- brand.nmsu.edu), and portland-state-university (candidate's hex
-- #154734 is the University of Vermont's own official Catamount Green,
-- not a PSU color at all; corrected to PSU's real Green/Electric Green).
--
-- Confirmed as-is (candidate hex matched the current official source,
-- modulo dropping a non-primary third value): drexel, university-at-
-- albany, university-of-louisiana-at-lafayette, university-of-alabama-at-
-- birmingham, rochester-institute-of-technology (all three candidate
-- values confirmed, re-pointed to a working on-domain PDF citation).
--
-- Reduced to fewer/different values than the candidate where the official
-- source named fewer or different official colors, usually dropping a
-- mechanically-attached white/black that the real source doesn't call
-- primary, or promoting the source's own explicit pairing over the
-- candidate's assumed one: tarleton-state-university (candidate's black
-- swapped for the official page's actual second color, white), western-
-- kentucky-university (candidate's black dropped in favor of the guide's
-- own "Colors: Red & White" quick-reference statement), university-of-
-- massachusetts-lowell (candidate's red DROPPED despite having its own
-- hex in the source table -- the source's lead sentence explicitly demotes
-- red to "strictly an accent color", not one of the two official colors),
-- indiana-university-indianapolis (candidate's gold, not found anywhere,
-- replaced with the official guide's actual stated Cream hex), eastern-
-- kentucky-university (candidate's gray dropped as a generic WordPress
-- theme neutral, not an EKU-specific named color; maroon confirmed via an
-- on-domain CSS custom property), and california-state-university-chico
-- (candidate's unofficial basketball-media-guide hexes replaced entirely
-- with the two named colors from the official style guide).
--
-- Kept white as a real third/second primary where the official source
-- explicitly names it among only 2-3 primary colors (not a mechanical
-- append): florida-gulf-coast-university, western-washington-university,
-- northern-illinois-university, tarleton-state-university, western-
-- kentucky-university, university-of-louisiana-at-lafayette, new-mexico-
-- state-university-main-campus, eastern-kentucky-university, university-
-- of-massachusetts-lowell, oakland-university.
--
-- Lower-confidence outcomes: post-university and minnesota-state-
-- university-mankato (official sites had no extractable hex text at all --
-- one a bare asset-download page, the other palette-as-image-only PDF/page
-- -- confirmed only via a reputable secondary team-color index, low
-- confidence); kean-university (official guide names colors by Pantone
-- only, no hex anywhere; blue hex corroborated via consistent on-domain
-- CSS usage, medium confidence, reduced to the one corroborated chromatic
-- value); oakland-university (official page names three colors by Pantone
-- with no stated hex; gold hex corroborated via two independent secondary
-- sources plus the school's own athletics site config, medium confidence).
--
-- Left null: cuny-john-jay-college-of-criminal-justice. The current
-- official 2023 branding PDF is an InDesign export composed entirely of
-- JPEG2000 images with zero extractable text; its own embedded XMP swatch
-- names (PANTONE 2768 U / 280 C) directly conflict with the Pantone
-- numbers given by a secondary team-color index (PMS 648 / 7688), and the
-- candidate's own hexes matched neither. Recorded the search rather than
-- guessing between conflicting sources.
--
-- Plates are still derived at render (deriveInks() / glyphInks()); this
-- stores source hexes only. Every finalized pair/triple was run through
-- production deriveInks()/glyphInks() (paper #f1ece1, MIN_B_ON_CREAM=1.25):
-- none fell through to the house-ink path, so no real chromatic primary was
-- lost to a fallback in this batch (some official neutrals, e.g. Oakland's
-- black/white and Omaha's black, are algorithmically rejected as "neutral"
-- by deriveInks' own chroma threshold when paired with a single chromatic
-- color -- that's the engine's existing single-ink behavior, not a data
-- loss). See data/brand-colors/batch-7-2026-08-24.jsonl for the full
-- per-school record, including the null John Jay entry.

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
      'florida-gulf-coast-university',
      '433660',
      array['#009366', '#004685', '#FFFFFF']::text[],
      'https://www.fgcu.edu/advancement/universitymarketing/resources/files/brandingguidelines-4-29-2026-ada.pdf',
      'high',
      'Candidate''s 2017 visual-identity PDF 404s; found and text-extracted the current (dated April 2026) official Branding Guidelines PDF linked from the live branding-guidelines page instead. ''Our primary colors are Emerald Green and Cobalt Blue and White'' -- Emerald Green HEX #009366 and Cobalt Blue HEX #004685, both meaningfully drifted from the 2017 candidate''s #00794C and #004785 (same families, updated values); White #FFFFFF kept because the page explicitly names it as one of three primary colors, not a mechanical append.'
    ),
    (
      'indiana-university-indianapolis',
      '151111',
      array['#990000', '#EDEBEB']::text[],
      'https://licensing.iu.edu/doc/iu-promotional-style-guide.pdf',
      'high',
      'Candidate''s brand.iu.edu/apply/color.shtml and the successor www.iu.edu color pages both 404 (IU''s brand microsite is mid-restructure post-IUPUI split); found and text-extracted the current official IU Licensing & Trademarks Promotional Products Style Guide PDF instead, which applies system-wide including Indiana University Indianapolis. ''Cream and crimson are key components of the IU brand... Crimson is the visual anchor'' -- Crimson HEX #990000 (exact match to candidate) and Cream HEX #EDEBEB. Corrected: the candidate''s third value #F1BE48 (a gold) does not appear anywhere in the official guide and was dropped in favor of the actual stated Cream hex.'
    ),
    (
      'california-state-university-chico',
      '110538',
      array['#9D2235', '#75787B']::text[],
      'https://www.csuchico.edu/style-guide/visual/colors.shtml',
      'high',
      'Candidate cited an unofficial 2016-17 basketball media guide PDF, not a brand source. Found the official Chico State style guide instead: ''Chico Red, Cornerstone Gray, Black, and White comprise Chico State''''s primary color palette... Chico Red should be the most prominent color.'' Chico Red HEX #9D2235 and Cornerstone Gray HEX #75787B kept as the two named chromatic/near-chromatic primaries; Black and White dropped per the chromatic-preference default (the page frames them as balancing neutrals, not a distinct hue). Substantial correction from the candidate''s unofficial #952945/#AAAAAB, which don''t match Chico State''s actual official values.'
    ),
    (
      'post-university',
      '130183',
      array['#5B254B', '#F47216']::text[],
      'https://teamcolorcodes.com/post-eagles-color-codes/',
      'low',
      'Candidate''s post.edu/branding/ page is real (title: ''Post University | Branding Style Guide'') but contains only downloadable logo asset files -- no stated hex, Pantone, or CMYK anywhere in the page text. No other official post.edu brand/colors subpage or PDF was found. Fell back to a reputable secondary team-color index per source-priority tier 4: ''The Post Eagles colors are purple and orange... Purple PMS 7652C Hex #5B254B... Orange PMS 158C Hex #F47216,'' differing somewhat from the candidate''s #5E2750/#FF8200 (same families, different exact values). Low confidence: no official on-domain hex was ever found.'
    ),
    (
      'cuny-new-york-city-college-of-technology',
      '190655',
      array['#007FA3', '#E17800']::text[],
      'https://www.citytech.cuny.edu/communications/branding-guide.aspx',
      'high',
      'Candidate''s citation was the WRONG SCHOOL: ccny.cuny.edu is the style guide for City College of New York, a different CUNY senior college, not New York City College of Technology (''City Tech'') -- and its candidate hexes (#7D55C7 purple, #000000, #595959) don''t resemble City Tech''s real palette at all. Found and confirmed City Tech''s own branding-guide page: ''City Tech''''s color palette... The primary blue and orange should be used in most applications'' -- Blue Pantone 314C HEX #007FA3 and Orange Pantone 152C HEX #E17800. Both values read directly from the citytech.cuny.edu page text.'
    ),
    (
      'western-washington-university',
      '237011',
      array['#003F87', '#007AC8', '#FFFFFF']::text[],
      'https://designsystem.wwu.edu/colors',
      'high',
      'Candidate''s cstv.com athletics logo-sheet PDF 404s and its hexes (#0E2B58, #7898C9) don''t match anything found. Found the current official WWU design system colors page instead: ''Main Colors -- These should be the most prominent colors in a design, comprising about 90% of the visual space'' -- Dark Blue #003F87 (~20%), Light Blue #007AC8 (~20%), White #FFFFFF (~50%), all three explicitly grouped under the ''Main Colors'' heading (white is not a mechanical append here -- it''s named alongside the two blues as part of the same 90%-of-design primary set). Green/yellow/red/black/gray sit under a separate ''Accent Colors'' (10%) heading and were dropped.'
    ),
    (
      'university-of-rhode-island',
      '217484',
      array['#002147', '#D0A627']::text[],
      'https://web.uri.edu/business/wp-content/uploads/sites/1235/URI-Branding-style-guide.pdf',
      'high',
      'Candidate''s gorhody.com S3 PDF downloads as an 18-page image-only Adobe Acrobat export with zero extractable text (confirmed via pdftotext -- vector/scanned swatches only), so its hexes (#68ABE8, #041E42) could not be verified and don''t appear in any text-based source found. Found and text-extracted a different, text-based URI Brand Visual Standards Guide PDF on the uri.edu domain: ''Primary Brand Colors... Blue is the dominant color accompanied by gold as an accent color'' -- PMS 282 Blue HEX #002147, and ''Yellow PMS 110 can be used as an alternate in place of Metallic Gold PMS 872'' with PMS 110 HEX #D0A627 (metallic gold itself has no RGB/hex equivalent, so the guide''s own stated digital substitute was used).'
    ),
    (
      'university-of-north-florida',
      '136172',
      array['#003886', '#A7A8A9']::text[],
      'https://www.unf.edu/brand/colors.html',
      'high',
      'Candidate''s Official_Athletic_Logos_and_Identifying_Marks.aspx page 404s. Found the official UNF Color Palette page instead: ''UNF''''s official school colors are blue and gray... Primary Colors -- Osprey Blue... supported by Osprey Gray. Together these two make up the primary foundation of our palette.'' Osprey Blue PMS 288C HEX #003886 and Osprey Gray PMS Cool Gray 6C HEX #A7A8A9 -- both corrected from the candidate''s #00246B and #D9D9D9 (real values are meaningfully different from both candidate hexes); white dropped (not one of the two named primary colors).'
    ),
    (
      'drexel',
      '212054',
      array['#07294D', '#FFC600']::text[],
      'https://drexel.edu/identity/drexel/color',
      'high',
      'Candidate''s drexel.edu/identity/web/colors/ page 404s (URL restructured); found the current drexel.edu/identity/drexel/color page and confirmed directly in its text: ''Drexel Blue -- Pantone 294C / HEX #07294D'' and ''Drexel Gold -- Pantone 7548C / HEX #FFC600,'' both exact matches to the candidate''s first two values. White (candidate''s third) dropped -- not named alongside Blue/Gold on this page.'
    ),
    (
      'rochester-institute-of-technology',
      '195003',
      array['#F76902', '#FFFFFF', '#000000']::text[],
      'https://www.rit.edu/brandportal/sites/rit.edu.brandportal/files/documents/rit-link-style-guide.pdf',
      'high',
      'Candidate''s rit.edu/marketing/brandportal/brand-elements/colors page 404s (confirmed via direct fetch) and the Brand Portal itself is a JS-rendered SPA with no static color text. Found and text-extracted an official on-domain RIT web link-style-guide PDF instead, which repeatedly and explicitly labels RIT''''s orange as ''("Primary") #F76902'' across multiple background-color tables, alongside #FFFFFF and #000000 as the paired background/text options -- exact match to all three candidate values, so confirmed as-is with a re-pointed citation.'
    ),
    (
      'portland-state-university',
      '209807',
      array['#6D8D24', '#CFD82D']::text[],
      'https://www.pdx.edu/university-communications/tools-and-templates/brand-colors',
      'high',
      'Candidate''s sidearmsports S3 ID-manual PDF 404s. Its candidate hex #154734 is, in fact, a completely different school''''s color -- the University of Vermont''''s official ''Catamount Green'' -- confirming this was a wrong-swatch pull, not a stale-but-related PSU value. Found the official PSU brand-colors page instead: ''Primary Pallet -- These colors are the dominate colors of the PSU brand. The PSU Green and/or Electric Green should be used strategically and be present across all communications'' -- PSU Green PMS 7496 HEX #6D8D24 and Electric Green PMS 389C HEX #CFD82D. Forest Green and Purple also sit in the Primary Pallet but weren''''t singled out the way these two were, so kept to the two named ''strategic'' colors.'
    ),
    (
      'university-of-miami',
      '135726',
      array['#005030', '#F47321']::text[],
      'https://ucomm.miami.edu/_assets/pdf/tools-and-resources/umiami-visual-identity-guide.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''The primary colors for the University of Miami visual identity system are Miami orange (Pantone 158) and Miami green (Pantone 3435)'' -- Miami Green HEX #005030 (exact match to candidate) and Miami Orange HEX #F47321 (corrected from the candidate''''s #F05A00, which doesn''''t appear in the guide). White (candidate''''s third value) dropped -- only two colors are named as primary.'
    ),
    (
      'bowling-green-state-university-main-campus',
      '201441',
      array['#FD5000', '#4F2C1D']::text[],
      'https://www.bgsu.edu/policies/marketing-brand-strategy/3341-10-4.html',
      'high',
      'Candidate''s bgsufalcons.com athletic-brand-standards page only exposed generic Sidearm-template chrome hexes shared across many unrelated schools'' sites, not BGSU-specific values -- so it was not treated as a reliable source. Found BGSU''s own official university policy ''3341-10-4 The Official Identity Colors'' instead: ''The primary identity color of BGSU is orange... HTML # fd5000'' and ''The secondary identity color of BGSU is brown... HTML color # 4f2c1d.'' Brown matches the candidate exactly; Orange corrected from the candidate''s #FF7300 (a materially different, more yellow shade) to the policy''s stated #FD5000. White (candidate''s third) dropped -- the policy frames black/white only as substitutes, not primary/secondary colors.'
    ),
    (
      'university-of-memphis',
      '220862',
      array['#003087', '#898D8D']::text[],
      'https://www.memphis.edu/communications/brand/colors.php',
      'high',
      'Candidate''s gotigersgo.com athletic-brand-standards page again only exposed generic Sidearm-template chrome, not Memphis-specific values. Found the official memphis.edu Brand Colors page: ''Our blue and gray color palette... Primary Colors -- Memphis Blue (PMS 2945C)... Memphis Gray (PMS 422C)'' -- named correctly but the page shows the actual hex only as an embedded image, not text, so per the never-eyedrop rule the hex was instead confirmed via the on-domain stylesheet linked from that same page (memphis.edu/_resources/css/colors.css): ''--university-blue: #003087; --university-gray: #898D8D.'' Blue corrected from the candidate''s #004991; gray is nearly identical to the candidate''s #8E908F (confirmed, tiny rounding difference). White dropped -- only blue and gray are named as the official pair.'
    ),
    (
      'tarleton-state-university',
      '228529',
      array['#4F2D7F', '#FFFFFF']::text[],
      'https://www.tarleton.edu/brand/university-colors/',
      'high',
      'Candidate''s 2014 tarletonsports.com media-relations page is stale but still resolves; its embedded site_colors JSON independently confirmed primary_background #4F2D7F, matching the candidate''s purple exactly. Cross-checked against the official tarleton.edu University Colors page: ''The official university colors are purple and white'' under a ''PRIMARY COLORS'' heading, with Teal/Black/Gray/Lavender under a separate ''ACCENT AND SECONDARY COLORS'' heading. Purple #4F2D7F kept (exact match); corrected the candidate''s third value from black (#000000) to white (#FFFFFF) -- white, not black, is the real second official color.'
    ),
    (
      'university-at-albany',
      '196060',
      array['#46166B', '#EEB211']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/ualbanysports.com/documents/2023/1/30/2023_UAlbany_Athletics_Brand_Guide.pdf',
      'high',
      'PDF fetched and text-extracted directly; confirmed as-is. ''Purple and Gold are considered the official colors of UAlbany. Additionally, White, Gray and Black may be utilized in conjunction with the athletics brand'' -- Purple #46166B and Gold #EEB211, exact matches to the candidate''s first two values. White (candidate''s third) dropped -- explicitly framed as usable-but-secondary, not one of the ''official colors.'''
    ),
    (
      'university-of-louisiana-at-lafayette',
      '160658',
      array['#CE181E', '#FFFFFF']::text[],
      'http://ocm.louisiana.edu/sites/communicationsandmarketing/files/Brand_Culture_Guide_July2015.pdf',
      'high',
      'PDF fetched and text-extracted directly (first attempt truncated mid-download at ~5MB of a 10.7MB file; re-fetched in full over HTTPS). ''The official school colors are vermilion (red) and white'' -- Official Colors table: Pantone 186 HEX ce181e and White HEX FFFFFF, both exact matches to the candidate''s first two values. Corrected: dropped the candidate''s near-black third value #0A0203 -- the guide explicitly places black under a separate ''Secondary Colors'' heading (''Black is only to be used as a secondary color''), not among the official colors.'
    ),
    (
      'oakland-university',
      '171571',
      array['#B59A57', '#000000', '#FFFFFF']::text[],
      'https://www.oakland.edu/ucm/merchandising/',
      'medium',
      'Candidate''s goldengrizzlies.com athletics-branding-guidelines page 404s; its embedded site_colors JSON (still served on the 404 template) gives primary_background #87733B and secondary_text #B59A57, both gold-family but not identical. Found the official oakland.edu merchandising/licensing page instead: ''Official Oakland University Colors are Pantone 465 Gold, Black and White'' -- three colors named, matching the candidate''s structure and confirming Black/White as legitimately primary (not a mechanical append). No hex is stated for Pantone 465 on any oakland.edu page found; used #B59A57, independently corroborated both by a reputable secondary team-color index (labeled there as Pantone 872 Metallic Gold, a different but closely related Pantone) and by the school''s own athletics site JSON config. Medium confidence: gold''s exact hex is corroborated but not directly stated on an official page; Black and White are confirmed as-is from the official page text.'
    ),
    (
      'eastern-kentucky-university',
      '156620',
      array['#861F41', '#FFFFFF']::text[],
      'https://www.eku.edu/in/guides/branding-information/',
      'high',
      'Candidate''s issuu.com-hosted 2023 Brand Guide is a JS-rendered flipbook with no extractable page text. Found EKU''s own branding-information page instead: its site-wide WordPress theme exposes an on-domain CSS custom property explicitly named ''--wp--preset--color--eku-maroon: #861f41'' (also aliased to the theme''s --primary token), an exact match to the candidate''s maroon. White #FFFFFF kept as the well-established second color (''Maroon and White''); dropped the candidate''s third value #87909A, which traces only to the WordPress theme''s generic ''--lightgray'' preset, not an EKU-specific named color.'
    ),
    (
      'western-kentucky-university',
      '157951',
      array['#B01E24', '#FFFFFF']::text[],
      'https://www.wku.edu/marketingandcommunications/documents/wku-communication-and-branding-manual-2018-digital.pdf',
      'high',
      'PDF fetched and text-extracted directly. The manual''s ''WKU Colors*'' section lists four colors with formulas (Red WEB B01E24, Black WEB 000000, White, Gray WEB 333333) with no explicit primary/secondary ranking, but a separate quick-reference fact sheet in the same document states plainly ''Colors: Red & White.'' Kept Red #B01E24 (exact match to candidate) and White #FFFFFF per that explicit two-color designation; dropped the candidate''s third value Black -- Black and Gray are logo/web-palette colors, not part of the stated ''Red & White'' pair.'
    ),
    (
      'new-mexico-state-university-main-campus',
      '188030',
      array['#8C0B42', '#FFFFFF']::text[],
      'https://brand.nmsu.edu/color/index.html',
      'high',
      'Candidate''s citation is a Conference USA multi-school brand-ID PDF, not an NMSU source. Text-extracted it directly and found the candidate''s hex #7E141B is actually printed on the immediately PRECEDING page under the header ''MIDDLE TENNESSEE'' (PMS 208 Crimson) -- a wrong-swatch pull from a different conference member entirely, not New Mexico State''s own color. New Mexico State''s own page in that same PDF (page 18, confirmed via alphabetical page-number sequence) lists Orange HEX F56423 and White, which also don''t match the candidate. Went to NMSU''s own official brand site instead: ''Our core brand colors of crimson and white...Aggie Crimson is our main identifier'' -- Aggie Crimson RGB 140/11/66 HEX #8C0B42 (PMS 208, same Pantone number as the Middle Tennessee swatch but a different hex) and White Sands HEX #FFFFFF.'
    ),
    (
      'university-of-vermont',
      '231174',
      array['#154734', '#FFD100']::text[],
      'https://www.uvm.edu/stratcomm/brand/color-palette',
      'high',
      'Candidate''s uvm.edu/sites/default/files/StyleGuideAthletics.pdf 404s. Found the current official UVM brand color-palette page instead: ''UVM''''s primary colors, Catamount Green and Gold, embody the spirit of our institution... They are the most iconic and important in our brand and should be the dominant colors'' -- Catamount Green PANTONE 3435C HEX #154734 and Gold PANTONE 109C HEX #FFD100. Both corrected from the candidate''''s #005710 and #FFC20E (different, non-matching shades); White (candidate''''s third) dropped -- not one of the two named primary colors.'
    ),
    (
      'loyola-university-chicago',
      '146719',
      array['#5A0722', '#EAAA00']::text[],
      'https://www.luc.edu/umc/brandidentity/brandcomponents/colors/',
      'high',
      'Candidate''s sidearmsports S3 athletics style-guide PDF 404s. Found the official luc.edu brand-identity colors page instead: ''Identity Colors -- These primary colors, especially maroon, are at the core of our visual identity... maroon and gold were the colors of the house of Loyola'' -- an embedded usage bar-chart confirms Maroon HEX #5A0722 (50% of usage) and Gold HEX #EAAA00 (25%). Both corrected from the candidate''s #582931 and #FDB913 (different, non-matching shades); White (candidate''s third, 12% in the same chart) dropped as a supporting/whitespace color, not one of the two ''especially maroon'' identity colors called out in the page''s own text.'
    ),
    (
      'minnesota-state-university-mankato',
      '173920',
      array['#480059', '#F7E400']::text[],
      'https://teamcolorcodes.com/minnesota-state-mavericks-color-codes/',
      'low',
      'Candidate''s mnsu.edu/standards/colors/ redirects to a 404. Found the current official mankato.mnsu.edu/brand-hub/design-resources/colors/ page (real, live, title confirmed) and the current official Brand Style Guide PDF, but both present the color palette only as images/graphics with zero extractable hex text (confirmed via pdftotext -- 0 matches). Fell back to a reputable secondary team-color index per source-priority tier 4: ''Maverick Purple PMS 269C Hex #480059'' and ''Maverick Gold PMS 109C Hex #F7E400,'' exact matches to the candidate. Low confidence: candidate confirmed only indirectly -- no official on-domain hex text was ever located.'
    ),
    (
      'university-of-alabama-at-birmingham',
      '100663',
      array['#1A5632', '#FDB913']::text[],
      'https://www.uab.edu/brandguide/university/colors',
      'high',
      'Candidate''s uab.edu/toolkit/uab-brand-refresh landing page had no inline hex; followed a linked path within the same Joomla brand-guide site to the actual University Colors page: ''Primary Colors'' heading lists ''UAB Green -- Pantone 357 -- #1a5632'' and ''UAB Gold -- Pantone 7549 -- #fdb913,'' both exact matches to the candidate''s first and third values. White (candidate''s second value) dropped -- only Green and Gold sit under the ''Primary Colors'' heading.'
    ),
    (
      'cuny-john-jay-college-of-criminal-justice',
      '190600',
      null::text[],
      null,
      null,
      'Candidate''s 2021 jjc_branding_guidelines PDF 404s. Found and downloaded the current official 2023 JJC Branding Guidelines PDF (jjay.cuny.edu/sites/default/files/2023-09/JJC-Branding-Guidelines-2023.pdf) but it is an InDesign export composed entirely of JPEG2000 images with zero extractable text (confirmed via pdftotext -- 0 lines); its embedded XMP metadata only reveals swatch names PANTONE 2768 U and PANTONE 280 C (both dark navy), no RGB/hex. A reputable secondary team-color index states Navy #002D62 (PMS 648C) and Light Blue #5090CC (PMS 7688C) -- but those Pantone numbers directly conflict with the official PDF''s own embedded PANTONE 2768/280 swatches, and the candidate''s own hexes (#232C64, #00AEEF) don''t match any source found. Given the conflicting Pantone references between the one authoritative-but-unreadable source and the secondary index, and no corroborating on-domain text, left null rather than guess. Also checked newserver.jjay.cuny.edu (dead host, no route) and www.jjay.cuny.edu (no colors page found).'
    ),
    (
      'university-of-nebraska-at-omaha',
      '181394',
      array['#000000', '#D72027']::text[],
      'https://www.unomaha.edu/office-of-strategic-marketing-and-communications/online-brand-guide/graphic-styles/index.php',
      'high',
      'Candidate''s unomaha.edu/university-communications/... path redirects to the homepage; found the current official Brand Colors page at its new office path. ''Black is UNO''''s primary brand color... front and center'' and ''Red is UNO''''s accent color'' -- the swatches are SVG images, so per the on-domain-source allowance the SVG source files themselves were fetched and read as text: the black swatch rect has no fill override (default pure black, #000000) and the red swatch uses ''.st0{fill:#D72027;}''. Kept Black (as stated primary) and corrected Red from the candidate''''s #D71920 to the SVG-stated #D72027 (small but real difference); dropped the candidate''''s white -- the page frames white only as one of three interchangeable ''secondary colors'' (with gray), not primary or accent.'
    ),
    (
      'university-of-massachusetts-lowell',
      '166513',
      array['#0067B1', '#FFFFFF']::text[],
      'https://goriverhawks.com/sports/2021/8/18/identity-standards',
      'high',
      'Candidate''s citation resolved directly and cleanly (not dead). ''Blue and White are considered the official colors of UMass Lowell. Additionally, Gray and Black may be utilized in conjunction with the athletics brand, red is strictly an accent color'' -- table gives UMass Lowell Blue HEX #0067B1 (exact match to candidate) and White. Corrected: DROPPED the candidate''s third value, Red #C8102E -- despite being tabulated alongside Blue/White/Gray/Black with its own hex, the page''s own lead sentence explicitly demotes red to ''strictly an accent color,'' not one of the two colors ''considered the official colors.'''
    ),
    (
      'kean-university',
      '185262',
      array['#00305C']::text[],
      'https://www.kean.edu/media/kean-branding-style-guide',
      'medium',
      'Candidate''s 2017 kean.edu/sites/default/files/pdf/... PDF 404s (no Wayback snapshot either). Found and text-extracted the current official Kean University Branding Style Guide PDF instead: ''Kean University''''s colors are blue and silver. Our official primary color... is PMS 540 (Kean Blue)... Supplemental colors... Gray (PMS 430), Light Blue (PMS 543)'' and ''A good CMYK representation of Kean blue is: C100 M70 Y10 K45'' -- no hex/RGB is stated anywhere in the official PDF, only Pantone/CMYK. Corroborated a hex for Kean Blue via kean.edu''''s own site-wide CSS, which consistently uses #00305C across multiple pages (near-identical to the candidate''''s #003057). Dropped the candidate''''s Gray #7C878E and White -- no hex for PMS 430 silver was found stated or corroborated anywhere, and inventing one from the Pantone number would violate the never-invent rule, so reduced to the one corroborated chromatic value. Medium confidence: named by the official guide but hex sourced from on-domain CSS rather than the guide''''s own text.'
    ),
    (
      'northern-illinois-university',
      '147703',
      array['#C8102E', '#000000', '#FFFFFF']::text[],
      'https://www.niu.edu/communication-standards/visual/colors.shtml',
      'high',
      'Candidate''s sidearmsports S3 licensing-style-guide PDF 404s. Found the official niu.edu Brand Colors page instead: ''Our primary brand colors are NIU Red and black. Gray... is used as an accent color'' and, further down, ''NIU Red, black and white are the foundation of our palette and should be used prominently throughout all communications'' -- NIU Red HEX #C8102E (corrected from the candidate''s #BA0C2F) and Black HEX #000000 (corrected from the candidate''s off-black #27251F); White #FFFFFF kept exactly as candidate, now confirmed by the explicit ''foundation of our palette'' framing rather than assumed as a mechanical append.'
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
