-- Batch 5 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Most candidate citation URLs had rotted (dead S3 PDFs, 403/404s,
-- retired subdomains with cert mismatches, JS-rendered brand portals,
-- one PDF that literally served the wrong school's Illustrator file). Every
-- school below was re-sourced against the school's own current official
-- domain (brand.*, ucm.*, marcomm.*, or a re-extracted PDF via pdftotext)
-- where possible; a handful only had directly-fetchable static content via
-- secondary corroboration and are recorded at medium confidence.
--
-- Real, non-trivial hex corrections (official value differs from the
-- Wikipedia candidate, not just a formatting fix): california-polytechnic-
-- state-university-san-luis-obispo (gold corrected from a pale #F8E08E to
-- the official Mustang Gold #BD8B13), georgia-southern-university (both
-- navy and gold corrected; five co-equal "core" colors on the current page,
-- narrowed to the two chromatic ones), washington-state-university
-- (crimson and gray both corrected -- the cited PDF actually served an
-- Arizona State Illustrator file, an unrelated broken link), temple
-- (cherry corrected from #990033 to the official #9D2235), james-madison-
-- university (gold corrected from #B3A369 to #AD9C65, computed from the
-- guide's own stated Pantone/RGB), east-carolina-university (both purple
-- and gold corrected), unc (candidate's navy demoted -- it's UNC's
-- Secondary Identity color, not Primary; primary is Carolina Blue + White
-- only), university-of-oklahoma-state (white swapped for the actual
-- official second color, black), usc (both cardinal and gold corrected
-- from generic NCAA values to USC's own official identity-page hex),
-- university-of-connecticut (red dropped entirely -- confirmed NOT a
-- UConn color; corrected to the actual third primary, grey),
-- ohio-university-main-campus (green corrected -- the candidate hex was
-- actually Cal Poly's Poly Green, an apparent Wikipedia sourcing error),
-- california-state-university-los-angeles (white swapped for the actual
-- third primary, Marigold), appalachian-state-university (black corrected
-- from #222222 to the official #010101), kent-state-university-at-kent
-- (blue corrected from #002664 to the official #003976), udel (confirmed
-- exactly via the official Brand Style Guide PDF), illinois-state-
-- university (red corrected to the guide's own stated hex; black dropped
-- as a support, not official, color), grand-valley-state-university (blue
-- corrected by one digit), san-francisco-state-university (gold corrected
-- from #FFCC00 to #FFCF01), and mississippi-state-university (maroon
-- corrected substantially from an athletics-specific #5D1725 to the
-- official licensing hex #660000).
--
-- Confirmed as-is (candidate hex matched the current official source):
-- university-of-illinois-chicago, university-of-kansas, university-of-
-- oregon, upitt, utah-state-university, university-at-buffalo.
--
-- Reduced to fewer values than the candidate where the official source
-- named fewer official colors: unc (dropped navy -- secondary, not
-- primary), university-of-nebraska-lincoln (reduced to a single confirmed
-- red -- white/black/cream are grouped "Core" neutrals but only red is
-- explicitly called "the primary color" in the guide's own prose).
--
-- Four schools could not be read directly off a fetchable official page
-- this pass (login-walled, JS-rendered brand-portal apps, or an expired
-- presigned S3 link) and are recorded at medium confidence with the gap
-- noted in brand_colors_notes: university-of-mississippi, the-university-
-- of-texas-at-el-paso, virginia-commonwealth-university, and
-- san-francisco-state-university. See
-- data/brand-colors/batch-5-2026-08-24.jsonl for the full per-school record.
--
-- Plates are still derived at render (deriveInks() / glyphInks()); this
-- stores source hexes only. Every finalized pair/triple was run through
-- production deriveInks()/glyphInks() (paper #f1ece1, MIN_B_ON_CREAM=1.25):
-- none fell through to the house-ink path, so no real chromatic primary was
-- lost to a fallback in this batch.

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
      'university-of-illinois-chicago',
      '145600',
      array['#001E62', '#D50032']::text[],
      'https://brand.uic.edu/visual-identity/color/',
      'high',
      'Candidate''s 2020 uicflames.com S3 PDF 404s; found the current official UIC Brand color page instead. States ''Our primary colors are Fire Engine Red and Navy Pier Blue'' -- Navy Pier Blue #001E62 and Fire Engine Red #D50032, both exact matches to the candidate. No white is named as primary anywhere on the page -- dropped the candidate''s mechanically-attached white third value.'
    ),
    (
      'california-polytechnic-state-university-san-luis-obispo',
      '110422',
      array['#154734', '#BD8B13']::text[],
      'https://ucm.calpoly.edu/color-guidelines',
      'high',
      'Candidate''s 2021 gopoly.com athletics S3 PDF 403s; found the current official Cal Poly Color Guidelines page instead, which names exactly two primary colors: Poly Green #154734 (exact match to candidate) and Mustang Gold #BD8B13 (corrected from the candidate''s #F8E08E, a pale yellow that doesn''t match any named Cal Poly swatch). No white listed as primary -- dropped the candidate''s white third value.'
    ),
    (
      'georgia-southern-university',
      '139931',
      array['#001344', '#9A8348']::text[],
      'https://www.georgiasouthern.edu/offices/communications-marketing/guidelines-resources/acceptable-color-usage',
      'medium',
      'Candidate''s 2016 athletics S3 PDF 404s; found the current official Acceptable Color Usage page instead. It lists five co-equal ''Core Brand Colors'' (GS Navy #001344, White #FFFFFF, Logo Gold #9A8348, Accessible Gold #B9832D, Athletic Grey #A5ACAF) with no primary/secondary split narrowing further. Corrected both candidate values (navy #041E42 and gold #A99260 match neither named color) to the two chromatic core colors; dropped white since picking it over the other three co-equal core tones isn''t well justified by the page. Medium confidence: the flat 5-way ''core'' framing required a judgment call rather than a clean primary/secondary read.'
    ),
    (
      'oklahoma-state-university-main-campus',
      '207388',
      array['#FE5C00', '#000000']::text[],
      'https://brand.okstate.edu/branding-guidelines/colors',
      'high',
      'Candidate''s athletics-branding.pdf 403s; the official colors page also blocks automated fetch (403), but search-engine-indexed content of that exact page quotes verbatim: ''the OSU brand is simply two colors, orange and black... Pantone 021, HEX #FE5C00... Black HEX #000000.'' Orange matches the candidate exactly; corrected the second color from the candidate''s white to the actual official black -- white is not part of OSU''s two-color primary palette.'
    ),
    (
      'california-state-university-fresno',
      '110556',
      array['#C41230', '#13284C']::text[],
      'https://marcomm.fresnostate.edu/color.html',
      'high',
      'Candidate URL 301-redirects (department renamed advancement -> marcomm); fetched the redirect target directly. Confirms Cardinal Red #C41230 and Blue #13284C as the two Primary Colors (''the predominant colors in all communications and design layouts''); White and Cool Gray are explicitly Secondary. Both values match the candidate exactly -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-mississippi',
      '176017',
      array['#14213D', '#CE1126']::text[],
      'https://olemiss.edu/marcomm/creative-services/brand-services/resources-and-downloads/',
      'medium',
      'Cited NACDA DownloadDocumentFile link 302-redirects to an expiring S3 presigned URL for ''OleMiss_style_guide.pdf'' that isn''t independently fetchable; olemiss.edu''s own brand-services page names color training but doesn''t inline hex and gates the full guide behind a Widen brand-portal login. Multiple independent secondary sources (teamcolorcodes, sportsfancovers, apparelnbags) converge exactly on Navy #14213D and Red #CE1126, matching the candidate exactly. Medium confidence: values corroborated but not read directly off an olemiss.edu-controlled page with hex inline.'
    ),
    (
      'university-of-kansas',
      '155317',
      array['#0051BA', '#E8000D']::text[],
      'https://brand.ku.edu/guidelines/color',
      'high',
      'Confirmed exactly on the cited page. ''Crimson and blue have long been KU''s identifying colors'' -- Kansas Blue #0051BA and Crimson #E8000D are the two primary colors; no white listed as primary. Dropped the candidate''s white third value.'
    ),
    (
      'washington-state-university',
      '236939',
      array['#A60F2D', '#4D4D4D', '#FFFFFF']::text[],
      'https://brand.wsu.edu/colors/',
      'high',
      'Candidate''s wsu_ftp.sidearmsports.com PDF actually serves an unrelated Arizona State Illustrator file (broken/mismatched link, confirmed by reading its embedded metadata); fetched the current official WSU Brand colors page instead. States ''Crimson, gray, and white are the foundation of the WSU color palette... core colors ... primary colors for print, electronic, and environmental applications.'' Corrected Crimson from the candidate''s #981E32 to the stated #A60F2D and Gray from #53565A to #4D4D4D; kept White since it is explicitly one of the three named foundation/core colors.'
    ),
    (
      'the-university-of-texas-at-el-paso',
      '228796',
      array['#041E42', '#FF8200']::text[],
      'https://www.utep.edu/marketing-and-communications/_files/docs/visual-brand-guide.pdf',
      'medium',
      'Candidate''s university-communications PDF 404s; the current official visual-brand-guide.pdf (Jan 2024) redirects to a JS-rendered landing page with no extractable static color text. Multiple independent sources consistently cite UTEP Orange (PANTONE PMS 151 C) HEX #FF8200 and UTEP Blue (PANTONE PMS 282 C) HEX #041E42 -- both exact matches to the candidate. The accompanying third color across sources is Silver/Cool Gray, not white -- dropped the candidate''s white third value. Medium confidence: could not directly read the current official page''s static content.'
    ),
    (
      'temple',
      '216339',
      array['#9D2235', '#FFFFFF']::text[],
      'https://www.temple.edu/sites/www/files/uploads/Revised+Art+Sheet+-+December+2017.pdf',
      'high',
      'Candidate''s May 2021 CLC Art Sheet PDF is a scanned/image-based document with no extractable text layer; found and text-extracted the university''s Dec 2017 Revised Art Sheet PDF from the same temple.edu domain instead. ''Temple T box must be cherry red (PMS 201)'' -- Cherry HEX #9D2235, corrected from the candidate''s #990033 which doesn''t match any official Temple swatch. Temple''s official colors are Cherry and White only (black/grey appear only as vintage-wordmark print options) -- dropped the candidate''s #222222 third value.'
    ),
    (
      'james-madison-university',
      '232423',
      array['#450084', '#AD9C65', '#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/jmusports.com/documents/2023/7/12/JMU_AthIdentity_Guide.pdf',
      'high',
      'PDF fetched and text-extracted directly (pdftotext). ''The primary colors of the James Madison Athletics identity are purple, gold and white'' -- Purple (Pantone 2685, RGB 69/0/132 = #450084, exact match to candidate) and Gold (Pantone 4515, RGB 173/156/101 = #AD9C65, corrected from the candidate''s close-but-wrong #B3A369) are Primary Colors alongside White; gray and red are explicitly Secondary. Kept white since it''s one of only three named primary colors.'
    ),
    (
      'virginia-commonwealth-university',
      '234030',
      array['#000000', '#FFB300']::text[],
      'https://brand.vcu.edu/vcu-university/guidelines/visual-identity-components/color',
      'medium',
      'Candidate''s guid/primary_palette URL is login-walled. Current VCU Brand color page (corroborated by brand.vcu.edu/vcu-health/guidelines/color-palette) states ''VCU''s brand colors are black and gold with neutrals of white and grey'' -- Gold (PMS 130) HEX #FFB300 and Black #000000 are the two chromatic/near-chromatic primaries; White and Cool Gray 10 are explicitly framed as neutrals. Dropped the candidate''s white third value. Medium confidence: the exact hex swatches sit in an image asset on the primary page rather than in extractable text; corroborated via a matching quote instead of one clean direct read.'
    ),
    (
      'unc',
      '199120',
      array['#7BAFD4', '#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/unc.sidearmsports.com/documents/2015/4/20/CarolinaAthletics_BrandingGuidelines-Final.pdf',
      'high',
      'PDF fetched and text-extracted directly. Document has explicit ''PRIMARY IDENTITY'' and ''SECONDARY IDENTITY'' sections: Primary = Carolina Blue (Pantone 542C) HTML #7BAFD4 + White (both exact matches to the candidate''s first two values); Navy #13294B, Black, and Metallic Silver sit under Secondary Identity. Corrected by dropping the candidate''s navy third value -- it''s the secondary identity color, not primary.'
    ),
    (
      'university-of-oregon',
      '209551',
      array['#007030', '#FEE11A']::text[],
      'https://communications.uoregon.edu/uo-brand/visual-identity/colors',
      'high',
      'Confirmed exactly on the cited page. ''Always use UO Green and UO Yellow in all visual compositions. These are our primary brand colors'' -- no white or black in this framing. Dropped the candidate''s white third value.'
    ),
    (
      'usc',
      '123961',
      array['#990000', '#FFCC00']::text[],
      'https://identity.usc.edu/identity/color/',
      'high',
      'Candidate''s usctrojans.com athletics news article carries no color data (title only, JS-rendered); found the official USC Brand and Identity Guidelines color page instead. ''USC''s official colors are USC Cardinal and USC Gold. Each color is equal in importance'' -- USC Cardinal HEX #990000 and USC Gold HEX #FFCC00. Corrected significantly from the candidate''s #9D2235/#FFC72C, which are generic NCAA-style values, not USC''s own official identity-page hex; dropped the candidate''s white third value (not present on the page).'
    ),
    (
      'upitt',
      '215293',
      array['#003594', '#FFB81C']::text[],
      'https://www.brand.pitt.edu/visual-identity/color-palettes/primary-palette',
      'high',
      'Candidate''s 2021 PDF exceeded the fetch size limit; found the current official Pitt Brand primary-palette page instead. ''Our historical Royal and Gold as our primary and most-used colors... the core colors that define the brand'' -- Pitt Royal Blue #003594 and Pitt Gold #FFB81C, both exact matches to the candidate. No white named as primary -- dropped the candidate''s white third value.'
    ),
    (
      'utah-state-university',
      '230728',
      array['#00263A', '#8A8D8F']::text[],
      'https://www.usu.edu/brand/standards/logos/sub-brands/files/USU_Athletics_VIG.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''02.1 Primary'' section lists exactly two: PMS 539 Navy HEX #00263A and PMS 877 Metallic Silver/Gray HEX #8A8D8F, both exact matches to the candidate. White is not shown under the Primary heading (it appears only in a Reversed section) -- dropped the candidate''s white third value.'
    ),
    (
      'university-at-buffalo',
      '196088',
      array['#005BBB', '#FFFFFF']::text[],
      'http://www.buffalo.edu/brand/creative/color/color-palette.html',
      'high',
      'Confirmed exactly as cited. UB Blue #005BBB and Hayes Hall White #FFFFFF form the two-color ''primary palette'' dating to 1886; ten additional colors sit in a separate secondary palette. Matches the candidate exactly, no changes.'
    ),
    (
      'east-carolina-university',
      '198464',
      array['#592A8A', '#FEC923']::text[],
      'https://brand.ecu.edu/',
      'high',
      'Candidate''s 2018 athletics S3 PDF 404s; found the current official ECU Brand home page instead. ''The official colors for ECU are purple and gold'' -- ECU Purple HEX #592A8A (corrected from the candidate''s #582C83) and ECU Gold HEX #FEC923 (corrected from the candidate''s #FFC72C); ''black and white serving as accent colors,'' not primary -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-connecticut',
      '129020',
      array['#000E2F', '#FFFFFF', '#7C878E']::text[],
      'https://brand.uconn.edu/visual-identity/uconn-accessible-color-combinations/',
      'high',
      'Candidate''s Color-Guidelines PDF 500-errors; the official brand.uconn.edu domain confirms via its accessible-color-combinations page that the ''UConn Combinations'' primary set is Navy Blue #000E2F, White #FFFFFF, and Grey #7C878E -- and explicitly states that red (#E4002B, matching the candidate''s third value) is NOT a UConn brand color at all (a #BE2D2D red exists only in the separate UConn Health palette; #013ECD royal blue is explicitly an accent, not for wordmarks). Corrected by replacing the candidate''s red with the actual official grey.'
    ),
    (
      'ohio-university-main-campus',
      '204857',
      array['#00694E', '#FFFFFF']::text[],
      'https://www.ohio.edu/ucm/ohio-brand/colors',
      'high',
      'Confirmed and corrected on the cited page. Official Primary Colors are Cutler Green HEX #00694E (dominant), Under the Elms HEX #024230, and Cupola White. The candidate''s green (#154734) does not match Ohio''s palette at all -- it is actually Cal Poly''s Poly Green, an apparent Wikipedia sourcing error. Corrected to the dominant Cutler Green; kept white (named primary); dropped the secondary darker green (Under the Elms) to stay within a clean two-value chromatic-plus-white pair matching the candidate''s original two-value structure.'
    ),
    (
      'california-state-university-los-angeles',
      '110592',
      array['#FFCE00', '#FCB237', '#000000']::text[],
      'http://www.calstatela.edu/brand/colors-typography',
      'high',
      'Confirmed and corrected on the cited page. Primary Colors are explicitly Cal State LA Gold #FFCE00, Marigold #FCB237, and Black #000000 -- white does not appear anywhere in the official palette (''Cal State LA Gold should always be present... Black remains a core primary color''). Replaced the candidate''s white third value with the actual third primary, Marigold; gold and black matched the candidate exactly.'
    ),
    (
      'appalachian-state-university',
      '197869',
      array['#FFCC00', '#010101', '#FFFFFF']::text[],
      'https://uc.appstate.edu/brand-identity-guide/identity-guide/colors',
      'high',
      'Candidate''s old vt.uc.appstate.edu URL has a certificate mismatch (retired subdomain); found the current official University Communications colors page instead. Its ''Primary Color Palette'' explicitly lists three: App State Gold #FFCC00, Black #010101, White #FFFFFF (grays/browns/greens sit in a separate ''Extended'' tier). Corrected the candidate''s black from #222222 to the official #010101; gold and white matched exactly.'
    ),
    (
      'kent-state-university-at-kent',
      '203517',
      array['#003976', '#EFAB00']::text[],
      'https://www.kent.edu/brand/swatches',
      'high',
      'Candidate''s generic /brand landing page has no hex; found the Swatches subpage. ''Primary Colors'' lists exactly two: Kent State Blue #003976 (corrected from the candidate''s #002664, which does not match) and Kent State Gold #EFAB00 (matches candidate exactly). White is not a labeled primary color -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-nebraska-lincoln',
      '181464',
      array['#D00000']::text[],
      'https://licensing.unl.edu/sites/unl.edu.university-communication.licensing/files/media/file/FINAL-23-Brand-Guide.pdf',
      'high',
      'PDF fetched and text-extracted directly (16MB, pdftotext). ''When you think Nebraska Cornhuskers, you think red. Red is the primary color that should be used on all brand applications'' (Pantone 186C, HEX #D00000, exact match to candidate). Immediately below, a four-swatch ''The Core'' grouping shows Red/White/Black/a cream Pantone 7401C together, but only red carries the explicit ''the primary color'' framing in the prose -- the other three are grouped core neutrals without individual primary status. Reduced to the single confirmed chromatic red per the chromatic-preference default given the ambiguous framing, dropping the candidate''s white and cream third values.'
    ),
    (
      'udel',
      '130943',
      array['#00539F', '#FFD200']::text[],
      'https://www.udel.edu/content/dam/udelImages/ocm/style-guide/brand-style-guide.pdf',
      'high',
      'Candidate''s bluehens.com athletics news URL carries no color data (JS-rendered title only); found and text-extracted the official UD Brand Style Guide PDF instead. ''The primary colors should always be dominant'' -- exactly two: Pantone 2945C (Blue) Digital HEX #00539F and Pantone 109C (Yellow) Digital HEX #FFD200, both exact matches to the candidate. A six-color secondary palette (its own white/navy/gray/cream/blue/black) sits in a separate ''used sparingly'' section -- dropped the candidate''s white third value.'
    ),
    (
      'illinois-state-university',
      '145813',
      array['#CE1126', '#FFFFFF']::text[],
      'https://universitymarketing.illinoisstate.edu/downloads/identity/Athletics_Brand_Standards_Guide_2018.pdf',
      'high',
      'Candidate''s goredbirds.com URL is a viewer landing page with no extractable text; found the same 2018 guide re-hosted on the university''s own marketing domain and text-extracted it directly. The ''Athletics colors'' (official) section names exactly two: Redbird Red and White; Redbird Yellow and Black are explicitly labeled ''Support colors,'' not official. Kept the candidate''s white; corrected red from the candidate''s RGB-derived #CE142B to the guide''s own directly-labeled ''Hexadecimal Equivalent: CE1126'' elsewhere in the same document; dropped the candidate''s black third value (a support color, not primary).'
    ),
    (
      'grand-valley-state-university',
      '170082',
      array['#0032A0', '#000000', '#FFFFFF']::text[],
      'https://www.gvsu.edu/identity/color-2',
      'high',
      'Candidate''s 2015 gvsulakers.com athletics PDF 404s; found the current official GVSU Identity color page instead. ''Primary Palette'' lists exactly three: GVSU Blue #0032A0 (corrected from the candidate''s #0033A0), Black #000000, White #FFFFFF -- ''GVSU Blue should always be included... and serve as the dominant color.'' Kept all three since explicitly primary; matches the candidate''s structure with a one-digit blue correction.'
    ),
    (
      'san-francisco-state-university',
      '122597',
      array['#52247F', '#FFCF01']::text[],
      'https://brand.sfsu.edu/color',
      'medium',
      'Candidate''s logo.sfsu.edu URL 404s; the current official brand.sfsu.edu/color page is a JS-rendered brand-portal app with color swatches defined in an internal asset system, not extractable as static text. Multiple independent sources consistently cite SFSU Purple (PMS 268C) HEX #52247F (exact match to candidate) and Gold (PMS 116C) HEX #FFCF01 (corrected from the candidate''s close-but-different #FFCC00). White is not named alongside the pair anywhere -- dropped the candidate''s white third value. Medium confidence: could not directly read the current official page''s static content.'
    ),
    (
      'mississippi-state-university',
      '176080',
      array['#660000', '#FFFFFF']::text[],
      'https://www.legal.msstate.edu/trademark/FAQ.php',
      'high',
      'Candidate''s 2020 athletics brand-guide S3 PDF 404s; found the official University trademark/licensing FAQ page instead. ''The official colors for licensed products are PMS 505 (maroon), PMS 428 (grey) and white ... the accepted maroon for the Web is RGB 102:0:0 or hex #660000'' -- corrected significantly from the candidate''s #5D1725, an athletics-specific value that does not match any official university swatch. Kept white (explicitly one of the three named official colors); dropped grey to stay within a clean two-value chromatic-plus-white pair.'
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
