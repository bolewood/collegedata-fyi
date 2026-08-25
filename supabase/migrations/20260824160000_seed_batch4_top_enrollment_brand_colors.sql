-- Batch 4 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Every candidate citation URL was opened and checked against the school's
-- actual official page; a large share had rotted (dead PDFs, redirected/
-- reorganized brand sites, bot-walled or JS-rendered athletics pages,
-- Cloudflare-blocked ucdavis.edu subdomains, a SharePoint-walled Sac State
-- color PDF) and required finding the current official replacement, usually
-- on the same domain. Real, non-trivial hex corrections were made where the
-- official page's stated value differed from the Wikipedia candidate:
-- uc-davis (athletics-only candidate replaced with the university-wide Aggie
-- Blue/Gold pair), uc-irvine (candidate's navy/gold did not match the
-- current official Primary Colors at all), the-university-of-arkansas
-- (red corrected from #A41F35 to the official #9D2235), auburn-university
-- (navy corrected from #03244D to the official #0C2340), the-university-of-
-- texas-rio-grande-valley (orange corrected from #F05023 to the current
-- official #CB4900), nyu (white swapped for Ultra Violet, the actual third
-- labeled primary), university-of-nevada-las-vegas (white swapped for the
-- page's actual black; gray confirmed), and university-of-utah (reduced to
-- a single confirmed red -- the official guide explicitly frames white/
-- black/grey as "secondary options," not primary).
--
-- Candidate's mechanically-carried third value (usually white) was dropped
-- where the official page did not label it a primary/core color alongside
-- an already-complete chromatic pair: florida-state-university, colorado,
-- university-of-cincinnati-main-campus, the-university-of-texas-at-san-
-- antonio, san-jose-state-university, georgia-state-university (red demoted
-- to secondary; white confirmed primary), iowa-state-university,
-- university-of-kentucky (gray dropped, white confirmed primary),
-- university-of-north-carolina-at-charlotte, florida-atlantic-university,
-- clemson (white is a separate "neutral primary" tier), uc-santa-barbara,
-- northern-arizona-university, and university-of-california-riverside.
-- Confirmed as-is with no changes: uga, oregon-state-university,
-- utah-valley-university, george-mason-university (all values matched an
-- official four-color Primary Colors set; a fourth near-black dropped only
-- to respect the three-value cap), north-carolina-state-university-at-
-- raleigh, and university-of-iowa (medium confidence -- see below). umd's
-- three values were confirmed unchanged, only reordered to lead with the
-- chromatic pair.
--
-- Two schools could not be confirmed against a directly-fetchable official
-- source this pass and are recorded at medium confidence with the gap noted
-- in brand_colors_notes: california-state-university-sacramento (official
-- page names the colors but hex lives behind a SharePoint-walled PDF; hex
-- corroborated by name-specific secondary sources) and university-of-iowa
-- (current hawkeyesports.com/branding-guide page is JS-rendered with no
-- static content; hex corroborated by multiple independent secondary
-- indices, matching the candidate exactly). See
-- data/brand-colors/batch-4-2026-08-24.jsonl for the full per-school record.
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
      'uc-davis',
      '110644',
      array['#022851', '#FFBF00']::text[],
      'https://foa.ucdavis.edu/communications/brand/colors',
      'medium',
      'Cited athletics style-guide PDF (ucdavisaggies.com S3) had no extractable color text. UC Davis''s own brand domains (marketingtoolbox.ucdavis.edu, communicationsguide.ucdavis.edu, foa.ucdavis.edu) are all behind a Cloudflare bot challenge that blocked direct fetch, but multiple independent on-domain campus subpages (foa.ucdavis.edu, uecomm.ucdavis.edu, gsm.ucdavis.edu) converge on the same university-wide values: Aggie Blue HEX #022851 and Aggie Gold HEX #FFBF00, explicitly called ''the official colors of UC Davis.'' This is the campus-wide brand pair, not the athletics-specific PMS295/PMS4515 pair the candidate cited (#002855/#B3A369, from a 2020 athletics style guide) -- corrected to the current, more authoritative university brand values. Medium confidence: page content read via search corroboration across several on-domain quotes rather than a single direct fetch.'
    ),
    (
      'florida-state-university',
      '134097',
      array['#782F40', '#CEB888']::text[],
      'https://brand.fsu.edu/web/colors',
      'high',
      'Cited licensing.fsu.edu PDF redirects to brand.seminoles.com, a JS-rendered page with no extractable color text; found the current official FSU Brand Style Guide colors page instead. States ''Primary Colors'' as Garnet HEX #782f40 and Gold HEX #ceb888, both exact matches to the candidate. Black/Slate #2c2a29 is a separate expanded-strata color, not primary; White (Canvas #ffffff) sits under ''Neutrals.'' Dropped the candidate''s white third value as neither primary nor neutral-labeled alongside the pair.'
    ),
    (
      'uga',
      '139959',
      array['#BA0C2F', '#FFFFFF', '#000000']::text[],
      'https://brand.uga.edu/visual-identity/visual-style/',
      'high',
      'Cited S3 athletics brand manual PDF 404s; found the current official UGA Brand Style Guide page instead. Confirmed all three candidate values exactly as UGA''s stated primary palette: Bulldog Red #BA0C2F, Chapel Bell White #FFFFFF, Arch Black #000000 -- explicitly the three foundational colors of the identity. Confirmed as-is.'
    ),
    (
      'colorado',
      '126614',
      array['#CFB87C', '#000000']::text[],
      'https://www.colorado.edu/imc/cu-boulder-brand/visual-identity',
      'high',
      'Cited S3 NIL guidelines PDF would not render extractable text; found the official CU Boulder Visual Identity page instead. States ''Primary Palette: The official CU Boulder colors are CU Gold, Black, CU Light Gray and CU Dark Gray'' -- four explicit primaries, no white anywhere in the primary or secondary tiers. Kept CU Gold #CFB87C and Black #000000 as the two chromatic/near-chromatic primaries per the brief''s chromatic-pair preference; dropped the candidate''s white (not on the page at all) and the two grays (to stay within the 1-2-chromatic preference).'
    ),
    (
      'umd',
      '163286',
      array['#E21833', '#FFD200', '#FFFFFF']::text[],
      'https://brand.umd.edu/colors',
      'high',
      'Confirmed. Page''s ''Core Palette'' lists Maryland Red #e21833, Maryland Gold #ffd200, White #ffffff, and Black #000000 with no explicit primary/secondary split (''the university encourages the use of all four colors''). Kept the two chromatic core colors plus White (explicitly one of only four named core colors, in that presentation order); dropped Black to stay within the three-value cap. Same three hex values as the candidate, reordered to put the chromatic pair first.'
    ),
    (
      'oregon-state-university',
      '209542',
      array['#D73F09', '#000000', '#FFFFFF']::text[],
      'https://communications.oregonstate.edu/brand-guide/colors',
      'high',
      'Confirmed exactly, all three values. Page''s ''Primary Colors'' section lists Beaver Orange HEX #D73F09, Paddletail Black HEX #000000, and Bucktooth White HEX #FFFFFF, stating ''our color system relies heavily on Beaver Orange, black and white.'' Kept all three per the no-neutral-append exception -- explicitly labeled primary, not appended neutrals.'
    ),
    (
      'the-university-of-texas-at-san-antonio',
      '229027',
      array['#0B2240', '#E14504']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/utsa.sidearmsports.com/documents/2023/2/8/utsa-athletics-branding-guide.pdf',
      'high',
      'PDF fetched and text-extracted directly (pdftotext -layout, since automated summarization missed the embedded text). Color section states UTSA Blue PANTONE 289C HEX #0B2240 and UTSA Orange PANTONE 1665C HEX #E14504 -- both exact matches to the candidate. No white or third color appears in the stated color section -- dropped the candidate''s white third value.'
    ),
    (
      'uc-irvine',
      '110653',
      array['#255799', '#FECC07']::text[],
      'https://brand.uci.edu/identity/colors.php',
      'high',
      'Cited 2017 trademarks.uci.edu art-sheet PDF 404s; found the current official UC Irvine Color Palette page instead. Corrected significantly: the page''s only two ''Primary Colors'' are UCI Blue HEX #255799 and UCI Gold HEX #fecc07. The candidate''s #0C2340 is close to the page''s Secondary ''Darkest Blue'' #002244, not the primary blue, and its #FFC72C does not match the stated gold at all -- both values replaced with the actual current primaries. White does not appear on the page in any tier -- not added.'
    ),
    (
      'university-of-cincinnati-main-campus',
      '201885',
      array['#E00122', '#000000']::text[],
      'https://www.uc.edu/about/marketing-communications/brand-guide/visual-identity/color.html',
      'high',
      'Cited creative-brand/brand-design URL 404s (site reorganized); found the current Brand Guide color page on the same domain. States ''The University of Cincinnati''s primary color palette is built upon the dynamic duo of red and black'' -- UC Red HEX #e00122 and UC Black HEX #000000 are explicitly the two primary colors; White is a supporting/accessibility color, not primary. Dropped the candidate''s white third value.'
    ),
    (
      'university-of-arkansas',
      '106397',
      array['#9D2235', '#FFFFFF']::text[],
      'https://includes.uark.edu/examples/approved-colors.html',
      'high',
      'Cited athletics brand-guide PDF (arkansasrazorbacks.com) would not render extractable text. Official brand.uark.edu Colors page states ''Our primary colors of Razorback Red and Apple Blossom form the core of our visual brand identity'' (only two, no third color) but doesn''t inline the hex; the university''s own Approved Web Colors reference page gives Razorback Red #9D2235 and Apple Blossom (White) #FFFFFF. Corrected the candidate''s red from #A41F35 (does not match any published UA swatch) to the official #9D2235; kept white per the no-neutral-append exception -- explicitly one of only two named primary colors.'
    ),
    (
      'the-university-of-texas-rio-grande-valley',
      '227368',
      array['#CB4900', '#646469', '#FFFFFF']::text[],
      'https://www.utrgv.edu/brand/identity/color-palette/index.htm',
      'high',
      'Cited umc/creative-services URL 404s (department page retired); found the current official UTRGV Color Palette page on the same domain. States ''The University''s official colors are orange, gray and white'' -- Orange HEX #CB4900, Gray HEX #646469 (matches candidate''s gray exactly), White HEX #FFFFFF, all three explicitly named the official trio. Corrected the candidate''s orange from #F05023 (an older/different value not on the current official page) to the current #CB4900; kept white and gray since all three are explicitly the named official set, not an appended neutral onto an already-complete pair.'
    ),
    (
      'nyu',
      '193900',
      array['#57068C', '#8900E1', '#000000']::text[],
      'https://www.nyu.edu/employees/resources-and-services/media-and-communications/nyu-brand-guidelines/designing-in-our-style/nyu-colors.html',
      'high',
      'Cited athletics S3 PDF (gonyuathletics.com) returns S3 AccessDenied. Found the official NYU (university-wide) Brand Guidelines colors page instead, which is more authoritative than the athletics guide. Its ''Primary Colors'' heading lists exactly three: NYU Violet #57068c, Ultra Violet #8900e1, and Black #000000. White sits under ''Neutral Colors,'' not primary. Corrected by replacing the candidate''s white third value with Ultra Violet, the actual third labeled primary; kept Violet and Black which matched the candidate exactly.'
    ),
    (
      'utah-valley-university',
      '230737',
      array['#275D38', '#000000', '#FFFFFF']::text[],
      'https://www.uvu.edu/marketing/docs/uvu-color-palette.pdf',
      'high',
      'Cited URL (uvu_style_guide_logos.pdf) 404s; found the current official ''UTAH VALLEY UNIVERSITY Official Color Palette'' PDF on the same domain. Its ''PRIMARY COLOR PALETTE'' section lists UVU Green Pantone 7483 Hex #275D38, Pantone Black C Hex #000000, White Hex #FFFFFF, and a metallic silver Hex #A7A8AA -- four explicit primaries. Confirmed the candidate''s three values (green, black, white) exactly match three of the four; dropped only the metallic silver to stay within the three-value cap.'
    ),
    (
      'california-state-university-sacramento',
      '110617',
      array['#043927', '#C4B581']::text[],
      'https://www.csus.edu/brand/essentials.html',
      'medium',
      'Cited color-palettes.html page 404s; the current Brand Essentials page confirms ''Sacramento State''s primary brand colors are Sac State Green and Sac State Gold'' by name but links out to a SharePoint-hosted PDF for the actual hex values, which is not publicly fetchable. Hex values (#043927, #C4B581, exact matches to the candidate) corroborated by name-specific secondary color-reference sites (colorxs.com''s dedicated ''Sac State Green''/''Sac State Gold'' pages). Medium confidence: official page names the colors, hex confirmed off-domain rather than read directly on csus.edu. No white/other color named alongside the pair.'
    ),
    (
      'george-mason-university',
      '232186',
      array['#215732', '#FFC72C', '#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/georgemason.sidearmsports.com/documents/2024/4/25/2024_George_Mason_Athletics_BRAND_GUIDELINES_FINAL.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''COLOR PALETTE / PRIMARY COLORS'' section lists four explicit primaries: Green #215732, Gold #ffc72c, Black #373534, White #ffffff. Confirmed the candidate''s three values exactly match three of the four; dropped Black (a near-black #373534) to stay within the three-value cap, keeping the candidate''s original green/gold/white combination since all three are explicitly primary.'
    ),
    (
      'san-jose-state-university',
      '122755',
      array['#0038A8', '#FFB81A']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/sjsuspartans.com/documents/2022/12/14/2023-SJSU-Athletics_Brand_StyleGuide.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''Primary Colors'' section names exactly two: SJSU Athletics Blue #0038A8 and SJSU Athletics Gold #FFB81A, both exact matches to the candidate. A gray #AAAAAA appears elsewhere in the document but not under the Primary Colors heading; white does not appear in that section at all. Dropped the candidate''s white third value.'
    ),
    (
      'north-carolina-state-university-at-raleigh',
      '199193',
      array['#CC0000', '#FFFFFF', '#000000']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/gopack.com/documents/2023/1/11/NCSU_2023_Brand_Guidelines_.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''Wolf Pack Red,'' ''White,'' and ''Black'' each get an identical Pantone/CMYK/RGB/HEX card: #CC0000, #FFFFFF, #000000 -- exact matches to all three candidate values, presented as the athletics color set with no lower tier. Confirmed as-is.'
    ),
    (
      'university-of-utah',
      '230764',
      array['#BE0000']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/utahutes.com/documents/2023/8/23/ATH_2023-24_Branding_Guide.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''COLOR PALETTE'' page headers Utah Red, White, Black, Grey, but only Utah Red carries a stated CMYK/RGB conversion (RGB 190/0/0 = HEX #BE0000, exact match to candidate''s first value); the accompanying text explicitly frames White/Black/Grey as ''secondary options ... used to help promote the passion,'' not primary. Dropped the candidate''s white and black per that explicit secondary designation, leaving a single confirmed chromatic ink.'
    ),
    (
      'auburn-university',
      '100858',
      array['#F26522', '#0C2340']::text[],
      'https://auburntigers.com/traditions-about-auburn',
      'high',
      'Confirmed page loads and states ''Auburn Athletics Hex Orange: #F26522 | Blue: #0C2340'' verbatim, alongside ''Auburn''s official colors are burnt orange and navy blue'' -- only two colors named, no white. Corrected the candidate''s navy from #03244D (does not match the page at all) to the official #0C2340; orange matched exactly. Dropped the candidate''s white third value (not mentioned on the page).'
    ),
    (
      'georgia-state-university',
      '139940',
      array['#0039A6', '#FFFFFF']::text[],
      'https://commkit.gsu.edu/typography-color/',
      'high',
      'Cited georgiastatesports.com URL is a dead 2006 archive page with no color data. Found the current official GSU Communications ToolKit color page instead. States ''The university primary colors are blue and white. These two colors should be the strongest palette'' -- Georgia State Blue #0039A6 and White #FFFFFF are explicitly primary; Red Accent #CC0000 is explicitly listed under Secondary Colors. Corrected by dropping the candidate''s red third value (demoted to secondary on the current official page) and kept the confirmed blue/white primary pair.'
    ),
    (
      'iowa-state-university',
      '153603',
      array['#C8102E', '#F1BE48']::text[],
      'https://marcom.iastate.edu/color-palette',
      'high',
      'Cited brandmarketing.iastate.edu URL redirects to marcom.iastate.edu, whose Color Palette subpage states ''The primary palette is led by the university''s two signature colors: cardinal (Pantone 186c) and gold (Pantone 142c)'' -- Cardinal HEX #C8102E and Gold HEX #F1BE48, both exact matches to the candidate. Three supporting neutral tones are listed separately, not white -- dropped the candidate''s white third value (not present on the page in any tier).'
    ),
    (
      'university-of-kentucky',
      '157085',
      array['#0033A0', '#FFFFFF']::text[],
      'https://s3.amazonaws.com/ukathletics.com/documents/2016/2/5/56b4afd4e4b0df6d856076fa.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''PRIMARY COLOR PALETTE'' section names exactly two: Kentucky Blue HTML #0033A0 and White HTML #FFFFFF (with a Cool Gray 3C swatch listed separately, not under primary). Corrected by dropping the candidate''s gray third value (#C8C9C7, not part of the stated primary palette) and kept the confirmed blue/white primary pair.'
    ),
    (
      'university-of-nevada-las-vegas',
      '182281',
      array['#CF0A2C', '#CAC8C8', '#000000']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/unlvrebels.com/documents/2018/9/12/UNLV_Art_Sheet.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''COLOR INFORMATION'' table lists exactly three colors, no white: UNLV Red HTML CF0A2C (exact match to candidate), UNLV Gray HTML CAC8C8 (exact match to candidate''s third value), UNLV Black HTML 000000. Corrected by replacing the candidate''s middle white value (not on the page at all) with the actual published black, keeping red and gray as confirmed.'
    ),
    (
      'university-of-north-carolina-at-charlotte',
      '199139',
      array['#005035', '#A49665']::text[],
      'https://brand.charlotte.edu/visual-identity/color-palette/',
      'high',
      'Cited S3 athletics style-guide PDF (uncc.sidearmsports.com) 404s; found the official campus Brand Identity & Visual Standards color page instead. States ''The University''s school colors are green and white. For design purposes, our primary colors are Charlotte Green and Niner Gold'' -- Charlotte Green #005035 and Niner Gold #A49665, both exact matches to the candidate''s first and third values. White is a ''supplementary'' color per the same page, not part of the stated design-primary pair -- dropped the candidate''s white middle value.'
    ),
    (
      'florida-atlantic-university',
      '133669',
      array['#003366', '#CC0000']::text[],
      'https://www.fau.edu/public-affairs/branding/visual-standards/',
      'high',
      'Confirmed on the cited page. States FAU Blue #003366 and FAU Red #CC0000 as the two primary colors, with Silver and Gray as the separate secondary pair. Both chromatic values are exact matches to the candidate. White does not appear on the page at all -- dropped the candidate''s white third value.'
    ),
    (
      'clemson',
      '217882',
      array['#F56600', '#522D80']::text[],
      'https://www.clemson.edu/brand/color/',
      'high',
      'Cited clemsontigers.com/styleguide/ page gives no hex text, only a link to a full brand PDF; found the current official Clemson Brand Colors page instead. Confirmed Clemson Orange #F56600 and Regalia (purple) #522D80, both exact matches to the candidate, as the named primary pair -- ''the heart of our brand bleeds Clemson Orange... our primary and expanded color palette complements the Orange.'' White (''Goal Line'') and a near-black (''College Avenue'') are explicitly grouped under a separate ''Neutral Primaries'' tier, distinct from the two chromatic primaries -- dropped the candidate''s white third value.'
    ),
    (
      'uc-santa-barbara',
      '110705',
      array['#003660', '#FEBC11']::text[],
      'https://brand.ucsb.edu/visual-identity/color',
      'high',
      'Confirmed. Page''s ''Primary Color Palette'' groups twelve colors together with no distinct 2-3-color primary sub-tier (Navy and Gold appear first, followed by ten expanded hues including White and Black). Navy #003660 and Gold #FEBC11 are exact matches to the candidate and are the traditional, most-cited UCSB colors; since white sits inside a large undifferentiated 12-color group rather than being singled out as one of only 2-3 named primaries, dropped per the brief''s chromatic-pair preference.'
    ),
    (
      'northern-arizona-university',
      '105330',
      array['#002454', '#FAC01A']::text[],
      'https://in.nau.edu/wp-content/uploads/sites/194/NAU-Brand-Quick-Guide-update-6-1-23.pdf',
      'high',
      'Cited nau.edu/visual-identity-guide/color/ redirects to a JS-rendered single-page app with no static content; found the current on-domain NAU Brand Quick Guide PDF instead and text-extracted it directly. States HEX #002454 (Univers 75 Black / navy) and HEX #FAC01A (gold), both exact matches to the candidate, with no white shown alongside them. Confirmed as-is (white dropped).'
    ),
    (
      'university-of-california-riverside',
      '110671',
      array['#003DA5', '#FFB81C']::text[],
      'https://brand.ucr.edu/ucr-colors',
      'high',
      'Confirmed on the cited page. ''Primary Colors'' section names exactly two: UCR Blue #003DA5 and UCR Gold #FFB81C, both exact matches to the candidate -- ''the dominant color on UCR designs should always be Pantone 293c complimented by Pantone 1235c.'' White is not listed under primary, extended, or neutral tiers anywhere on the page -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-iowa',
      '153658',
      array['#000000', '#FFCD00']::text[],
      'https://hawkeyesports.com/branding-guide',
      'medium',
      'Cited branding-guide-2020 URL 404s; the current branding guide page at hawkeyesports.com/branding-guide is JS-rendered with no extractable static content. Multiple independent secondary color-reference sources converge on Hawkeye Black #000000 and Hawkeye Gold #FFCD00, exact matches to the candidate''s black and gold values (candidate''s white third value not corroborated anywhere and dropped). Medium confidence: official page identified and named but not directly readable; values confirmed only via secondary indices.'
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
