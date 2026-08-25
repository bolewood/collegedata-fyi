-- Batch 3 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Every candidate citation URL was opened and checked against the school's
-- actual official page; several had rotted (dead PDFs, redirected/reorganized
-- brand sites, bot-walled S3-hosted athletics PDFs, a login-walled UNT
-- SharePoint page) and required finding the current official replacement on
-- the same domain. Corrections made where the official page's stated hex
-- differed from the Wikipedia candidate: university-of-central-florida,
-- florida-international-university, university-of-houston,
-- california-state-university-long-beach, uf, san-diego-state-university,
-- university-of-north-texas, ucla, the-university-of-alabama,
-- brigham-young-university, california-state-university-northridge, and
-- texas-state-university. Candidate's mechanically-carried third value
-- (usually white/black) was dropped where the official page did not label it
-- a primary/core color alongside the confirmed pair: grand-canyon-university,
-- purdue, university-of-arizona, kennesaw-state-university (white swapped
-- for the page's actual third color, gray), california-state-university-
-- fullerton, indiana-bloomington (white swapped for the page's actual
-- second primary, cream), uw-madison, university-of-illinois-urbana-
-- champaign, uc-san-diego, university-of-north-texas (black dropped, white
-- kept -- explicitly primary on the current source), the-university-of-
-- texas-at-arlington. Confirmed as-is with no changes: arizona-state-
-- university-campus-immersion, liberty-university (white dropped there,
-- rest confirmed), osu, rutgers, university-of-south-florida,
-- texas-tech-university (all three explicitly labeled primary on their
-- official pages). southern-new-hampshire-university and
-- california-state-university-long-beach are the two schools not confirmed
-- against a fully official source this pass (low and medium confidence,
-- respectively) -- see data/brand-colors/batch-3-2026-08-24.jsonl for the
-- full per-school record, including the southern-new-hampshire-university
-- human-review flag (secondary-index hexes differ substantially from the
-- Wikipedia candidate and neither could be confirmed officially).
--
-- Plates are still derived at render (deriveInks() / glyphInks()); this
-- stores source hexes only.

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
      'southern-new-hampshire-university',
      '183026',
      array['#082241', '#F3D014']::text[],
      'https://www.brandcolorcode.com/southern-new-hampshire-university',
      'low',
      'Cited Issuu URL (issuu.com/snhu/docs/gsfinalweb) is bot-walled (403/404). SNHU''s official brand portal, brand.snhu.edu, is a Frontify-hosted single-page app with no server-rendered content -- unscrapable without a headless browser; its links (Learn about our look...) give no hex text. SNHU''s 2023 rebrand newsroom article names only ''Ink Blue'' as the primary logo color, no hex. Fell back to two independent secondary indexes (teamcolorcodes.com, brandcolorcode.com) that converge on Navy #082241 (PMS 289C) and Gold #F3D014 (PMS 115C), which differ substantially from the Wikipedia candidate (#1A326C/#FAB20B). Flagging for human review: neither pair could be confirmed against an official source this pass.'
    ),
    (
      'grand-canyon-university',
      '104717',
      array['#522398', '#000000']::text[],
      'https://www.gcu.edu/sites/default/files/media/Documents/brand/styleguide/BrandingStandardsManual.pdf',
      'high',
      'Cited athletics page (gculopes.com) returned no extractable body text; found the official GCU Branding & Standards Manual PDF instead. States ''GCU Purple'' PMS 267 = HEX #522398 (exact match to candidate) and logo colors specified as ''267 + BLACK'' (Pantone Black C = #000000) throughout the logo-usage pages. White is only a reversed/background option, not one of the two stated logo colors -- dropped the candidate''s third value #FFFFFF per the no-neutral-append rule.'
    ),
    (
      'arizona-state-university-campus-immersion',
      '104151',
      array['#7D2248', '#FFC72C']::text[],
      'https://brandguide.asu.edu/sites/default/files/2022-04/220323-ASU-BrandGuide-SunDevilAthletics-BrandIdentityGuidelines.pdf',
      'high',
      'Confirmed exactly. Sun Devil Athletics Brand Identity Guidelines color page: PANTONE 216C maroon HTML 7D2248 and PANTONE 123C gold HTML FFC72C, both exact matches to the candidate. Black is listed as a rich-black HTML 2C2A29 (not pure black) and white FFFFFF also appears, but maroon and gold are the two colors used across every logo/lockup example; dropped the candidate''s white third value as an unlabeled neutral.'
    ),
    (
      'university-of-central-florida',
      '132903',
      array['#000000', '#FFC904']::text[],
      'https://www.ucf.edu/brand/brand-assets/colors/',
      'high',
      'Corrected. Official page states verbatim ''Our colors are black and bright gold'' -- Black HEX 00 00 00 and UCF Bright Gold ''HEX FF C9 04, FF CC 00 or RGB 255R, 202G, 6B'' (raw HTML lists two hex spellings for the same swatch; kept FFC904 as it is listed first and is the closer match to the stated RGB). The candidate''s third value #B7A369 does not appear anywhere on the page (there is a separate print-only ''UCF Metallic Gold'' Pantone 10121 with no published hex) and was dropped.'
    ),
    (
      'liberty-university',
      '232557',
      array['#B72025', '#0A254E']::text[],
      'https://www.liberty.edu/marketing/wp-content/uploads/sites/114/1960553-Branding-Guide_digital.pdf',
      'high',
      'Confirmed exactly. 2022 Brand Guide, page 11: ''Primary Colors: Red, Navy, or both should always be the primary colors'' -- Liberty Red PMS 187 HEX #B72025 and Liberty Navy PMS 282 HEX #0A254E, both exact matches to the candidate. White is not named as a primary color (Light Gray and Light Blue are the labeled secondary/accent tiers instead) -- dropped the candidate''s white third value.'
    ),
    (
      'osu',
      '204796',
      array['#BA0C2F', '#A7B1B7', '#FFFFFF']::text[],
      'https://bux.osu.edu/color/primary-colors/',
      'high',
      'Confirmed exactly, all three values. Buckeye UX design system states verbatim ''Our primary palette consists of scarlet (red), gray and white'' -- Scarlet PMS 200 HEX #ba0c2f, Gray PMS 429 HEX #a7b1b7, White #ffffff. Kept white per the no-neutral-append rule''s exception: it is genuinely one of three explicitly labeled PRIMARY colors on the official page, not an appended neutral.'
    ),
    (
      'purdue',
      '243780',
      array['#CFB991', '#000000']::text[],
      'https://www.purdue.edu/brand-studio/brand/visual-identity/',
      'high',
      'Recorded marcom.purdue.edu URL redirects to www.purdue.edu/brand-studio/brand/visual-identity/. Confirmed exactly: ''At our core, we are gold and black'' -- Boilermaker Gold HEX #CFB991 and Black HEX #000000, both exact matches to the candidate, explicitly labeled ''Primary Colors'' (eight other hues are labeled ''Supporting Colors''). White is not part of the primary pair -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-arizona',
      '104179',
      array['#AB0520', '#0C234B']::text[],
      'https://brand.arizona.edu/applying-the-brand/colors',
      'high',
      'Recorded URL redirects to marcom.arizona.edu/applying-the-brand/colors. Confirmed exactly: ''The University of Arizona primary colors'' are Arizona Red HEX #AB0520 and Arizona Blue HEX #0C234B, both exact matches to the candidate. White appears only in the ''Neutral Colors'' tier, not the primary tier -- dropped the candidate''s white third value.'
    ),
    (
      'penn-state',
      '214777',
      array['#001E44', '#1E407C', '#FFFFFF']::text[],
      'https://brand.psu.edu/design-toolkit/design-essentials',
      'high',
      'Upgraded/expanded. Official page: ''we''ve simplified the Penn State Brand Palette by embracing our primary brand colors (Nittany Navy, Beaver Blue, and White Out)'' -- three explicitly labeled primary colors: Nittany Navy #001E44 (matches candidate), Beaver Blue #1E407C (missing from the Wikipedia candidate, added), White Out #FFFFFF (matches candidate). Pugh Blue is explicitly ''secondary,'' not included.'
    ),
    (
      'kennesaw-state-university',
      '486840',
      array['#0B1315', '#FDBB30', '#C5C6C8']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/ksuowls.com/documents/2022/12/9/AthleticsStyleGuide.pdf',
      'high',
      'Cited PDF fetched successfully. ''COLOR PALETTE'' section states PMS 1235 gold WEB FDBB30 (exact match to candidate), Process Black WEB 0B1315 (exact match), and PMS 421 gray WEB C5C6C8. There is no white anywhere in the stated three-swatch palette -- corrected by replacing the candidate''s unlabeled #FFFFFF third value with the actual published gray.'
    ),
    (
      'florida-international-university',
      '133951',
      array['#081E3F', '#D1A644']::text[],
      'https://brand.fiu.edu/visual-styles/colors/',
      'high',
      'Cited PDF (brand.fiu.edu/_assets/downloads/fiu_styleguide.pdf) 404s; found the current ''Brand Colors'' page on the same domain. States ''Primary Colors'' FIU Blue HEX #081E3F (exact match to candidate) and FIU Gold HEX #D1A644 -- corrected from the candidate''s #B6862C, which does not appear on the current official palette (Bright Gold #FFCC00 and White are separate ''Accent Colors,'' not primary). Dropped candidate''s white third value.'
    ),
    (
      'california-state-university-fullerton',
      '110565',
      array['#00244E', '#FF7900']::text[],
      'https://brand.fullerton.edu/colors/',
      'high',
      'Confirmed exactly. Page''s ''Primary Colors'' section: Titan Blue HEX #00244E and Titan Orange HEX #FF7900, both exact matches to candidate, described as the ''official colors'' that ''should always display dominantly.'' White is not part of the primary pair (only appears in the unrelated Web/Dark Mode palettes) -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-houston',
      '225511',
      array['#C8102E', '#FFFFFF']::text[],
      'https://www.uh.edu/brand/brand-identity/style-guide/index.php',
      'high',
      'Cited athletics page (uhcougars.com) returned no extractable color content; found the official UH Brand Style Guide instead. States ''Our brand is built on the bold red and white of the University of Houston'' -- Red (PMS 186) HEX #C8102E and White #FFFFFF are the two labeled primary colors. Corrected the candidate''s red from #C92A39 (does not match any published UH swatch) to the official #C8102E; kept white per the no-neutral-append exception (genuinely one of two labeled primaries). Dropped candidate''s gray third value (#B8B9B7 does not match the page''s actual accent gray #888B8D and gray is explicitly ''accent,'' not primary).'
    ),
    (
      'indiana-bloomington',
      '151351',
      array['#990000', '#EDEBEB']::text[],
      'https://licensing.iu.edu/doc/iu-promotional-style-guide.pdf',
      'high',
      'Cited athletics PDF (iuhoosiers.com / s3 mirror) 404s; found the official IU Licensing and Trademarks Promotional Products Style Guide instead. States ''Cream and crimson are key components of the IU brand'' -- Crimson PMS 201 HEX #990000 and Cream HEX #EDEBEB, both exact matches to the candidate''s first and third values. The guide explicitly notes white has been ''substituted for decades'' for cream in practice but names crimson+cream, not crimson+white, as the two official primary colors -- dropped the candidate''s middle white value.'
    ),
    (
      'rutgers',
      '186380',
      array['#CC0033', '#000000', '#FFFFFF']::text[],
      'https://communications.rutgers.edu/sites/default/files/rutgers_visual_identity_system_user_guide.pdf',
      'high',
      'Cited identity.rutgers.edu URL redirects to communications.rutgers.edu, whose page links out to the Visual Identity System User Guide PDF rather than showing hex itself. Confirmed exactly there: ''System Colors ... Primary Color Palette ... Red (Pantone 186), Black, White'' with Rutgers Red HEX #CC0033, Black HEX #000000, White HEX #FFFFFF -- all three explicitly labeled the required primary palette, exact match to the candidate. Kept all three per the no-neutral-append exception.'
    ),
    (
      'university-of-south-florida',
      '137351',
      array['#006747', '#FFFFFF', '#CFC493']::text[],
      'https://gousfbulls.com/documents/2023/8/21/23-ATH-BrandGuidelines-FINAL.pdf',
      'high',
      'Cited PDF (s3 mirror) 404s; found the current 2023 USF Athletics Brand Guidelines PDF instead. ''ATHLETICS COLORS / Primary Colors'' section states ''these three colors are a traditional representation of South Florida'' -- USF Green HEX #006747, White HEX #FFFFFF, and USF Gold HEX #CFC493 (positioned in the guide''s primary tier alongside Green and White; Black/Slime/Dark Green/Gray are separate ''Accent Colors''). All three exact matches to the candidate -- confirmed as-is.'
    ),
    (
      'uw-madison',
      '240444',
      array['#C5050C', '#FFFFFF']::text[],
      'https://brand.wisc.edu/web/colors/',
      'high',
      'Corrected. Official page: ''Badger Red and white are carried throughout the entire visual expression of UW-Madison, serving as the foundation and centerpiece of all branded materials'' -- explicitly only two ''primary colors,'' Badger Red HEX #C5050C and White #FFFFFF (both match candidate). Black (#121212) is listed in the ''Secondary Colors (Digital)'' tier, not primary -- dropped the candidate''s black third value.'
    ),
    (
      'university-of-illinois-urbana-champaign',
      '145637',
      array['#13294B', '#FF5F05']::text[],
      'https://marketing.illinois.edu/visual-identity/color',
      'high',
      'Confirmed exactly. Page''s two ''Primary Colors'' are Illini Orange HEX #FF5F05 and Illini Blue HEX #13294B (both match candidate), stated to occupy roughly 80% of design space. White and Black sit in the ''Secondary Colors'' tier -- dropped the candidate''s white third value.'
    ),
    (
      'texas-state-university',
      '228459',
      array['#501214', '#AC9155', '#D7BD8A']::text[],
      'https://brand.txst.edu/visual-identity/colors.html',
      'high',
      'Cited txst.com athletics page is JS-rendered with no extractable swatch text; found the official Brand Guidelines color page instead. ''Primary Colors (Core Brand)'' explicitly lists three chromatic hexes as ''the foundation of our core brand color palette'': Texas State Maroon #501214 (matches candidate), Texas State Dark Gold #AC9155, and Texas State Bright Gold #D7BD8A. The candidate''s single gold value #6A5638 does not appear anywhere on the current official palette (closest listed value is an unrelated web-exclusive Dark Gold #64480C) -- replaced with the two actually-published, explicitly-primary gold tones.'
    ),
    (
      'california-state-university-long-beach',
      '110583',
      array['#000000', '#EBA91B', '#FFFFFF']::text[],
      'https://www.csulb.edu/university-relations-and-development/strategic-communications/brand-guidance',
      'medium',
      'Cited PDFs (longbeachstate.com athletics style guide, multiple URLs) are bot-walled, returning HTML instead of PDF content. Official campus Brand Guidance page names the colors but gives no hex: ''The primary university colors are white, yellow and black.'' Hex for yellow/gold (#EBA91B, PMS 124C) found on the same csulb.edu domain via the College of Business branding subpage, which states campus-level branding colors as Gold #EBA91B and Black #000000. Medium confidence per source-priority tier 3 (official page names colors, hex found elsewhere on-domain). Candidate''s gold #ECAA00 is close but not an exact match to the on-domain sourced value -- corrected.'
    ),
    (
      'uf',
      '134130',
      array['#FA4616', '#0021A5']::text[],
      'https://brandcenter.ufl.edu/colors/',
      'high',
      'Cited identity.ufl.edu URL redirects to brandcenter.ufl.edu/colors/. Confirmed ''At our core, we are orange and blue'' -- Core Orange HEX #FA4616 (exact match to candidate) and Core Blue HEX #0021A5. Corrected the candidate''s blue from #003087 (an older ''UF Blue'' value not on the current page) to the current official Core Blue. Dropped candidate''s white third value (white is listed only as a plain neutral, not a primary).'
    ),
    (
      'san-diego-state-university',
      '122409',
      array['#C23038', '#231F20']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/goaztecs.com/documents/2021/10/19/Athletic_SDSU_Styleguide_2021_10_18_21_v4_1_.pdf',
      'high',
      'Cited PDF fetched successfully. ''COLOR PALETTE'' page: ''The official colors of San Diego State University are red and black'' -- PMS 187 red is specified as RGB 194/48/56 (= HEX #C23038, corrected from the candidate''s #C41230, a one-value-off transcription) and black as RGB 35/31/32 (= HEX #231F20, a rich/near-black, not pure #000000). White is used as a background in the same figure but is not one of the two colors the page names as official -- dropped the candidate''s white third value.'
    ),
    (
      'uc-san-diego',
      '110680',
      array['#182B49', '#FFCD00']::text[],
      'https://brand.ucsd.edu/logos-and-brand-elements/color-palette/index.html',
      'high',
      'Cited 2016 PDF (ucpa.ucsd.edu) 404s; found the current official Color Palette page instead. ''Core Colors'' are UC San Diego Navy HEX #182B49, Blue HEX #00629B, Yellow HEX #FFCD00, and Gold HEX #C69214 -- four core hues total. Kept Navy and Yellow, exact matches to the candidate and the two most traditionally cited Triton colors, capping at two chromatic values per the brief''s preference; White sits in the separate ''Neutral Colors'' tier and was dropped (candidate''s middle value).'
    ),
    (
      'university-of-north-texas',
      '227216',
      array['#00853E', '#FFFFFF']::text[],
      'https://meangreensports.com/documents/download/2025/8/19/UNT_Athletics_Branding_Guide_2025.pdf',
      'high',
      'Cited identityguide.unt.edu URL now redirects to a Microsoft-login-walled SharePoint page (no longer public). Found the current (2025) UNT Athletics Branding Guide instead, which carries the same institutional color data: ''PRIMARY PALETTE: 1. UNT GREEN HEX #00853E, 2. WHITE HEX #FFFFFF'' with ''3. BLACK HEX #000000'' explicitly placed in the SECONDARY PALETTE. Green matches candidate exactly; kept white per the no-neutral-append exception (explicitly labeled primary alongside green). Dropped candidate''s black third value since the same source explicitly demotes it to secondary.'
    ),
    (
      'ucla',
      '110662',
      array['#2774AE', '#FFD100']::text[],
      'https://brand.ucla.edu/identity/colors',
      'high',
      'Cited Nike/Jordan athletics style-guide PDF would not render extractable text. Fetched the official UCLA Brand Guidelines colors page directly instead: ''The primary UCLA Blue and Gold'' -- UCLA Blue HEX #2774AE (exact match to candidate) and UCLA Gold HEX #FFD100. Corrected the candidate''s gold from #F2A900, which the page identifies as ''Westwood Gold,'' an athletics-only accent shade, not the primary UCLA Gold used campus-wide.'
    ),
    (
      'the-university-of-alabama',
      '100751',
      array['#9E1B32', '#828A8F', '#FFFFFF']::text[],
      'https://brand.ua.edu/colors/',
      'high',
      'Cited athletics logos PDF (rolltide.com) is bot-walled (403). Found the official Brand Resources colors page instead: ''Crimson Flame, Capstone Gray and Victory White should be used in all marketing'' -- explicitly the three primary colors. Crimson Flame (Pantone 201) HEX #9E1B32 -- a substantial correction from the candidate''s #B30838, which does not match the current official swatch at all. Added Capstone Gray HEX #828A8F (the actual second primary color; the candidate had only two values and no gray). Kept White per the no-neutral-append exception (explicitly one of three labeled primaries).'
    ),
    (
      'brigham-young-university',
      '230038',
      array['#002E5D', '#FFFFFF']::text[],
      'https://brand.byu.edu/colors',
      'high',
      'Corrected. Official page''s ''Primary Colors'' are Navy HEX #002E5D and White #FFFFFF only. The candidate''s #003DA5 does not match any swatch on the page at all -- the closest named blue is a distinct secondary color, ''Royal'' HEX #0047BA, which is explicitly not primary. Replaced with the actual primary Navy; kept White per the no-neutral-append exception (explicitly one of only two labeled primaries).'
    ),
    (
      'california-state-university-northridge',
      '110608',
      array['#CE1126', '#000000', '#D1CEC6']::text[],
      'https://www.csun.edu/sites/default/files/02_CSUN_Athletics%20Guide.pdf',
      'high',
      'Cited PDF fetched successfully. ''COLOR INFORMATION'' page states the CSUN Matadors identity palette as PMS 186C Red HEX #CE1126 (exact match to candidate), Black HEX #000000 (exact match), and PANTONE 428C Gray HEX #D1CEC6 -- no white appears anywhere in this palette section. Replaced the candidate''s unlabeled white third value with the actual published gray.'
    ),
    (
      'texas-tech-university',
      '229115',
      array['#E90802', '#000000', '#FFFFFF']::text[],
      'https://www.ttu.edu/brand/visual-identity/index.php',
      'high',
      'Confirmed exactly, all three values. Page explicitly labels three ''Primary Colors'': Black #000000, Scarlet #E90802, White #FFFFFF, noting ''Texas Tech students selected the school colors, scarlet and black, during convocation'' in 1926, with white completing the trio. Kept all three per the no-neutral-append exception.'
    ),
    (
      'the-university-of-texas-at-arlington',
      '228769',
      array['#0064B1', '#F58025']::text[],
      'https://www.uta.edu/administration/mme/brand-standards/digital-branding',
      'high',
      'Cited resources.uta.edu/advancement/... URL 404s (department reorganized under mme/); found the current Digital Branding page on the same rebuilt site. Confirmed exactly: ''Primary Brand Colors'' are UTA Blue HEX #0064B1 and UTA Orange HEX #F58025, both exact matches to candidate, explicitly stated as ''just the blue and orange'' with secondary web variants kept separate. Dropped the candidate''s white third value.'
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
