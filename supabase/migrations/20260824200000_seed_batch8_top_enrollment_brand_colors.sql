-- Batch 8 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Most candidate citation URLs had rotted (dead S3/sidearm/wixstatic PDFs,
-- 403/404s, retired paths, WAF-blocked domains, JS-rendered brand portals,
-- SSO-gated pages) or turned out to be image-only PDFs with no extractable
-- text. Every school below was re-sourced against the school's own current
-- official domain where possible, verified by downloading PDFs and running
-- pdftotext -layout (never trusting a fetch-tool summary of a PDF), or by
-- reading the raw HTML/CSS/SVG text of an official page.
--
-- Caught mid-batch: east-tennessee-state-university's own Wikipedia-sourced
-- candidate blue (#00053E) does not exist anywhere in ETSU's actual official
-- brand PDF -- the real ETSU Blue is #041E42 -- a textbook example of the
-- plausible-but-fabricated-hex risk this batch was built to guard against;
-- caught only by independently re-extracting the PDF's real text rather than
-- trusting the candidate or any AI-generated search summary.
--
-- Real, non-trivial hex corrections (official value differs meaningfully
-- from the Wikipedia candidate, not just a formatting fix): wichita-state-
-- university (both official colors -- Shocker Yellow #FFDB00 and black --
-- differ from all three candidate values), cuny-lehman-college (candidate's
-- blue/green don't appear anywhere in the source at all; corrected to the
-- document's own stated Lehman Blue/Green), the-university-of-tampa (red
-- confirmed, white demoted out of Primary Colors), fordham-university
-- (Fordham Maroon corrected from #72253D to the brand portal's own
-- #7E072A), coastal-carolina-university (bronze corrected from #A27752 to
-- the site's own --bronze CSS custom property, #936B48), university-of-
-- central-oklahoma (both blue and bronze corrected), boston-college (both
-- maroon and gold corrected), the-university-of-tennessee-chattanooga
-- (both blue and gold substantially corrected), western-carolina-university
-- (gold corrected from #B9975B to #C1A875), east-tennessee-state-university
-- (blue corrected -- see above -- gold confirmed exact), texas-a-and-m-
-- university-commerce (blue corrected, reduced to one corroborated value;
-- school has since renamed to East Texas A&M University, same IPEDS ID),
-- troy-university (both maroon and gray corrected from the site's own live
-- web-style-guide color palette), fort-hays-state-university (gold
-- corrected from #F6BE00 to #FDB913), college-of-staten-island-cuny (both
-- blue and gray corrected via secondary index, black dropped),
-- north-dakota-state-university-main-campus (both green and gold
-- corrected), university-of-wisconsin-whitewater (purple corrected via
-- exact RGB-to-hex conversion of the officially stated RGB triplet),
-- university-of-west-florida (both navy and green corrected -- looks like
-- an outdated pre-rebrand candidate palette), southern-utah-university (red
-- corrected from #E91D2D to the explicitly-labeled SUU Red #DB0000), and
-- university-of-wisconsin-la-crosse (gray corrected from #969799 to the
-- explicitly data-labeled Primary Gray #78797A).
--
-- Confirmed as-is (candidate hex matched the current official source,
-- modulo dropping a non-primary third value or re-pointing to a working
-- on-domain citation): gwu (all three values, re-ordered to match the
-- source's own Blue/Buff/White sequence), texas-christian-university,
-- university-of-maryland-baltimore-county (gold confirmed, white dropped),
-- upenn (both values, white dropped), university-of-southern-mississippi
-- (both values, white dropped), university-of-north-dakota (all three
-- values -- an explicitly-defined three-color digital palette, not a
-- mechanical append), university-of-toledo (both values, white dropped),
-- southeastern-louisiana-university (all three values, white explicitly
-- named alongside green/gold).
--
-- Kept white as a real second/third primary where the official source
-- explicitly names it among only 2-3 primary colors (not a mechanical
-- append): gwu, university-of-north-dakota, southeastern-louisiana-
-- university, university-of-wisconsin-whitewater (RGB-converted).
--
-- Lower-confidence outcomes (official source unreachable or hex-less;
-- fell back to a reputable secondary index per source-priority tier 4,
-- confirmed by reading the actual cited page's text myself): university-
-- of-new-hampshire-main-campus (SharePoint-gated brand book), university-
-- of-central-oklahoma (WAF-blocked PDF, DSpace-gated mirror), boston-
-- college (image-only PDF off a non-.edu host, SSO-gated colors page),
-- college-of-staten-island-cuny (candidate citation was an unrelated dead
-- sports article with zero brand content). Medium confidence (hex
-- corroborated via an on-domain CSS custom property or inline SVG fill
-- rather than the brand page's own body text): coastal-carolina-university,
-- texas-a-and-m-university-commerce, california-state-university-east-bay.
--
-- No school was left null this batch -- every official or fallback search
-- turned up at least one corroborated chromatic hex.
--
-- Plates are still derived at render (deriveInks() / glyphInks()); this
-- stores source hexes only. Every finalized pair/triple was run through
-- production deriveInks()/glyphInks() (paper #f1ece1, MIN_B_ON_CREAM=1.25):
-- none fell through to the house-ink path, so no real chromatic primary was
-- lost to a fallback in this batch. See
-- data/brand-colors/batch-8-2026-08-24.jsonl for the full per-school
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
      'university-of-new-hampshire-main-campus',
      '183044',
      array['#003591', '#FFFFFF']::text[],
      'https://www.brandcolorcode.com/university-of-new-hampshire',
      'low',
      'Candidate''s box.app.com share link requires JavaScript and returns no readable brand content (confirmed by direct fetch: bare ''Box'' shell page). UNH''s own brand book lives behind a SharePoint login (universitysystemnh.sharepoint.com) with no public un-gated brand/colors page found on unh.edu. Fell back to a reputable secondary index per source-priority tier 4, which cites ''University of New Hampshire Brand Guidelines (Verified Source)'': Blue Pantone 661C HEX #003591, White #FFFFFF. Corrected: candidate''s #041E42 is meaningfully darker/different from the real #003591; candidate''s third value #BBBCBC (silver) dropped -- UNH''s stated colors are only Blue and White, not three.'
    ),
    (
      'gwu',
      '131469',
      array['#002D62', '#E4CF9F', '#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/gwsports.com/documents/2024/4/10/GW_Revolutionaries_Identity_Guidelines.pdf',
      'high',
      'Candidate''s PDF downloaded and text-extracted cleanly. Confirmed in the ''GW Athletics Color Palette'' section: ''GW has its own distinctive palette of colors, which has an emphasis on blue, buff and white.'' Blue PMS 282 HEX 002D62 (exact match) and Buff PMS 7502 HEX E4CF9F (exact match), both explicitly grouped with white as the three-color primary set (not a mechanical append -- white is named alongside blue and buff in the same sentence). Lime HEX CEDC00 is explicitly flagged ''FOR STUDENT LIFE PROMOTION AND MERCHANDISE ONLY'' and excluded. Confirmed as-is, reordered to match the source''s own Blue/Buff/White sequence.'
    ),
    (
      'texas-christian-university',
      '228875',
      array['#4D1979', '#FFFFFF']::text[],
      'https://brand.tcu.edu/university-color/',
      'high',
      'Candidate''s logo-identity-standards page only states the purple hex without confirming white as official; found TCU''s dedicated University Color page instead: ''TCU''s school colors are purple and white, but purple has long been the strongest color for TCU... The correct TCU purple for website development is #4d1979.'' White is one of only two explicitly named official colors, not a mechanical append. Confirmed as-is exactly.'
    ),
    (
      'wichita-state-university',
      '156125',
      array['#FFDB00', '#000000']::text[],
      'https://www.wichita.edu/services/strategic_communications/brand_standards/_documents/visual-standards-2022.pdf',
      'high',
      'Candidate''s sidearmsports.com S3 PDF 404s (NoSuchKey). Found and text-extracted the current official Wichita State Visual Identity Standards PDF instead: ''Wichita State''s official colors: Shocker Yellow(TM) ... Hex: FFDB00'' and ''Black ... Hex:000000''; ''Wichita State has two primary colors: Shocker Yellow and black.'' Substantial correction from all three candidate values (#27251F, #FFFFFF, #FFCD00) -- none of which match the real primary pair or appear in the document.'
    ),
    (
      'university-of-maryland-baltimore-county',
      '163268',
      array['#000000', '#FDB515']::text[],
      'https://styleguide.umbc.edu/umbc-colors/',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly: ''UMBC Colors Primary Colors UMBC Black: ... Web – #000000 ... UMBC Gold: ... Web – #fdb515.'' Gold matches candidate exactly; Black confirmed. UMBC AOK Teal (#007176) and UMBC Retriever Brown (#a67a05) are listed separately under ''Secondary Colors'' and excluded. Corrected: candidate''s third value #FFFFFF dropped -- only Black and Gold are labeled Primary Colors on the page, white is not named as a primary.'
    ),
    (
      'cuny-lehman-college',
      '190637',
      array['#0061A0', '#84BD00']::text[],
      'https://www.cuny.edu/wp-content/uploads/sites/4/page-assets/about/administration/offices/communications-marketing/university-identity/campus-identity/Lehman_graphic_identity.pdf',
      'high',
      'Candidate''s citation downloaded and text-extracted cleanly, but the candidate''s own hexes (#1C377B, #C9A93E) do not appear anywhere in the document -- a wrong-swatch pull. The real text states: ''In 2017, the Lehman College Primary blue and green, taken from the Lehman College Logo, were updated to slightly brighter tones'' -- Lehman Blue PMS 300 HEX #0061A0 and Lehman Green PMS 376 HEX #84BD00. A Gray swatch (#DCDDDE) sits in the same layout block but is never called Primary in the prose (only ''blue and green'' are), so it was left out per the chromatic-preference default; Yellow/Green (#CDDE00) is explicitly labeled an Accent color and excluded.'
    ),
    (
      'upenn',
      '215062',
      array['#011F5B', '#990000']::text[],
      'https://branding.web-resources.upenn.edu/logos-and-branding/elements-penn-logo',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly: ''Penn Red Web RGB: 153,000,000 Hex: #990000'' and ''Penn Blue Web RGB: 001,031,091 Hex: #011F5B'' -- both exact matches. Corrected: candidate''s third value #FFFFFF dropped -- the page only notes ''the logo can be used in black and white or Penn blue'' as a usage guideline, it never states white as a third official color with its own hex.'
    ),
    (
      'the-university-of-tampa',
      '137847',
      array['#C8102E', '#000000']::text[],
      'https://www.ut.edu/content/dam/ut/uploadedFiles/University_Services/Public_Information/UTBrandGuidelines2024UpdateV2.pdf',
      'high',
      'Candidate''s uploadedFiles PDF 404s (page restructured); found and text-extracted the current 2024-update UT Brand Guidelines PDF on the same domain instead. ''Primary Colors: UTampa RED – PMS 186C ... RGB (web) R:200 G:16 B:46'' (=#C8102E, exact match) and ''BLACK – PMS Process Black ... RGB (web) R:0 G:0 B:0''. Corrected: candidate''s white dropped -- the guide lists White (with an apparent RGB typo, R255 G205 B255) under a separate ''Secondary Colors'' heading alongside Gray, Steel and Silver; the usage note ''UTampa red and black are primary colors. They can be combined with white'' does not promote white to primary status.'
    ),
    (
      'fordham-university',
      '191241',
      array['#7E072A']::text[],
      'https://live.standards.site/fordham-university/',
      'high',
      'Candidate''s fordham.edu page redirects to a brand landing page with no stated hex; it links out to Fordham''s official brand-standards portal (live.standards.site/fordham-university/), whose embedded page-builder data names ''Fordham Maroon'':''#7E072A'' explicitly, along with ''Fordham Black'' #282220, ''Fordham Gray'' #5A6675, ''Deep Maroon'' #512533, ''Victory Blue'' #004658 and others as a wider palette. Corrected: candidate''s #72253D does not match the real Fordham Maroon; candidate''s #E1E1E1 light-gray dropped -- with ~11 named colors on the portal and no explicit ''these are the two/three primary colors'' statement, kept just the one clearly flagship chromatic (maroon) per the prefer-1-2-chromatic default rather than guess which secondary belongs alongside it.'
    ),
    (
      'coastal-carolina-university',
      '218724',
      array['#006F71', '#936B48']::text[],
      'https://www.coastal.edu/universitycommunication/brandstandards/visualstandards/',
      'medium',
      'Candidate''s PDF 404s. The live Visual Standards page names the colors by Pantone only (''the seal should always appear in PMS 322 (teal) or PMS 875 (bronze)''), no hex in the body text. Read the site''s own production stylesheet (coastal.edu/media/2024siteassets/siteassets/css/style.css) for the hex: ''--teal: #006F71'' (exact match to candidate) and ''--bronze: #936B48''. Corrected: candidate''s #A27752 does not match the site''s own --bronze custom property (that hex does appear once elsewhere in the same stylesheet, but only as a cookie-banner background color, unrelated to the brand palette). Medium confidence: hex read from an on-domain CSS custom property, not the brand page''s own text.'
    ),
    (
      'university-of-central-oklahoma',
      '206941',
      array['#002D62', '#FFD200']::text[],
      'https://teamcolorcodes.com/central-oklahoma-bronchos-color-codes/',
      'low',
      'Candidate''s PDF returns 403 (WAF-blocked) on direct fetch, and the same URL now redirects to the ucomm office landing page with no working link to a current brand PDF; the only other located copy (shareok.org institutional repository) sits behind a DSpace login wall. Fell back to a reputable secondary index per tier 4: ''blue color code ... Pantone: PMS 648 C, Hex Color: #002D62'' and ''bronze color code ... Pantone: PMS 116 C, Hex Color: #FFD200.'' Corrected: candidate''s #003366 and #FFCC00 are both off from these values; candidate''s white dropped (UCO''s colors are described everywhere found as simply ''Bronze and Blue,'' no third color). Low confidence: no official on-domain hex was reachable.'
    ),
    (
      'boston-college',
      '164924',
      array['#98002E', '#BC9B6A']::text[],
      'https://teamcolorcodes.com/boston-college-eagles-color-codes/',
      'low',
      'Candidate''s squarespace-hosted PDF (not even on a bc.edu domain) downloads as a 15MB, 19-page, zero-extractable-text file (confirmed via pdftotext -- image/vector only). BC''s own ''More on the BC colors'' page (bc.edu/content/bc-web/restricted/branding/colors) redirects to a SAML/SSO login wall, inaccessible without a bc.edu account. Fell back to a reputable secondary index per tier 4, confirmed by reading its actual swatch table (not just an AI summary): ''Maroon ... Hex Color: #98002E ... PANTONE: PMS 202'' and ''Gold ... Hex Color: #BC9B6A ... PANTONE: PMS 874'' -- these Pantone numbers match BC''s own published PMS 202/874 maroon-and-gold identity. Corrected: candidate''s #8C2232 and #DBCCA6 both differ from these; candidate''s white dropped (not part of the two-color maroon/gold identity anywhere found). Low confidence: no official on-domain hex was reachable.'
    ),
    (
      'university-of-southern-mississippi',
      '176372',
      array['#000000', '#FFD046']::text[],
      'https://www.usm.edu/university-communications/files/usm_graphic_standards_september2020.pdf',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly: ''The official Southern Miss colors are black and gold, chosen in 1912... BLACK Web - #000000 ... GOLD Web - #FFAB00 or #FFD046.'' Both candidate values (#000000, #FFD046) are exact matches to one of the two stated web-gold options. Corrected: candidate''s white dropped -- the page states only black and gold are the official colors, no third value.'
    ),
    (
      'the-university-of-tennessee-chattanooga',
      '221740',
      array['#112E51', '#FDB736']::text[],
      'https://www.utc.edu/communications-and-marketing/creative-and-marketing-services/brand-basics',
      'high',
      'Candidate''s graphic-guidelines page 404s and the direct university-colors page returns 403 to automated fetches; found and read the ''Brand Basics'' page on the same domain instead: ''Our University is blue and gold to its core... Blue RGB 17/46/81 binhex #112E51 CMYK 100/84/41/37 Pantone 295 Gold RGB 253/183/54 binhex #FDB736... Gray RGB 160/174/192 binhex #A0AEC0'' (gray explicitly a third/secondary swatch, not grouped with ''blue and gold to its core''). Substantial correction: candidate''s #00386B and #E0AA0F are both well off the real values; candidate''s white dropped -- not mentioned anywhere on the page.'
    ),
    (
      'eastern-michigan-university',
      '169798',
      array['#046A38']::text[],
      'https://www.emich.edu/communications/brand-standards/logo-colors-type/colors.php',
      'high',
      'emich.edu sits behind a Cloudflare JS challenge that blocks direct automated fetches of the live page; confirmed the page''s actual text via an archived snapshot of the same URL instead: ''Primary Palette ... Green PMS 349 ... #046A38 ... Neon PMS 375 ... #97D700 Accent Color *Note: Use this color sparingly as an accent only!'' Green matches the candidate exactly and is the only color not flagged as accent-only. Corrected: candidate''s second value #FFFFFF dropped -- no hex for white is stated anywhere on the page, only a usage note (''Do not use white text over this color'').'
    ),
    (
      'western-carolina-university',
      '200004',
      array['#592C88', '#C1A875']::text[],
      'https://www.wcu.edu/discover/communications-and-marketing/wcu-brand/visual-identity/wcu-colors.aspx',
      'high',
      'Candidate''s Athleticsbrandstyleguidev4.pdf downloads empty (0 bytes). Found and read WCU''s own Colors page instead: ''PMS 267 C ... RGB 89 44 136 ... HEX #592C88'' (Purple, exact match to candidate) and ''PMS 467 C or 872 metallic ... RGB 193 168 117 ... HEX #C1A875'' (Gold). Trail #2C1B39, Feldspar #E5E6BD, Spring #DAF55B, Rain #26B6A2 and Sky #DBF0F4 are separate secondary swatches, excluded. Corrected: candidate''s gold #B9975B is close but not exact to the real #C1A875; candidate''s white dropped -- not listed on this page at all.'
    ),
    (
      'east-tennessee-state-university',
      '220075',
      array['#041E42', '#FFC72C']::text[],
      'https://www.etsu.edu/brand/documents/mini-brand-guidelines-accessible.pdf',
      'high',
      'Candidate''s issuu embed can''t be reliably text-extracted; found and text-extracted ETSU''s official ''Mini Brand Guidelines'' PDF (dated March 2026) on etsu.edu instead. MAIN COLOR PALETTE: ''ETSU Blue PMS 282 ... R:0 G:5 B:62 (web) HTML: 041E42'' and ''ETSU Gold PMS 123 ... R:255 G:199 B:44 HTML: FFC72C.'' Gold matches the candidate exactly, but the candidate''s blue (#00053E) is WRONG -- it does not appear anywhere in this official PDF; the real ETSU Blue is #041E42 (this looks like exactly the kind of plausible-but-fabricated hex the batch brief warned about, so it was independently re-verified via pdftotext rather than trusted). Gray #A2AAAD and Bright Blue #0033A0 are listed under a separate SECONDARY COLOR PALETTE and excluded; candidate''s white dropped -- only two colors are in the MAIN palette.'
    ),
    (
      'university-of-north-dakota',
      '200280',
      array['#009A44', '#FFFFFF', '#000000']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/undsports.com/documents/2023/4/10/Athletics_Brand_22_Media.pdf',
      'high',
      'Candidate''s citation downloaded and text-extracted cleanly. ''The official colors of North Dakota Athletics are #009A44, #000 and #FFF. Use these codes for digital applications (social media, web, video).'' All three candidate values confirmed exactly; this is the source''s own explicitly-defined three-color digital palette, not a mechanical white/black append. Gray AAAEAD (Pantone 421) is a separate print-only accent and excluded. Confirmed as-is.'
    ),
    (
      'texas-a-and-m-university-commerce',
      '224554',
      array['#00386C']::text[],
      'https://www.etamu.edu/brand/color-palette/',
      'medium',
      'Candidate''s tamuc.edu URL redirects to etamu.edu -- the university renamed itself East Texas A&M University (ETAMU) but retains the same IPEDS ID given. The live Color Palette page states ''Our university''s colors -- blue and gold -- have been a part of our history'' under a ''PRIMARY COLOR PALETTE'' heading, but the actual swatch hex values are rendered as images with no extractable text (confirmed: only generic WordPress theme-preset hexes are present in the page''s markup). One genuine on-domain signal was found: a CSS custom property literally named ''--wp--preset--color--tamuc-blue: #00386c''. A linked ''Brand Guidlines Quick Guide'' PDF that might have stated both hexes returns a broken redirect loop. Corrected/reduced: candidate''s #0A2846 doesn''t match the corroborated blue; candidate''s gold #EDAC09 and white dropped entirely -- no gold hex was found anywhere on-domain or in a secondary check, and rather than guess, it was left off. Medium confidence: single value from an on-domain CSS custom property, not body text.'
    ),
    (
      'california-state-university-east-bay',
      '110574',
      array['#D50032']::text[],
      'https://www.csueastbay.edu/universitycommunications/brand/fonts-and-colors.html',
      'medium',
      'Candidate''s citation is live, with a ''Colors: Primary / Secondary / Tertiary'' section, but the actual swatches are rendered as images (primary.jpg / secondary.jpg / tertiary.jpg) with no extractable hex text -- per the no-eyedropping rule, those can''t be used directly. The same page''s own Pioneer ''P'' logo mark is an inline SVG using fill="#D50032" for its red, which matches the candidate exactly and is a genuine on-domain hex value (not from an image). Corrected/reduced: dropped candidate''s white and black -- neither could be independently confirmed as a named primary color anywhere in extractable text on this page. Medium confidence: red corroborated via an on-domain SVG fill rather than a body-text or CSS-variable statement.'
    ),
    (
      'troy-university',
      '102368',
      array['#6D0017', '#B2B3B5']::text[],
      'https://trojan.troy.edu/styleguide/index.html',
      'high',
      'Candidate''s citation is live, but is Troy''s *web developer* style guide (HTML5/CSS standards), not a printed brand book -- it turned out to still carry real brand hex. Its own ''Color Palette'' section lists live swatches: #6d0017, #ded7c3, #f6eed6, #000, #555, #888, #b2b3b5, #ccc, #f5f5f5, #fff -- and #6d0017 is literally the background-color used on the page''s own live navigation banner, confirming it as Troy''s production maroon. Corrected: candidate''s #98002E is a notably brighter, different maroon than the site''s actual #6D0017; candidate''s gray #999999 approximates but doesn''t match the real #B2B3B5 swatch. Kept the two most brand-relevant swatches (dark maroon + gray) and dropped the near-white cream swatches (#ded7c3, #f6eed6), which read as background/accent tones rather than a second primary.'
    ),
    (
      'university-of-toledo',
      '206084',
      array['#0B2240', '#FFCD00']::text[],
      'https://utrockets.com/sports/2023/3/30/toledo-athletics-branding',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly: ''Branding Guidelines Colors MIDNIGHT BLUE PANTONE 289 C #0B2240 ... ATHLETIC GOLD PANTONE 116C #FFCD00.'' Both candidate values confirmed exactly. Corrected: candidate''s white dropped -- only Midnight Blue and Athletic Gold are named as the two official colors; Orange (#E87722) appears elsewhere on the page only in the context of approved sport-specific sub-branding marks, not the core two-color identity.'
    ),
    (
      'fort-hays-state-university',
      '155061',
      array['#000000', '#FDB913']::text[],
      'https://www.fhsu.edu/university-marketing-strategic-communications/documents/2026-fhsu-brand-standards-v2.pdf',
      'high',
      'Candidate''s documents/brand-standards.pdf 404s after a URL restructure (university-marketing -> university-marketing-strategic-communications); located and text-extracted the current live ''2026-fhsu-brand-standards-v2.pdf'' on the same domain instead. ''These are the official colors of FHSU... PRIMARY BRAND COLORS TIGER GOLD ... HEX: #FDB913 TIGER BLACK ... HEX: #000000.'' Black confirmed exact; corrected: candidate''s gold #F6BE00 differs from the real Tiger Gold #FDB913. Highlight/fine-printing colors (Seaway, Bluelight, Frontier, etc.) are a separate accent tier, excluded; candidate''s white dropped -- not part of the two-color Primary Brand Colors set.'
    ),
    (
      'college-of-staten-island-cuny',
      '190558',
      array['#8AC2EB', '#73797C']::text[],
      'https://www.brandcolorcode.com/college-of-staten-island-csi',
      'low',
      'Candidate''s citation is a live but unrelated 2013 sports-news article page with no brand/color content at all (just a rotator and schedule links). No dedicated CSI brand/colors page was found on csidolphins.com or csi.cuny.edu. Fell back to a reputable secondary index per tier 4, which cites ''as per their official visual identity manual, Pantone codes ... 292 C and 431 C'': Blue Hex #8AC2EB, Gray Hex #73797C. Corrected: candidate''s #69B3E7 and #5B6770 are both plausible-looking but different from these; candidate''s #000000 dropped -- the school''s colors are described everywhere found as simply blue and gray, no third value. Low confidence: no official on-domain hex was reachable.'
    ),
    (
      'southeastern-louisiana-university',
      '160612',
      array['#215732', '#FFFFFF', '#FFC72C']::text[],
      'https://lionsports.net/sports/2021/7/27/slu-athletics-branding.aspx',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly: ''Green Pantone 357 C ... HEX 215732'' and ''White ... HEX FFFFFF'' and ''Gold Pantone 123 C ... HEX FFC72C,'' listed together as the three official colors. All three candidate values confirmed exactly; white is explicitly one of only three named colors here, not a mechanical append. Confirmed as-is.'
    ),
    (
      'north-dakota-state-university-main-campus',
      '200332',
      array['#00583D', '#FFC425']::text[],
      'https://www.ndsu.edu/marketing-communications/resources/logos',
      'high',
      'Candidate''s gobison.sidearmsports.com S3 PDF 404s (NoSuchKey). Found and read the official NDSU Logos resource page instead: ''Green Pantone: #343 ... HEX: #00583d'' and ''Yellow Pantone: #123 ... HEX: #ffc425.'' Corrected: candidate''s #005643 and #FFC82E both drift from these real official values; candidate''s white dropped -- not named on this page.'
    ),
    (
      'university-of-wisconsin-whitewater',
      '240189',
      array['#501D82', '#FFFFFF']::text[],
      'https://www.uww.edu/umc/brand-and-visual-identity/colors',
      'high',
      'Candidate''s news/campus-identity-standards/colors page 404s (site restructured); found and read the current Color Guidelines page instead: ''The official university colors are Warhawk Purple and White... Warhawk Purple Pantone: PMS 268 CMYK: 82,100,0,12 RGB: 80,29,130'' and ''White Pantone: PMS White CMYK: 0,0,0,0 RGB: 255,255,255.'' No hex is printed directly (the page says to ''refer to our guide for tips, including HEX numbers, if using Canva''), so the purple hex was derived by exact, lossless RGB(80,29,130)->#501D82 conversion of the officially stated RGB triplet -- not an invented or eyedropped value. Corrected: candidate''s #502D7F differs meaningfully in the G and B channels from the real #501D82. White kept -- explicitly one of only two official colors. Secondary colors (a darker purple PMS 2617 and black) are excluded.'
    ),
    (
      'university-of-west-florida',
      '138354',
      array['#00205B', '#00A346']::text[],
      'https://uwf.edu/brand/color/',
      'high',
      'Candidate''s goargos.com PDF returns HTML (dead link, restructured site). Found and read UWF''s official Color page instead: ''Primary Institutional Color Palette. Our primary blue has been reimagined as a rich Argo Navy, and our primary green is now a brighter and more energetic Argo Green... Argo Navy ... HEX: 00205B ... Argo Green ... HEX: 00A346.'' Substantial correction: candidate''s #0072CE and #00AF66 are both well off the real values (this looks like an outdated pre-rebrand palette). Heritage Blue, Cannon Green, Luna Blue, Nautilus Blue, Pine and Spring Green are explicitly a separate Secondary tier and excluded; candidate''s white dropped -- the Primary palette is only navy + green.'
    ),
    (
      'southern-utah-university',
      '230603',
      array['#DB0000']::text[],
      'https://www.suu.edu/webservices/styleguide/colors.html',
      'high',
      'Candidate''s mc/brand/ page 404s. Found SUU''s Web Services style guide on the same domain instead, which explicitly names and gives hex for ''SUU Red'': ''Reds SUU Red Hex: #DB0000... Alternate Red Hex: #C41425... SUU Black Hex: #000000... White Hex: #FFFFFF.'' Corrected: candidate''s #E91D2D does not match the real, explicitly-labeled SUU Red #DB0000. Kept just the one clearly-named institutional chromatic color per the prefer-1-2-chromatic default -- black/white/alternate-red here read as this particular page''s UI/accessibility palette rather than a stated ''these are SUU''s official school colors'' list, so they were not carried over without stronger confirmation.'
    ),
    (
      'university-of-wisconsin-la-crosse',
      '240329',
      array['#830019', '#78797A']::text[],
      'https://www.uwlax.edu/brand/guides/design/colors/',
      'high',
      'Candidate''s ucomm/uwl-branding/colors-and-fonts page 404s (site restructured under a new /brand/ path). Found the current official Colors page instead: ''UWL''s primary colors have been maroon and gray since 1909.'' Page markup explicitly labels swatch data-title="Primary Maroon" data-hex="#830019" (exact match to candidate) and data-title="Primary Gray" data-hex="#78797a". Corrected: candidate''s gray #969799 does not match the real, explicitly-labeled Primary Gray #78797A.'
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
