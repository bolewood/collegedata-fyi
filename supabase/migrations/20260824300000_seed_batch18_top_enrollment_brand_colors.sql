-- Batch 18 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a reorder
-- and/or a dropped mechanically-attached white (hex matched the official
-- source verbatim once a live copy was located): campbell-university
-- (white/orange/black -- official athletics style guide, reordered to the
-- doc's own "orange first, then black, then white" hierarchy), carthage-
-- college (red RGB-stated + black, both parts of the school's repeated
-- two-color footer statement; white dropped), rogers-state-university
-- (blue/red, both stated with hex/RGB on the current Logos & Colors page;
-- white dropped), rollins-college (blue/gold, exact -- PDF recovered via
-- the college's own scholarship repository after the cited rollins.edu
-- link 404d), tuskegee-university (crimson/gold, exact; white dropped),
-- regis-university (blue/gold, exact; white dropped), st-john-fisher-
-- university (cardinal/gold, exact; white dropped), framingham-state-
-- university (gold/black, exact 2-hex match, confirmed as-is via Wayback
-- after the cited PDF 404d), drake-university (blue RGB-stated + gray hex,
-- exact, from the Missouri Valley Conference's Drake-specific branding
-- page; white dropped), wingate-university (blue/gold "hero colors" from
-- the site's Color & Typography brand-post page, exact; white dropped),
-- cameron-university (black/gold, exact -- official guide recovered
-- directly from cameron.edu after the cited studylib.net link was blocked
-- by a bot wall; white dropped).
--
-- Wrong-swatch / wrong-tier / stale corrections (candidate hex did not
-- match the school's own current official source):
-- george-fox-university (candidate hex matched neither the main brand
-- guide, which gives Pantone/CMYK only, nor the athletics brand book;
-- corrected to the athletics book's literal Navy #082044 / Old Gold
-- #C2A204), skidmore-college (gold corrected from #FFD100 to the
-- athletics guide's stated #FFC600; a near-duplicate darker-green primary
-- shade was deliberately dropped so the ink-deriver doesn't pick it over
-- the school's actual hero green), university-of-mount-saint-vincent
-- (gold and "navy" both wrong -- candidate's #007E95 is a teal that
-- doesn't appear anywhere in the school's 2024 Brand Guidelines; corrected
-- to Gold #C99700 / Navy #003057, white kept since it's 1 of exactly 3
-- named primary colors), fort-valley-state-university (both blue and gold
-- corrected against the current 2020 Brand Standards Guide, replacing a
-- dead 2012 PDF citation), milwaukee-school-of-engineering (red corrected
-- from #BA122B to the Brand Manual's stated #C5050C; white+black kept,
-- both are 2 of exactly 3 named Primary Palette colors), florida-southern-
-- college (candidate's blue/red did not match anything on the official
-- Color and Typography page at all -- a clear wrong-swatch pull; corrected
-- to the page's actual sole Primary pair, FSC Red #C1002A + white),
-- francis-marion-university (candidate's blue/red actually came from the
-- page's separate "Approved web site colors" list, not the "official
-- school colors" statement; corrected to the stated Red/White/Blue set),
-- montana-state-university-billings (blue corrected from #002F5F to the
-- current guidelines page's stated #15356D; white dropped, it's not named
-- as an official color here), lee-university (recovered via Wayback after
-- the live leeuflames.com/goleeflames.com domain started returning a
-- generic Sidearm landing page to every document path; RGB-derived hex
-- confirmed candidate's values, reordered to Cardinal+White primary,
-- Navy secondary), palm-beach-atlantic-university (candidate's #002B5C did
-- not match the current 2026 Brand Standards' sole stated primary,
-- #0C2340; reduced to that single color since nothing else, including
-- white, is named official), truman-state-university (candidate paired
-- Primary Purple with Tertiary White; corrected to the documented
-- Primary+Secondary chromatic pair, purple + blue, which better preserves
-- the school's actual two-color identity), trinity-university (candidate's
-- maroon/gray are stale pre-2026-rebrand values; Trinity rebranded this
-- year and the current site states a new Primary Palette, Maroon #870A0F
-- + white), augsburg-university (candidate's maroon/gray matched nothing
-- stated; the official page gives only Pantone for both colors except one
-- explicit web-hex callout for maroon, #660033 -- reduced to that single
-- unambiguously-sourced value rather than guess at an unlabeled gray).
--
-- Left null (no usable on-domain hex/RGB found after a documented search;
-- see data/brand-colors/batch-18-2026-08-24.jsonl for full per-school
-- detail): keene-state-college (cited page returns HTTP 200 with a
-- genuinely empty body in curl, WebFetch, and a rendered browser alike;
-- only Pantone-186 is named anywhere), niagara-university (official page
-- names only "Purple (PMS 268) & White", no hex/RGB on domain),
-- central-state-university (only source found is an image-only Yumpu
-- flipbook with no extractable text and conflicting third-party Pantone
-- claims), western-new-england-university (current graphic-standards PDF
-- specifies every color as Pantone-only, no hex/RGB anywhere), stonehill-
-- college (official Colors & Typography page shows Pantone swatches as
-- images only, no hex/RGB text), ohio-northern-university (athletics page
-- has no color text at all; on-domain apparel guide names "orange, black
-- and white" but gives no hex/RGB; the full branding guidelines PDF is
-- blocked by a bot wall on studylib.net in curl, WebFetch, and a rendered
-- browser alike, so its claimed values could not be independently
-- verified).
--
-- Every populated row was run through the production deriveInks()/
-- glyphInks() (web/src/lib/derive-inks.ts) via a throwaway vitest case
-- before finishing (deleted, not committed). All 24 populated rows produce
-- their own derived plates (house=false) -- no school in this batch loses
-- its chromatic primary to the house forest/ochre fallback. One data point
-- worth flagging: drake-university's stated companion color, Cool Gray 5
-- (#B3B3B0), is correctly treated as neutral by the deriver (chroma below
-- threshold) and never itself surfaces as a rendered plate -- the value is
-- still real and sourced, just not chromatic enough to anchor a plate.
-- See data/brand-colors/batch-18-2026-08-24.jsonl for the full per-school
-- record, including the six null entries.

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
      'george-fox-university',
      '208822',
      array['#082044','#C2A204']::text[],
      'https://www.georgefox.edu/offices/communications/resources/athletics-brand-identity.pdf',
      'high',
      'Candidate citation 404s. Main Brand Style Guide gives only CMYK/Pantone for Navy/Slate Blue/Accent Red/Sun Gold, no hex anywhere. Found the Feb-2024 Athletics Brand Book instead: "Navy Blue is George Fox Athletics'' primary color" PANTONE 282 C HEX #082044; "Old Gold is George Fox University''s accent color" PANTONE 457 HEX #C2A204 RGB(192,161,46) -- the traditional Navy/Old Gold school colors. Candidate''s #081E3F/#BC9C16 matched neither; corrected. White (also stated) dropped, not part of the 2-color identity.'
    ),
    (
      'skidmore-college',
      '195526',
      array['#006A52','#FFC600']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/skidmoreathletics.com/documents/2023/10/17/Athletics_SG_OneSheet_vF.pdf',
      'high',
      'Candidate''s color.php citation 404s. Official Skidmore Athletics Brand and Style Guide states three "PRIMARY COLORS" (green #006A52, a darker-shade green #004438, gold #FFC600) plus one secondary light blue-gray. Candidate''s green matched exactly; gold (#FFD100) did not match the stated #FFC600 and was corrected. Dropped the near-duplicate darker-green shade and the secondary blue-gray -- keeping it would make the ink-deriver pick the darker shade over the school''s actual hero green as the dark plate.'
    ),
    (
      'university-of-mount-saint-vincent',
      '193399',
      array['#C99700','#003057','#FFFFFF']::text[],
      'https://university.mountsaintvincent.edu/wp-content/uploads/2024/08/UMSV-2024-Brand-Guidelines.pdf',
      'high',
      'Candidate''s cmsvathletics.com citation domain is dead/renamed; the live umsvathletics.com quick-facts page names only "Gold, Navy Blue" with Pantone 117/540, no hex. Official 2024 UMSV Brand Guidelines "Primary Colors" states exactly three official colors -- Gold HEX #C99700, Hudson Navy HEX #003057, White HEX #FFFFFF. Candidate''s gold (#C5B358) and "navy" (#007E95, actually a teal -- wrong swatch) did not match; corrected. White kept, it is explicitly 1 of exactly 3 named primaries.'
    ),
    (
      'fort-valley-state-university',
      '139719',
      array['#205097','#F2C442']::text[],
      'https://www.fvsu.edu/content/userfiles/files/FVSU-BrandStandardsGuide_2020.pdf',
      'high',
      'Candidate''s www2.fvsu.edu citation domain does not resolve. Current official 2020 Brand Standards Guide on fvsu.edu: "Primary Palette" Blue HEX #205097, Gold HEX #F2C442. Candidate''s blue (#003087) and gold (#EAAA00) did not match the current primary hex; corrected.'
    ),
    (
      'campbell-university',
      '198136',
      array['#FB471F','#000000','#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/campbell.sidearmsports.com/documents/2023/6/30/Campbell_StyleGuide.pdf',
      'high',
      'Candidate citation resolved and text-extracted cleanly. "The official colors of Campbell Athletics are white, orange and black... hierarchy is orange first, then black, then white." HTML FB471F / 000000 / FFFFFF -- matches candidate''s three hexes exactly. Reordered to the document''s own stated hierarchy; kept all three since white+black are 2 of only 3 named official colors.'
    ),
    (
      'wingate-university',
      '199962',
      array['#00205B','#C5B783']::text[],
      'https://www.wingate.edu/the-wingate-brand/brand-post/~board/branding-guidelines/post/color-typography',
      'high',
      'Candidate''s landing citation exposes no static text; found the site''s dedicated Color & Typography brand-post page. "Wingate Blue and Gold are our hero colors" -- Wingate Blue Hex 00205B, Wingate Gold Hex C5B783. Matches candidate exactly; white (not mentioned in the page''s color system) dropped.'
    ),
    (
      'carthage-college',
      '238476',
      array['#D72316','#000000']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/athletics.carthage.edu/documents/2021/11/15/Athletics_Brand_guidelines_2021_Final_1_.pdf',
      'high',
      'Candidate citation resolved and text-extracted cleanly. Every page footer: "CARTHAGE COLORS: PMS 3517 . RGB: R215 G35 B22 . Black" -- exactly two official colors (RGB-stated red =#D72316, matches candidate, plus Black). White appears nowhere in that statement; candidate''s white was an unwarranted mechanical append and was dropped.'
    ),
    (
      'rogers-state-university',
      '207661',
      array['#0C2340','#BA0C2F']::text[],
      'https://www.rsu.edu/offices-services/communications-marketing/branding/',
      'high',
      'Candidate''s logo-samples-usage/ citation 404s; found the current Logos & Colors page at rsu.edu. "Blue (primary) and Red (secondary)... Blue Hex #0C2340; Red PMS 200C RGB 186,12,47" (=#BA0C2F). Matches candidate''s blue/red exactly. White is not part of this 2-color statement and was dropped.'
    ),
    (
      'florida-southern-college',
      '134079',
      array['#C1002A','#FFFFFF']::text[],
      'https://www.flsouthern.edu/campus-offices/offices-directory/office-of-marketing-and-communication/brand-guidelines/color-and-typography',
      'high',
      'Candidate''s fscmocs.com/StyleGuide citation 404s. Current flsouthern.edu Brand Guidelines "Color and Typography" page lists exactly two Primary Colors: FSC Red hex c1002a Pantone PMS 200C, and White hex ffffff -- no blue anywhere. Candidate''s blue (#0060A9) and secondary red (#E03A3E) matched nothing here, a clear wrong-swatch pull; corrected to the actual primary set.'
    ),
    (
      'milwaukee-school-of-engineering',
      '239318',
      array['#C5050C','#FFFFFF','#000000']::text[],
      'https://msoe.s3.amazonaws.com/files/resources/msoe-brandmanual-f-lowres.pdf',
      'high',
      'Candidate''s exact filename 403s from the S3 bucket; found the current MSOE Brand Manual at the same bucket/prefix. "PRIMARY PALETTE": Red RGB 197/5/12 HEX #C5050C; White HEX #FFFFFF; Black HEX #000000 -- all three explicitly primary with hex stated. Candidate''s red (#BA122B) did not match; corrected. Kept white+black, they are 2 of exactly 3 named Primary Palette colors.'
    ),
    (
      'rollins-college',
      '136950',
      array['#0071BA','#FACF00']::text[],
      'https://scholarship.rollins.edu/context/brand_guide/article/1001/viewcontent/rollins_brand_guide.pdf',
      'high',
      'Candidate''s rollins.edu citation 404s; recovered the identical official 2018 Rollins Brand Guide via the college''s own scholarship repository (curl was bot-blocked; fetched through a rendered browser session, verified byte-for-byte, then text-extracted). "Although blue and gold are the official Rollins colors" -- Blue Hex 0071BA, Gold Hex FACF00. Matches candidate exactly; white dropped, not part of the 2-color official statement.'
    ),
    (
      'tuskegee-university',
      '102377',
      array['#7B0707','#F2BD2C']::text[],
      'https://www.tuskegee.edu/Content/Uploads/Tuskegee/files/OCPRM/Brand-Standards-Manual.pdf',
      'high',
      'Candidate''s PolicyManual.pdf citation 404s; found the current Brand Standards Manual at the same OCPRM path. "The official university website colors are (HEX) Red: #7b0707 and Gold: #f2bd2c." Matches candidate''s crimson/gold exactly; white (not named as an official color) dropped.'
    ),
    (
      'francis-marion-university',
      '218061',
      array['#003A70','#B7312C','#FFFFFF']::text[],
      'https://www.fmarion.edu/communications/mediaresources/',
      'high',
      'Candidate''s /news/colors citation is a lorem-ipsum placeholder page. Live Media Resources page: "Official school colors are Red, White, and Blue -- Blue PMS 654 #003A70; Red PMS 7260 #B7312C; White #ffffff." A separate "Approved web site colors" list also exists on the same page but is a distinct secondary palette; candidate''s blue/red actually came from that list, not the official-colors statement. Corrected to the primary Red/White/Blue set, keeping white since it is 1 of exactly 3 named official colors.'
    ),
    (
      'regis-university',
      '127918',
      array['#002B49','#F1C400']::text[],
      'https://one.regis.edu/_documents/university-operations/marcom/regisu-brand-standards.pdf',
      'high',
      'Candidate''s marcom.regis.edu citation domain does not resolve; found the current Brand Standards PDF at one.regis.edu. "Color Palette" states Regis Blue HEX #002B49 and Regis Gold HEX #F1C400, with three lower-tier "Accent" colors following. Matches candidate exactly; white dropped, not part of the primary color-palette statement.'
    ),
    (
      'montana-state-university-billings',
      '180179',
      array['#15356D','#F0B310']::text[],
      'https://www.msubillings.edu/ucam/guidelines.htm',
      'high',
      'Candidate''s guidelines.htm citation redirects to the current live page at the same path. "PRIMARY COLORS: MSUB Blue -- Web hex #15356D; MSUB Gold -- Web hex #F0B310." Black is listed separately as a "SECONDARY COLOR," white is not an official color at all. Candidate''s blue (#002F5F) did not match; corrected. White dropped.'
    ),
    (
      'lee-university',
      '220613',
      array['#6F263D','#FFFFFF','#0D233F']::text[],
      'http://www.goleeflames.com/documents/2016/7/18/Lee_U_Athletics_Style_Guide.pdf',
      'high',
      'leeuflames.com/goleeflames.com now return a generic Sidearm landing page to curl and a rendered browser alike for every documents/ path (2016 and 2024 guides both); recovered the exact candidate PDF via a 2017 Wayback capture. "PRIMARY COLORS: Nike White; Nike Cardinal PANTONE 209 C R111 G38 B61" (=#6F263D). "SECONDARY COLORS: Nike Navy PANTONE 289 C R13 G35 B63" (=#0D233F). RGB-derived hex matches candidate''s cardinal/navy exactly; reordered to Cardinal+White (primary) then Navy (secondary).'
    ),
    (
      'palm-beach-atlantic-university',
      '136330',
      array['#0C2340']::text[],
      'https://issuu.com/pba.edu/docs/pba_brand_standards_2026',
      'high',
      'Candidate''s pbasailfish.com quick-facts page names only "Navy Blue and White," no hex. Found PBA''s current (2026) official Brand Standards guide on the school''s own Issuu account, linked from pba.edu/advancement; text extracted via a rendered browser session. "Pantone 289 is the official primary color of Palm Beach Atlantic University" -- HEX 0c2340 is the ONLY named primary color; accent colors "may not be used as alternatives," white is not listed anywhere in the Color System. Candidate''s #002B5C did not match; corrected and reduced to the single stated primary.'
    ),
    (
      'framingham-state-university',
      '165866',
      array['#EBAB00','#000000']::text[],
      'https://www.framingham.edu/Assets/uploads/about-fsu/marketing-and-communications/documents/071517_EMG-Branding_StyleGuide_final.pdf',
      'high',
      'Candidate''s exact citation URL 404s on both framingham.edu and www.framingham.edu; recovered the identical PDF via a 2023 Wayback capture. "MAIN COLORS: FSU Gold HEX #EBAB00, FSU Black HEX #000000" -- "The main colors of the University are FSU gold (PMS 124) and black." Matches candidate exactly, confirmed as-is.'
    ),
    (
      'st-john-fisher-university',
      '195720',
      array['#993333','#FFCC33']::text[],
      'https://www.sjf.edu/services/style-guide/colors-and-typography/',
      'high',
      'Candidate citation resolved and text-extracted cleanly. "St. John Fisher University''s colors are gold and cardinal red... Hex = #993333 [cardinal]... Hex = #FFCC33 [gold]." Matches candidate''s two chromatic hexes exactly; white (not named as an official color) dropped.'
    ),
    (
      'drake-university',
      '153269',
      array['#1B4677','#B3B3B0']::text[],
      'https://s3.amazonaws.com/sidearm.sites/mvc.sidearmsports.com/documents/2022/8/29/Style_Guide_Full_Version.pdf',
      'high',
      'Candidate citation resolved and text-extracted cleanly. "DRAKE BRANDING -- COLORS: PMS 294 / RGB 27,70,119" (=#1B4677) paired with "PMS Cool Gray 5 / HEX #B3B3B0" -- no third color, no white. Matches candidate''s values exactly; white dropped (never in source). Source is a Missouri Valley Conference guide with a Drake-specific branding page, treated as an official athletics brand guide.'
    ),
    (
      'truman-state-university',
      '178615',
      array['#510C76','#00A8E2']::text[],
      'https://identity.truman.edu/files/2020/06/Athletics-Brand-Guide.pdf',
      'high',
      'Candidate citation resolved and text-extracted cleanly. "PRIMARY PURPLE HEX #510C76; SECONDARY BLUE HEX #00A8E2; TERTIARY WHITE HEX #FFFFFF; BLACK HEX #000000." Candidate paired Primary Purple with Tertiary White, not the actual Secondary color; corrected to the documented Primary+Secondary chromatic pair (purple + blue), better representing the school''s two-color identity.'
    ),
    (
      'trinity-university',
      '229267',
      array['#870A0F','#FFFFFF']::text[],
      'https://trinity.edu/brand/visual/colors',
      'high',
      'Candidate''s dam.trinity.edu Brand Portal SPA citation 404s. Trinity rebranded in 2026 ("sun imagery" identity, per contemporaneous local press); current trinity.edu/brand/visual/colors states "Primary Palette -- Trinity Maroon HEX #870A0F; White HEX #FFFFFF" -- exactly two Primary colors, with a separate Secondary and Accent palette. Candidate''s maroon (#723130) and gray (#BBBCBC) are stale pre-rebrand values matching nothing in the current palette; substantially corrected.'
    ),
    (
      'augsburg-university',
      '173045',
      array['#660033']::text[],
      'http://inside.augsburg.edu/marketing/style_guidelines/',
      'high',
      'Candidate citation resolved. Page states "two Pantone Matching System colors: PMS 209 (maroon) and PMS Cool Gray 9" with no hex for either at first, but continues "On the Web: For Augsburg maroon, use hex code #660033." No comparable stated hex exists for the gray -- a linked color-combinations chart shows two different unlabeled grays with no indication which is "Cool Gray 9." Candidate''s #75263B/#747678 matched neither; corrected and reduced to the single unambiguously-sourced maroon.'
    ),
    (
      'cameron-university',
      '206914',
      array['#000000','#FFC425']::text[],
      'https://www.cameron.edu/storage/departments/public-affairs/branding-guide/CU_Branding_Guide_4.22.pdf',
      'high',
      'Candidate''s studylib.net citation is blocked by a bot-security wall in curl, WebFetch, and a rendered browser alike. Found the actual official April-2022 Branding Guide hosted directly on cameron.edu. "The official colors of Cameron are black (Pantone Black) and gold (Pantone 123)" -- Gold HEX #FFC425, Black HEX #000000. Matches candidate''s black/gold exactly; white dropped, not part of the 2-color official statement.'
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
