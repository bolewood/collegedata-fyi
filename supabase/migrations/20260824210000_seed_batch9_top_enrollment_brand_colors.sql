-- Batch 9 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Most candidate citation URLs had rotted (dead sidearm/S3 PDFs, restructured
-- .edu paths, image-only PDFs with zero extractable text, live-but-unrelated
-- sports-news/press-room pages, Cloudflare-gated domains) or were dead ends
-- that required searching the school's current domain for a replacement.
-- Every school below was re-sourced against the school's own current
-- official domain where possible, verified by downloading PDFs and running
-- pdftotext -layout/-raw (never trusting a fetch-tool summary of a PDF), or
-- by reading the raw HTML/CSS/SVG text of an official page (via direct
-- fetch or, where a domain blocked automated fetches, a Wayback Machine
-- capture of the exact same official URL).
--
-- Caught mid-batch (wrong-swatch pull, exactly the risk this batch is built
-- to guard against): southern-illinois-university-edwardsville's candidate
-- citation was a multi-school Ohio Valley Conference PDF whose SIUE row
-- (PMS 485, RGB->#D81E05) is NOT the same red as SIUE's own current official
-- brand guidelines PDF (PMS 186C, #E5182D) -- resolved in favor of the
-- university's own document over the conference-wide one. Also caught:
-- university-of-california-merced had two disagreeing on-domain sources (an
-- older WordPress brand page with an internally-inconsistent Hex/RGB pair,
-- vs. the current Foleon-hosted brand portal whose Hex agrees with its own
-- RGB and matches the candidate) -- resolved via the newer, internally
-- consistent source. youngstown-state-university's single official PDF has
-- its own internal Hex/RGB mismatch (HEX CODE: C8333B vs RGB(203,51,59) =
-- CB333B) that could not be resolved against a second source; stored the
-- literal stated hex rather than silently substituting a derived value, and
-- downgraded confidence to medium as a result.
--
-- Real, non-trivial hex corrections (official value differs meaningfully
-- from the Wikipedia candidate, not just a formatting fix): morgan-state-
-- university (blue and orange both corrected -- none of the three candidate
-- values matched), tennessee-technological-university (purple and gold both
-- corrected, candidate looks like a stale pre-refresh pull), university-of-
-- maine (both blues corrected, same stale-pull pattern), california-state-
-- university-stanislaus (all three candidate values replaced by the current,
-- Jan-2026-updated official palette), colorado-mesa-university (maroon
-- corrected from #5D0022 to the real "Mavroon" #860037, gold dropped as an
-- accent color), lamar-university (red corrected via lossless RGB->hex
-- conversion of the school's own stated RGB triplet), ferris-state-
-- university and university-of-wyoming (both confirmed exactly on a
-- corrected/working URL), southern-illinois-university-edwardsville (see
-- wrong-swatch note above), youngstown-state-university (see internal-
-- inconsistency note above, plus white swapped for the source's actual
-- black), northern-kentucky-university (gold corrected), south-dakota-
-- state-university (blue corrected by one digit), central-washington-
-- university (a near-black third value replaced with the source's actual
-- stated black).
--
-- Confirmed as-is or with only a neutral dropped/reordered (candidate's
-- chromatic hex(es) matched the current official source): university-of-
-- akron-main-campus, new-jersey-institute-of-technology (red confirmed,
-- white kept as one of only two stated primaries, fabricated-looking accent
-- blue dropped), columbia (both blues kept, fabricated black dropped),
-- cleveland-state-university (white/black dropped, real second primary
-- Fresh Green added), university-of-wisconsin-eau-claire, university-of-
-- south-alabama (all three, confirmed exactly), university-of-notre-dame
-- (white demoted -- explicitly "supporting" not primary), texas-womans-
-- university (white kept, black dropped), stephen-f-austin-state-university
-- (single stated primary purple only), university-of-colorado-colorado-
-- springs (white dropped), southern-illinois-university-carbondale (white
-- dropped), louisiana-tech-university (confirmed exactly, no correction),
-- california-baptist-university (all three, confirmed exactly).
--
-- Lower-confidence outcomes (official source unreachable; fell back to a
-- reputable secondary index per source-priority tier 4, confirmed by
-- reading the actual cited page's text myself): arkansas-state-university,
-- wilmington-university (no public university-wide brand page found at
-- all), central-washington-university (crimson corroborated via an
-- on-domain SVG fill in addition to the secondary index, so medium rather
-- than low).
--
-- No school was left null this batch -- every official or fallback search
-- turned up at least one corroborated chromatic hex.
--
-- Plates are still derived at render (deriveInks() / glyphInks()); this
-- stores source hexes only. Every finalized pair/triple was run through
-- production deriveInks()/glyphInks() (paper #f1ece1, MIN_B_ON_CREAM=1.25)
-- via a throwaway port of the same algorithm: none fell through to the
-- house-ink path, so no real chromatic primary was lost to a fallback in
-- this batch (a handful of single-chromatic-plus-neutral entries, e.g. UCCS
-- black+gold and Lamar red+white, correctly filter the neutral member and
-- fall back to charcoal for the A plate while keeping the real chromatic as
-- B -- expected algorithm behavior, not a lost primary). See
-- data/brand-colors/batch-9-2026-08-24.jsonl for the full per-school record.

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
      'northwestern',
      '147767',
      array['#4E2A84']::text[],
      'https://www.northwestern.edu/brand/visual-identity/color-palettes/',
      'high',
      'Candidate''s northwestern.edu/auxiliary-services PDF returns a live but unrelated Procurement & Payment Services page (404 content), no brand data. Found and read Northwestern''s current official Color Palettes page instead: ''Our visual branding relies almost exclusively on a proprietary Northwestern Purple,'' with the primary swatch table giving HTML: #4E2A84 for Northwestern Purple. Rich Black is presented as a tint scale (100%/90%/80%/50%/20%/10%) with only some percentages carrying a stated hex (e.g. 80% = #342F2E), not a single named ''black'' swatch, and no hex is given for white anywhere on the page (''White Space'' is a bare section heading with no swatch). Corrected: dropped candidate''s white and black -- neither has a stated hex as a primary color; purple is effectively the sole primary chromatic, consistent with the page''s own ''almost exclusively'' framing. Kept just the one clearly-stated primary per the prefer-1-2-chromatic default.'
    ),
    (
      'south-dakota-state-university',
      '219356',
      array['#0033A0', '#FFD100']::text[],
      'https://gojacks.com/sports/2017/7/17/pressroom.aspx',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly. Page''s own ''SDSU ATHLETICS LOGOS & SCHOOL COLORS'' section states: ''COLORS YELLOW BLUE ... RGB - 255r 209g 0b ... Hex - #ffd100 ... RGB - 0r 51g 160b ... Hexadecimal - #0033a0.'' Corrected: candidate''s blue #0032A0 is a one-digit typo of the real, explicitly stated #0033A0; candidate''s white dropped -- the page names exactly two official colors (yellow and blue), no white.'
    ),
    (
      'arkansas-state-university',
      '106458',
      array['#CC092F', '#000000']::text[],
      'https://teamcolorcodes.com/arkansas-state-red-wolves/',
      'low',
      'Candidate''s astate.edu/a/marketing/... URL 404s (site restructured). The school''s own current knowledge-base export (kb.astate.edu/books/logos-colors-fonts) discusses ''A-State Red (PANTONE 186), A-State Black... and white'' as approved one-color logo variants but states no hex anywhere in extractable text -- the only #cc092f occurrence found on-domain is an incidental inline text-highlight style, not a stated brand-color swatch, so it wasn''t relied on alone. Fell back to a reputable secondary index per tier 4, confirmed by reading its actual swatch table: ''Arkansas State Red Wolves Primary Logo Colors Scarlett... Hex Color: #cc092f... Black... Hex Color: #000000.'' Scarlet matches the candidate exactly; corrected: candidate''s white dropped -- the school''s own materials describe only Red and Black as official logo colors, no white swatch given a hex anywhere. Low confidence: no official on-domain hex was reachable.'
    ),
    (
      'university-of-akron-main-campus',
      '200800',
      array['#041E42', '#A89968']::text[],
      'https://gozips.com/documents/download/2018/6/19/Brand_Guide_2018_digital.pdf',
      'high',
      'Candidate''s s3.amazonaws.com/sidearm.sites PDF 404s. Found and text-extracted the same 2018 Brand Guide re-hosted on gozips.com instead: ''The primary colors for Akron Athletics are Akron Blue (PMS 282) and Akron Gold (PMS 871)... HTML: #041E42... HTML: #A89968.'' Both candidate chromatic values confirmed exactly. Corrected: candidate''s white dropped -- the document names exactly two primary colors (blue and gold); white/black are not part of the primary pair.'
    ),
    (
      'morgan-state-university',
      '163453',
      array['#1B4383', '#F47937']::text[],
      'https://www1.morgan.edu/toolkit/official-colors/',
      'high',
      'Candidate''s morgan.edu/toolkit/colors/ URL 404s (moved to www1 subdomain with a renamed path). Found and read the current Branding Toolkit Official Colors page instead: ''Morgan Blue in lieu of which use *Pantone(R) 288... Hex: #1B4383'' and ''Morgan Orange in lieu of which use Pantone(R) 1655... Hex: #F47937,'' explicitly the two official school colors. Substantial correction: none of the candidate''s three values (#002D74, #FFFFFF, #FF4E00) match the real official blue/orange -- this looks like a stale or fabricated candidate pull. Black and white are explicitly listed on the same page only as ''Support Colors... to add contrast to Morgan Blue and Morgan Orange,'' not primary, and brown/gold are a separate ''Secondary Colors'' tier -- both excluded per the prefer-1-2-chromatic default.'
    ),
    (
      'new-jersey-institute-of-technology',
      '185828',
      array['#CC0000', '#FFFFFF']::text[],
      'https://www.njit.edu/communications/sites/njit.edu.communications/files/2019%20NJIT%20Branding%20Guidelines_r1.pdf',
      'high',
      'Candidate''s www5.njit.edu PDF redirects through several hops to the general Communications landing page (dead link). Found and text-extracted NJIT''s current 2019 Branding Guidelines PDF instead: ''NJIT primary color palette. The official school colors are NJIT Red (Pantone 1795) and White... RGB/web-safe R:204, G:0, B:0'' (=#CC0000, exact match to candidate) grouped explicitly with White as the two-color primary set -- not a mechanical append. Corrected: candidate''s third value, Accent Blue, is explicitly in a separate ''Accent color'' secondary tier with its own stated HTML #1C1475 (not candidate''s #071D49, which doesn''t appear anywhere in the document) -- dropped, since only Red and White are the stated ''official school colors.'''
    ),
    (
      'columbia',
      '190150',
      array['#1D4F91', '#B9D9EB']::text[],
      'https://visualidentity.columbia.edu/content/color',
      'high',
      'Candidate''s /branding URL sits behind a Cloudflare JS challenge that blocks automated fetches; confirmed the same domain''s dedicated Color content page via a Wayback Machine mirror of the live URL instead (read as real extracted text, not a tool summary): a structured color table gives ''Columbia Blue Hex #B9D9EB'' (heritage/iconic swatch) and, under ''Primary Color... should represent at least 60 percent of the total color usage,'' ''Primary Blue Hex #1D4F91'' (matches candidate''s third value exactly). Corrected: candidate''s #000000 does not appear anywhere on the page as a named color -- the closest neutral is ''Neutral 1... Hex #222222 (Pantone Neutral Black C),'' explicitly a Neutral-tier swatch, not black and not primary. Kept both blues (Columbia Blue is the university''s iconic heritage color; Primary Blue is the current digital-brand primary, and the page states white may also be used as a primary) rather than guess which one is ''the'' answer; dropped the fabricated black.'
    ),
    (
      'cleveland-state-university',
      '202134',
      array['#006A4D', '#69BE28']::text[],
      'https://www.csuohio.edu/sites/default/files/CSU_Brand-Guidelines_01-2023.pdf',
      'high',
      'Candidate''s /marketing/color-palette URL 404s. Found and text-extracted the current CSU Brand Guidelines PDF instead: ''PRIMARY COLORS... University Green... HEX: 006A4D... Fresh Green... HEX: 69BE28... This color palette should be the primary colors used in marketing materials.'' Corrected: candidate''s white and black both dropped -- they don''t appear in the Primary Colors section at all (Baby Blue/Golden Yellow/Plum are a separate Secondary tier, Mango/Indigo/Silver Grey a separate Accent tier); the real second primary is Fresh Green, not a neutral.'
    ),
    (
      'university-of-wisconsin-eau-claire',
      '240268',
      array['#2B3E85', '#EDAC1A']::text[],
      'https://cdn.uwec.edu/uwec14/files/uwec-brand-manual-4-16-14.pdf',
      'high',
      'Candidate''s cdn.uwec.edu URL 404s live; the current uwec.edu site has migrated away from this brand-manual path with no obvious un-gated successor page found. Retrieved and text-extracted the exact cited PDF via a Wayback Machine capture instead: ''Primary Color Palette... the official university colors: Blue PMS 2747... HEX #2b3e85... Gold PMS 130... HEX #edac1a.'' Both candidate values confirmed exactly. Confirmed as-is; low-risk correction only in that the live citation URL is dead and had to be read via archive.'
    ),
    (
      'university-of-south-alabama',
      '102094',
      array['#00205B', '#BF0D3E', '#FFFFFF']::text[],
      'https://www.southalabama.edu/departments/publicrelations/brand/',
      'high',
      'Candidate''s /brand/resources/usa_brand_guidelines.pdf 404s. Found and text-extracted the live USA Brand page instead: ''USA Red (Pantone 193), USA Blue (Pantone 281) and USA White are our primary colors... USA Blue... HEX 00205B... USA Red... HEX BF0D3E... USA White... Hex: FFFFFF.'' All three candidate values confirmed exactly; white is explicitly one of only three named primary colors here, not a mechanical append. Confirmed as-is.'
    ),
    (
      'university-of-notre-dame',
      '152080',
      array['#0C2340', '#C99700']::text[],
      'https://onmessage.nd.edu/athletics-branding/colors/',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly: ''The official colors of Notre Dame athletics are blue and gold... Notre Dame Blue... #0c2340... Standard Dome Gold... #c99700.'' Both candidate chromatic values confirmed exactly. Corrected: candidate''s white dropped -- the same page states ''White is a supporting color in conjunction with blue and gold,'' explicitly not one of the primary pair; Irish Green (#00843D) is likewise flagged as an ''accent color to be used sparingly,'' also excluded.'
    ),
    (
      'texas-womans-university',
      '229179',
      array['#850928', '#FFFFFF']::text[],
      'https://twu.edu/marketing-communication/brand-guidelines/',
      'high',
      'Candidate''s sidearmsports.com S3 athletics PDF 404s. Found and read TWU''s own current Brand Guidelines page instead: ''Maroon PMS | 202C ... HEX | 850928 White PMS | N/A ... HEX | FFFFFF'' listed together ahead of a separate ''Secondary Colors'' heading (Amaranth/Eggplant/Gold). Maroon matches candidate exactly; white is explicitly grouped with maroon as a primary pair, not mechanically appended. Corrected: candidate''s black dropped -- ''black of text'' is only mentioned as a usage note about body copy, never given its own swatch/hex as an official color.'
    ),
    (
      'southern-illinois-university-edwardsville',
      '149231',
      array['#E5182D', '#B9975B']::text[],
      'https://www.siue.edu/marketing-and-communications/pdf/siue-brand-guidelines.pdf',
      'high',
      'Candidate''s citation is a multi-school Ohio Valley Conference style guide (ovcsports.com/documents/.../OVC_Style_Guide.pdf), not an SIUE-specific source -- exactly the wrong-swatch-pull risk the batch brief warns about. That PDF''s actual SIUE row reads ''485 Red (216, 30, 5)'' which does convert to candidate''s #D81E05, but is only a Pantone/RGB reference in a shared conference nickname table, not SIUE''s own branding. Found and text-extracted SIUE''s own current official Brand Guidelines PDF instead: ''PRIMARY COLOR PALETTE... PMS 186 C... HEX #e5182d'' (SIUE Red, ''the dominant accent color in most communications'') and ''PMS 465... HEX #b9975b'' (''Primarily used when representing Eddie the Cougar''). Corrected: the conference guide''s red (#D81E05/PMS 485) does not match SIUE''s own current brand red (#E5182D/PMS 186C) -- a real discrepancy between two nominally ''official'' sources, resolved in favor of the university''s own current .edu brand guidelines PDF over the older/generic conference document. Candidate''s white and the document''s own PMS 427 gray/black swatches are described as background/typography support, not chromatic identity -- dropped per the prefer-1-2-chromatic default.'
    ),
    (
      'stephen-f-austin-state-university',
      '228431',
      array['#5F259F']::text[],
      'https://www.sfasu.edu/docs/umc/sfa-official-university-identity-standards-manual.pdf',
      'high',
      'Candidate''s www.sfasu.edu/pubaffairs/... path 404s (moved under /docs/umc/). Found and text-extracted the current Identity Standards Manual (Oct 2024) at the corrected path: ''OFFICIAL COLOR PALETTE PRIMARY COLOR Purple should be used as the main, dominant color at all times... HEX/Web #5f259f.'' Matches candidate''s purple exactly, and the document names exactly one ''PRIMARY COLOR.'' Corrected: candidate''s white (never appears anywhere in the document) and #B1B3B3 (which does appear, but as ''Black 25%'' -- a tint of the Secondary Palette''s black scale, not a distinct primary gray or white) both dropped -- purple alone is the stated primary.'
    ),
    (
      'tennessee-technological-university',
      '221847',
      array['#753BBD', '#FFD100']::text[],
      'https://www.tntech.edu/ocm/color.php',
      'high',
      'Candidate''s /ocm/marketingtoolkit/color.php 404s (the leftover purple/gold hexes visible in that 404 page''s raw HTML are just cached site-theme CSS, not body content). Found the current University Color Palette page at the corrected /ocm/color.php path instead: ''Primary Color Palette Tennessee Tech Purple Hex #753BBD... Tennessee Tech Gold Hex #FFD100.'' Substantial correction: candidate''s #4F2984 and #FFDD00 are both a visibly different, apparently outdated purple/gold pair -- neither matches the current stated primary hexes. Corrected: candidate''s white dropped -- Black/Gray/White are explicitly a separate ''Secondary Color Palette,'' with instructions to ''use these colors in conjunction with purple and gold,'' i.e. not primary on their own.'
    ),
    (
      'university-of-colorado-colorado-springs',
      '126580',
      array['#000000', '#CFB87C']::text[],
      'https://brand.uccs.edu/visual-guidelines/color',
      'high',
      'Candidate''s gomountainlions.com press-room article is a live but dead 2014 sports article with no brand-color body content (only a generic SIDEARM CMS theme config that happens to reuse #cfb87c as a UI accent). Found and read UCCS''s own current Brand Color page instead: ''The official UCCS colors are black and gold... CU Black HEX #000000... CU Gold HEX #cfb87c.'' Both match candidate''s black and gold exactly. Corrected: candidate''s white dropped -- Dark Gray/Light Gray/White are listed as separate additional swatches on the same page, but the page''s own summary statement names only ''black and gold'' as the official colors.'
    ),
    (
      'university-of-maine',
      '161253',
      array['#082E58', '#79BDE8']::text[],
      'https://umaine.edu/marketingandcommunications/brand/visual-identity/',
      'high',
      'Candidate''s umaine.edu/brand/graphics/colors/ URL 404s (site restructured under Marketing and Communications). Found and read the current Visual Identity page instead: ''Classic palette... Dark blue Pantone: 289... Hex: #082E58 Light Blue Pantone: 292... Hex: #79BDE8... white... Hex: #FFFFFF... Red... Hex: #AB0634... Black... Hex: #000000... Gray... Hex: #908C89... The blues should be the most prominent colors in your design.'' Substantial correction: candidate''s #003263 and #B0D7FF are both meaningfully different from the current stated dark/light blue hexes -- looks like a stale or pre-refresh candidate pull. Kept just the two blues, which the page itself calls out as the colors that ''should be the most prominent,'' rather than all six classic-palette swatches (white/red/black/gray also listed but not singled out as most-prominent).'
    ),
    (
      'southern-illinois-university-carbondale',
      '149222',
      array['#72253D', '#7C868D']::text[],
      'https://s3.amazonaws.com/sidearm.sites/mvc.sidearmsports.com/documents/2022/8/29/Style_Guide_Full_Version.pdf',
      'high',
      'Candidate''s citation is a multi-school Missouri Valley Conference style guide -- downloaded and text-extracted cleanly, and carefully matched to the correct school-specific section (checked for wrong-swatch risk given it''s a shared conference document): the page headed ''SOUTHERN ILLINOIS BRANDING'' with naming rules ''First reference: SIU, Salukis... Southern Illinois... Do NOT use: SIUC'' states ''PMS: 209C... HEX: #72253D'' and ''PMS: 430C... HEX: #7C868D,'' both confirmed exactly attributed to this school (not a neighboring conference member). Corrected: candidate''s white dropped -- only two colors are listed in the SIU-specific section, no white.'
    ),
    (
      'california-state-university-stanislaus',
      '110495',
      array['#C10230', '#FFD100', '#202322']::text[],
      'https://www.csustan.edu/brand/visual-identity-guidelines/color-palette',
      'high',
      'Candidate''s warriorathletics.com press-room URL is a live but dead 2013 article (title ''Sidearm Sports'' -- redirected to a generic ad-rotator shell, no color content). Found and read Stan State''s own current Color Palette page instead (updated Jan 20, 2026): ''Primary Colors... Warrior Red... WEB: #C10230... Warrior Gold... WEB: #FFD100... Dark Grey... WEB: #202322,'' explicitly three ''Primary Colors,'' with darker/accessible shade variants kept in a separate ''Shades or Accessible Versions'' tier. Substantial correction: none of the candidate''s three values (#E31B23, #FFFFFF, #BFB241) match the current official palette -- this looks like a stale, pre-rebrand candidate pull; even the school''s mascot-color nickname (''Warriors'') hasn''t changed but the hex values clearly have. Kept all three since the source explicitly labels exactly three colors ''Primary.'''
    ),
    (
      'university-of-california-merced',
      '445188',
      array['#002856', '#DAA900']::text[],
      'https://brand.ucmerced.edu/logos-elements/colors',
      'high',
      'Candidate''s citation 403s to direct fetch. A Jan-2025 Wayback capture of the same URL showed ''Bobcat Blue... HEX 0F2D52'' -- internally inconsistent with its own stated ''RGB 0 40 86'' (which converts to #002856, not #0F2D52). Rather than trust either value in isolation, checked whether the brand site had moved: UC Merced''s brand presence has since relocated to a Foleon-hosted portal (uc-merced.foleon.com/public-relations/ucmerced-brand/, live and current). A Nov-2025 Wayback capture of that portal''s own Colors page (embedded JSON/HTML, not an image) states ''Bobcat Blue... RGB 0 40 86 HEX 002856 PMS 295'' and ''Bobcat Gold... RGB 218 169 0 HEX DAA900 PMS 110'' -- consistent with its own RGB and matching candidate''s hexes exactly. Confirmed as-is via the newer, internally-consistent official source; flagged the older WordPress page''s stale/inconsistent hex as a caught discrepancy rather than used.'
    ),
    (
      'louisiana-tech-university',
      '159647',
      array['#003087', '#CB333B']::text[],
      'https://brand.latech.edu/identity-standards/university-colors/',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly: ''Primary color palette Tech Blue PMS 287 HEX #003087... Tech Red PMS 1797 HEX #CB333B... These are the primary University colors for Louisiana Tech University.'' Both candidate values confirmed exactly. No correction needed: white/black are explicitly part of a separate ''Neutral color palette'' on the same page, not primary, and the candidate never included them anyway.'
    ),
    (
      'northern-kentucky-university',
      '157447',
      array['#FFC72C', '#FFFFFF', '#000000']::text[],
      'https://www.nku.edu/marcomm/creative-services/brand/index.html',
      'high',
      'Candidate''s sidearmsports.com S3 athletics-style-guide PDF 404s. Found and read NKU''s own current Brand page instead: ''The main colors are gold, white and black. These three main colors become iconic to NKU. Gold: Hex: #FFC72C.'' White and black are explicitly two of exactly three named main colors (no separate hex given beyond the standard #FFFFFF/#000000). Corrected: candidate''s gold #FFC82E differs from the real, explicitly stated #FFC72C; white and black both kept since the source names exactly three main colors, not a mechanical append.'
    ),
    (
      'california-baptist-university',
      '110361',
      array['#002554', '#FFFFFF', '#A07400']::text[],
      'https://www.cbubrand.guide/colors',
      'high',
      'Candidate''s sidearmsports.com S3 athletics PDF 404s. Found and read CBU''s own official Brand Guide Colors page instead: ''Blue, white, and gold are the official primary colors of the CBU brand... Designs using CBU colors should be 60% blue, 30% white, and 10% gold... PANTONE 648 C... WEB HEX #002554... PANTONE 132... WEB HEX #A07400.'' All three candidate values confirmed exactly; white is explicitly one of only three named primary colors (30% of the palette), not a mechanical append. Confirmed as-is.'
    ),
    (
      'lamar-university',
      '226091',
      array['#DC0032', '#FFFFFF']::text[],
      'https://www.lamar.edu/_files/documents/marketing-communications/licensing-and-trademarks/athletics-brand-standards.pdf',
      'high',
      'Candidate''s exact cited PDF path (''faculty_staff/policies/Athletics Visual Standards Manual.pdf'') 404s; a same-named PDF found elsewhere on the domain downloads but is image-only with zero extractable text (confirmed via pdftotext). Found and text-extracted Lamar''s current Athletics Brand Identity Guidelines PDF instead: ''The official colors of Lamar University are Lamar Red and White... Lamar Red (Primary)... R 220 G 0 B 50... White (Primary)... R 255 G 255 B 255... Black (Secondary)... Lamar Gold (Secondary)... Lamar Green (Secondary).'' Red hex derived by exact, lossless RGB(220,0,50)->#DC0032 conversion of the officially stated RGB triplet (document gives no separate hex column). Corrected: candidate''s #E31937 does not match this real, explicitly-labeled Primary red; candidate''s black dropped -- the document explicitly marks it ''(Secondary)'', not one of the two Primary colors (Red and White).'
    ),
    (
      'colorado-mesa-university',
      '127556',
      array['#860037', '#FFFFFF']::text[],
      'https://www.coloradomesa.edu/marketing/documents/cmu-brand-guidelines.pdf',
      'high',
      'Candidate''s cmumavericks.com athletics PDF redirects to a generic HTML page (dead link). Found and text-extracted CMU''s current Brand Guidelines PDF instead (updated March 2026): ''PRIMARY COLORS... MAVROON... HEX: #860037... WHITE... HEX: #FFFFFF... Mavroon and white are the university''s main colors. Mavroon must be used in every piece of marketing and communications. In addition to Mavroon and white, Athletic Gold... and black are used as accent colors.'' Substantial correction: candidate''s maroon #5D0022 is meaningfully different from the real, explicitly-labeled ''Mavroon'' #860037. Corrected: candidate''s gold (#FED103, close to the document''s own accent-tier #FED102) dropped -- the source explicitly calls gold and black ''accent colors,'' not one of the two main colors (Mavroon and white).'
    ),
    (
      'ferris-state-university',
      '169910',
      array['#BA0C2F', '#FFD043']::text[],
      'https://www.ferris.edu/administration/advance/standards/color.htm',
      'high',
      'Candidate''s non-www ferris.edu URL 404s; the www-prefixed version of the identical path is live. Text-extracted directly: ''Ferris Crimson... HEX: #BA0C2F Ferris Gold... HEX: #FFD043... The official colors of Ferris State University are the specific shades of crimson and gold defined above.'' Both candidate chromatic values confirmed exactly. Corrected: candidate''s white dropped -- the source states the official colors are ''the specific shades of crimson and gold,'' with an explicit carve-out that white/black/neutral gray may only be used in photography/neutral space, not as a third official color.'
    ),
    (
      'youngstown-state-university',
      '206695',
      array['#C8333B', '#000000']::text[],
      'https://ysu.edu/sites/default/files/creative-services/YSU_2024_Brand_Identity_and_Style_Guide.pdf',
      'medium',
      'Candidate''s ysusports.com licensed-logos catalog PDF is a live but unrelated HTML page (dead link, no color content). Found and text-extracted YSU''s current 2024 Brand Identity & Style Guide instead: ''UNIVERSITY COLORS... PANTONE 186... 100% BLACK'' as the two official colors, with the Block Y logo''s own color-standards block giving ''Spot: Pantone 186... RGB: R=203, G=51, B=59... HEX CODE: C8333B.'' Flagging an internal inconsistency in the source itself: the stated RGB(203,51,59) mathematically converts to #CB333B, not the #C8333B literally printed as ''HEX CODE'' a few lines below it -- confirmed this is the document''s own literal text (not a pdftotext artifact) by re-extracting with both -layout and -raw modes, which agreed. Stored the school''s literal stated hex (#C8333B) rather than silently substituting my own RGB-derived value, and flagged the discrepancy here; confidence set to medium (not high) because of this unresolved internal inconsistency in the one official source found. Corrected: candidate''s #CE0E2D doesn''t match either reading; candidate''s white swapped for black -- the document''s ''UNIVERSITY COLORS'' are explicitly red + black, not red + white.'
    ),
    (
      'university-of-wyoming',
      '240727',
      array['#492F24', '#FFC425']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/wyoming.sidearmsports.com/documents/2024/5/2/Wyoming_Athletics_Brand_Guide.pdf',
      'high',
      'Candidate''s citation downloaded and text-extracted cleanly (live, not dead). ''PRIMARY COLORS... WYOMING BROWN... HEX: 492F24... WYOMING GOLD... HEX: FFC425... Brown and Gold have been the traditional colors of University of Wyoming Athletics since 1895.'' Both candidate chromatic values confirmed exactly. Corrected: candidate''s white dropped -- the ''PRIMARY COLORS'' section names only brown and gold; Apparel Brown/Apparel Gold and a tan/gold pair are separate secondary tiers further in the document.'
    ),
    (
      'wilmington-university',
      '131113',
      array['#008350', '#FFFFFF']::text[],
      'https://teamcolorcodes.com/wilmington-university-wildcats-color-codes/',
      'low',
      'Candidate''s wildcats.athletics.wilmu.edu/information/sid citation is a live sports-information-directory download page (rosters/logos-download links) with no brand-color content at all. Checked wilmu.edu''s sitemap for a dedicated /brand or /marketing/colors page (none found; a brandfetch.com mirror was blocked with a 403) -- Wilmington University (New Castle, DE, ''Wildcats,'' not to be confused with UNC Wilmington ''Seahawks'' or Wilmington College Ohio ''Quakers'') does not appear to publish a public university-wide brand-standards page. Fell back to a reputable secondary index per tier 4, confirmed by reading its actual swatch table: ''Green PANTONE: PMS 7731 C Hex: #008350... White Hex: #FFFFFF... Wilmington University Wildcats colors HEX codes are #008350 for green and #FFFFFF for white.'' Corrected: candidate''s green #00964E and gold #FEC532 don''t match anything found anywhere -- gold dropped entirely since no source (official or secondary) confirms a gold as part of the identity, only green and white. Low confidence: no official on-domain hex was reachable.'
    ),
    (
      'central-washington-university',
      '234827',
      array['#AB0032', '#000000', '#FFFFFF']::text[],
      'https://teamcolorcodes.com/central-washington-wildcats-color-codes/',
      'medium',
      'Candidate''s cwu.edu/public-affairs/... PDF 404s; the search-indexed ''university-colors.php'' URL sits under an explicit ''_unpublish'' path segment and 404s too, confirming it''s deliberately retired. CWU''s current brand hub (cwu.edu/brand/, cwu.edu/about/offices/marketing-communications/brand.php) links its full brand-guide files only via SharePoint-gated folders, no public hex text. One genuine on-domain signal: the live cwu.edu/crimson-black/ page''s own inline logo mark uses literal SVG ''.cls-1 { fill: #ab0032; }'', confirming the crimson value as a real, non-eyedropped on-domain CSS/SVG fill (matches candidate exactly). For the full three-color statement, fell back to a reputable secondary index per tier 4, confirmed by reading its table: ''The official colors of Central Washington University are CWU Crimson and Black and White... Hex Color: #AB0032... Black: Hex Color: #000000... White: #ffffff.'' Corrected: candidate''s third value #2C2A29 (a near-black, not confirmed anywhere) replaced with the explicitly stated pure black #000000. Medium confidence: crimson corroborated on-domain via SVG fill plus secondary-index agreement; black/white only via the secondary index.'
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
