-- Batch 11 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Most candidate citation URLs had rotted (dead sidearm/S3 PDFs -- several
-- fixed by finding the school's own current PDF path or athletics-domain
-- "documents/download/" endpoint rather than the plain "documents/" wrapper
-- page, one fixed via a full-length Wayback capture after an initial
-- capture turned out to be truncated at 1MB by the crawler), restructured
-- .edu paths, an obsolete .eps vector file, a JPEG-only citation with no
-- extractable text, image-only "colors" pages where the swatches only
-- exist in a PNG (read directly rather than OCR'd or eyedropped, since the
-- image itself prints the hex as text), and Issuu-hosted flipbooks that
-- serve only an app shell. Every school below was re-sourced against the
-- school's own current official domain where possible, verified by
-- downloading PDFs and running pdftotext -layout (never trusting a
-- fetch-tool summary of a PDF), or by reading the raw HTML text of an
-- official page directly.
--
-- Wrong-swatch / wrong-tier catches (candidate hex did not match the
-- school's own official source, or matched the wrong section of the right
-- page -- exactly the risk this batch is built to guard against):
-- california-state-university-monterey-bay (candidate's navy/gold matched
-- nothing on the actual official page; real Primary Colors are Monterey
-- Bay Blue #31456B and Ocean Blue #6B92B6), university-of-wisconsin-green-
-- bay (candidate matched nothing; real official colors are Phoenix Green
-- #0F5640 and white), santa-clara-university (candidate's #862633 is
-- "Bronco Red," an athletics-only supporting color -- the actual "main"
-- institutional pair is Santa Clara Red #A32035 + white), villanova-
-- university (candidate's blue and light-blue both wrong; the stated
-- Signature Blue is #002664, and the light blue candidate used is
-- restricted by the source to 10% of athletics print only), duke
-- (candidate's #013088 is a Sidearm CMS JSON theme value, not a documented
-- swatch; official Duke Blue is #012169), university-of-alabama-in-
-- huntsville (candidate matched neither stated primary; corrected to UAH
-- Blue #0058A4 + Black #2C2A29), tufts (brown corrected from #512C1D to
-- the actual Tufts Brown #63493A), texas-southern-university (maroon/gray
-- corrected to the PDF's own stated web hex, #75263B/#606060), southeast-
-- missouri-state-university (a conference-produced PDF's RGB-derived red
-- did not match SEMO's own domain, which states PMS 186 as #C8102E),
-- valdosta-state-university (red corrected from #CC0000 to the source
-- image's stated #DA1A32), hofstra-university (candidate's hex were
-- imprecise roundings of an older document; corrected to the current
-- CLC guide's stated RGB, deterministically converted), sacred-heart-
-- university (candidate's #CD1041 matched neither of the two official
-- color sections found; corrected to the Primary Palette's #A70034).
--
-- Primary-vs-secondary / tier corrections (candidate mechanically included
-- a white/black/gray that the real source marks as secondary, tacked on a
-- color from the wrong tier, or the true primary set has more than 2-3
-- members so the two-chromatic default was applied): loyola-marymount-
-- university, william-and-mary (4 labeled primaries, not the narrow 2-3
-- case -- kept the two chromatics), university-of-missouri-kansas-city,
-- slippery-rock-university-of-pennsylvania, wright-state-university-main-
-- campus, yale (white sits in its own separate "whitespace" tier, not a
-- primary/secondary listing of exactly 2-3), murray-state-university,
-- middle-georgia-state-university, elon-university, case-western-reserve-
-- university (only one color is labeled "Primary Color" -- the rest are
-- explicitly secondary/tertiary), university-of-rochester, southern-
-- connecticut-state-university, indiana-state-university (the source's own
-- "White" entry carries contradictory RGB/CMYK values -- dropped rather
-- than guess).
--
-- Confirmed as-is (candidate hex matched the verified official source
-- exactly, including the narrow case where white/black really is one of
-- only 2-3 labeled primary/official colors): university-of-wisconsin-
-- oshkosh (black, yellow, white are literally "the official colors"),
-- eastern-washington-university (official colors are literally "Red and
-- White").
--
-- Left null: jacksonville-state-university (official brand-guide page
-- exists but only links out to Issuu-hosted flipbooks that serve no
-- extractable content, just Issuu's own app-shell theme color -- no PDF
-- alternative found on jsu.edu or the athletics domain), saint-leo-
-- university (candidate PDF dead; the only located brand guide is a
-- content-less 3dissue.net flipbook shell; no /brand page or accessible
-- guide found on saintleo.edu or the athletics domain), william-paterson-
-- university-of-new-jersey (candidate citation is fight-song lyrics with
-- no stated hex; the only real brand guidelines PDF is gated behind a
-- Microsoft SAML institutional login).
--
-- Ran every final hex list through production deriveInks()/glyphInks()
-- (web/src/lib/derive-inks.ts) via a throwaway vitest scratch file
-- (deleted before finishing). No case lost a real chromatic primary to
-- the house-ink fallback -- every non-null school below produced its own
-- derived plates (house=false for all 27 populated rows). Several schools
-- with a stated but near-white/near-neutral second color (e.g. santa-
-- clara-university, eastern-washington-university, indiana-state-
-- university) fall into deriveInks' single-ink path because the algorithm
-- correctly treats the near-neutral second colour as non-chromatic and
-- brightens a tint of the one true chromatic instead -- expected behavior,
-- not a bug. See data/brand-colors/batch-11-2026-08-24.jsonl for the full
-- per-school record.

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
      'loyola-marymount-university',
      '117946',
      array['#AB0C2F','#0076A5']::text[],
      'https://brand.lmu.edu/identitystandards/colors/',
      'high',
      'Candidate URL resolved live and was read directly. Page states ''LMU Crimson and LMU Blue should be used more than any other colors in the palette. The secondary colors are meant to act as complements to the primary colors, LMU Crimson and LMU Blue.'' LMU Crimson HEX #AB0C2F, LMU Blue HEX #0076A5 -- matches candidate''s two chromatic hexes exactly. Corrected: dropped candidate''s white, which is not even listed on the page at all (the page''s own secondary/neutral set is LMU Light Gray #C8C9C7, LMU Dark Gray #888B8D, LMU Black #000000 -- no white swatch exists on this page).'
    ),
    (
      'sacred-heart-university',
      '130253',
      array['#A70034','#8A8D8F']::text[],
      'https://www.sacredheart.edu/media/shu-media/marketing-amp-communications/SHU_Brand_Guide_ADA.pdf',
      'high',
      'Candidate''s static.psbin.com .eps file is an obsolete vector format that could not be text-extracted and is unrelated to SHU''s current identity system. Found and pdftotext''d SHU''s current (ADA-accessible) Brand Style Guide PDF. Document has two distinct sections: page 18 ''Official Colors'' for the wordmark/logo lockup only (Gold #D2A67C, Red #CE1141, Gray #AFB3B6, Dark Gray #4B4D4F), and page 23 ''Primary Palette'' -- ''A primary palette has been identified for use in all applications'' -- listing Red (PMS 187) HEX A70034, Gray HEX 8A8D8F, Black HEX 000000. Wrong-swatch/wrong-tier catch: candidate''s #CD1041 matches neither red value exactly and appears to be a third, unsourced red. Chose the institution-wide Primary Palette (used in all applications) over the logo-specific Official Colors: Red #A70034 + Gray #8A8D8F, dropping Black to keep to the two chromatic/near-chromatic leads per prefer-1-2-chromatic guidance.'
    ),
    (
      'tufts',
      '168148',
      array['#3E8EDE','#63493A']::text[],
      'https://brand.tufts.edu/guidelines/color',
      'high',
      'Candidate''s communications.tufts.edu PDF 404s. Found and read the current Tufts Brand Guidelines color page: ''Primary Colors: Our primary colors are Tufts Blue and Tufts Brown... If you can only use one of these colors, use Tufts Blue.'' Tufts Blue HEX #3E8EDE (matches candidate exactly), Tufts Brown HEX #63493A. Wrong-swatch catch: candidate''s brown (#512C1D) does not match the official Tufts Brown at all. Corrected the brown and dropped candidate''s white, which is not part of the two-color primary pair (a separate ''Tufts Accessible Blue'' #002E6D exists for text-contrast use only, also not primary).'
    ),
    (
      'william-and-mary',
      '231624',
      array['#004E38','#B79257']::text[],
      'https://www.wm.edu/brand/visual-brand/color-palette/',
      'high',
      'Candidate''s brand.wm.edu URL redirects live to the current color-palette page, read directly. ''Primary Color Palette... The primary colors consist of W&M Green, W&M Gold, W&M Silver and White.'' W&M Green HEX #004E38, W&M Gold HEX #B79257 (both match candidate), W&M Silver HEX #D8DCDB, White HEX #FFFFFF. This is 4 labeled primaries, not the narrow 2-3 case the no-neutral-append exception covers, so dropped both candidate''s white and the unlisted Silver to keep to the two chromatic leads per prefer-1-2-chromatic guidance, rather than picking arbitrarily between the two neutrals for a third slot.'
    ),
    (
      'jacksonville-state-university',
      '101480',
      null::text[],
      null,
      null,
      'Candidate''s jsu.edu/marketingservices/styleguide/style_guide.pdf 404s (redirects to a designlicensing path that also 404s). Found JSU''s current ''Jax State Brand Guidelines'' landing page (jsu.edu/designlicensing/brandguide/index.html), which links out to two Issuu-hosted flipbooks (''Jax State Brand Guidelines'' and ''Athletic Brand Standards'') via isu.pub short links. Both Issuu documents serve only their app shell to a direct fetch -- no page content, only Issuu''s own UI theme colors (e.g. #ff5a47), which per this batch''s own precedent (and batch 10''s identical finding for Belmont) must not be treated as a documented JSU swatch. Checked jaxstatesports.com (athletics) for an alternate PDF brand guide; none found in top-level nav or Wayback CDX for jsu.edu brand-guide PDFs. Left null rather than read an Issuu app-shell color or an unverified third-party aggregator hex as JSU''s official red.'
    ),
    (
      'villanova-university',
      '216597',
      array['#002664','#FFFFFF']::text[],
      'https://www.villanova.edu/university/comm-marketing/guidelines/villanova-visual-identity/university-colors.html',
      'high',
      'Candidate''s villanova.com athletics standards-guide.pdf is dead (serves the live site''s HTML shell, not a PDF). Found and read Villanova''s official University Colors page instead: ''The University colors are blue and white, with Pantone 281 as our signature blue color... Villanova Signature Blue Pantone 281 ... HTML HEX #: 002664.'' Wrong-swatch catch: candidate''s #00205B and #13B5EA do not match; #13B5EA looks like it was sourced from ''Athletic Light Blue (Pantone 298)'', which the page explicitly restricts to at most 10% of any athletics print design, not a core University color. Corrected to the stated Signature Blue #002664 + White (the two colors literally named ''blue and white'').'
    ),
    (
      'university-of-wisconsin-oshkosh',
      '240365',
      array['#000000','#FFFFFF','#FFCC00']::text[],
      'https://www.uwosh.edu/umc/toolkit/brand/',
      'high',
      'Candidate''s uwosh.edu/umc/brand/brand-colors/ 404s (site reorganized). Found the current brand toolkit page and read it live: ''The official colors of UW-Oshkosh are black, yellow and white.'' Titan Yellow HEX #FFCC00, Black HEX #000000, White HEX #FFFFFF -- confirmed as-is. This is the narrow case where all three (including white and black) are explicitly the named official colors, matching the candidate exactly.'
    ),
    (
      'texas-southern-university',
      '229063',
      array['#75263B','#606060']::text[],
      'https://tsu.edu/about/administration/marketing-and-communications/documents/tsu-brand-standard-guidelines_0322.pdf',
      'high',
      'Candidate''s www.tsu.edu/.../pdf/tsu-graphic-standards.pdf 404s (TSU''s 404 page). Found and pdftotext''d the current TSU Brand Standard Guidelines PDF instead. ''COLOR PALETTE'' table: PMS 209 (maroon) WEB #75263b, PMS 249 (gray) WEB #606060, Black #000000, White #ffffff -- four colors with no stated primary/secondary split beyond print ratios (60/50/40/30%). Wrong-swatch catch: candidate''s maroon (#6F263D) and gray (#A2AAAD) match neither stated value. Corrected to the two chromatic/near-chromatic leads (maroon PMS 209 + gray PMS 249) that the school''s own ''maroon and gray'' Tigers identity is built on, dropping the separately-listed black/white per prefer-1-2-chromatic.'
    ),
    (
      'california-state-university-monterey-bay',
      '409698',
      array['#31456B','#6B92B6']::text[],
      'https://csumb.edu/communications/brand-guidelines/color-palette-and-typography/',
      'high',
      'Candidate''s csumb.edu/affairs/official-colors 404s (site reorganized). Found the current Brand Guidelines > Color Palette page and read it live: ''Primary Colors -- These core colors should comprise about 85% of CSUMB-branded content.'' Monterey Bay Blue HEX #31456b, Ocean Blue HEX #6b92b6 -- explicitly the two Primary Colors. Secondary: Valley Green #689466 (10%). Tertiary (5% together): Valley Green Bright, Sunshine, Tangerine. Major wrong-swatch catch: none of candidate''s hexes (#002A4E navy, #FFFFFF, #9E8B50 gold) appear anywhere on the actual official page -- corrected entirely to the stated Primary Colors pair.'
    ),
    (
      'university-of-missouri-kansas-city',
      '178402',
      array['#FFC72C','#004B87']::text[],
      'https://www.umkc.edu/mcom/documents/KC-Roos-Identity-Guide.pdf',
      'high',
      'Candidate''s live URL 404s; the same file is intact in Wayback (2019-09-05 capture, full 7.8MB, not the later truncated 1MB capture). pdftotext''d the Wayback copy directly: ''COLOR PALETTE ... PMS 123c #FFC72C ... PMS 301c #004B87 ... Kansas City''s yellow (PMS 123c) should stand as the dominant color representing the Roos athletics program... The navy (PMS 301c) can and should be used as a secondary color.'' Matches candidate''s navy and yellow exactly (order swapped to put the stated-dominant yellow first). A third color, light blue PMS 660c #407EC9, is explicitly ''NEVER to be used outside of the primary mark'' -- excluded. Dropped candidate''s white, which is not in this document.'
    ),
    (
      'slippery-rock-university-of-pennsylvania',
      '216038',
      array['#007055','#231F20']::text[],
      'https://www.sru.edu/documents/offices/public-affairs/SRU-Brand-Guidelines.pdf',
      'high',
      'Candidate''s licensing/trademarks landing page itself states no hex (only CSS theme colors, not documented swatches); it links to SRU''s Brand Guidelines PDF, which was downloaded and pdftotext''d. ''The University''s primary colors are green (PMS 342), black, gray (PMS 429) and white.'' Table: PMS 342 HEX #007055 (candidate''s green was close but off, #006951 vs actual #007055 -- corrected), White RGB 255/255/255, PMS 429 Gray HEX #A2AAAD, Black CMYK 0/0/0/100 but stated RGB 35/31/32 (a rich-black conversion, not pure #000000) -- computed deterministically to #231F20. Four colors are named primary; per prefer-1-2-chromatic, kept Green + Black (the pairing SRU''s own wordmark options -- Green, Black, White EPS/AI variants -- treat as the two solid-ink choices), dropping white and gray.'
    ),
    (
      'wright-state-university-main-campus',
      '206604',
      array['#046A38','#CBA052']::text[],
      'https://wsuraiders.com/documents/download/2022/8/23/WrightStateAthletics-Brandbook_Aug2022.pdf',
      'high',
      'Candidate''s sidearm.sites S3 URL is a genuine NoSuchKey (deleted from bucket, confirmed at both us-east-1 and us-east-2 endpoints). Found the current Brandbook on wsuraiders.com (the athletics domain''s own /documents/download/ path serves the real PDF; the /documents/ path without ''download'' serves an HTML wrapper page) and pdftotext''d it directly. ''The Wright State Athletics color palette is comprised of two primary colors (green and gold) and five accent colors (black, two secondary golds, dark green, and white)... Primary Colors: PMS 349C HEX 046A38, PMS 7407C HEX CBA052.'' Matches candidate''s green and gold exactly. Dropped candidate''s white, which the document explicitly lists as one of the five accent colors, not primary.'
    ),
    (
      'yale',
      '130794',
      array['#0A2240']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/yalebulldogs.com/documents/2021/12/1/Vision_of_Yale_Athletics_DEC_17_2019.pdf',
      'high',
      'Candidate URL resolved directly and was pdftotext''d. Document structures color as four distinct tiers, not a single primary set: ''PRIMARY COLOR: ATHLETICS MIDNIGHT BLUE'' HEX 0A2240 (matches candidate''s blue exactly), ''SECONDARY COLOR: OFFICIAL YALE BLUE'' HEX 00346A (uncoated-paper value), ''TERTIARY COLOR: ATHLETICS GRAY'' HEX B1B1B1, and a separate ''WHITE SPACE: OFFICIAL YALE CHINA WHITE'' tier (#FFFFFF) that is about generous negative space, not a fourth ranked color alongside primary/secondary/tertiary. Since only one color is labeled PRIMARY and white sits in its own distinct ''whitespace'' tier rather than a primary/secondary listing of exactly 2-3, this doesn''t qualify for the narrow white-inclusion exception -- dropped candidate''s white and kept the single stated PRIMARY chromatic.'
    ),
    (
      'saint-leo-university',
      '137032',
      null::text[],
      null,
      null,
      'Candidate''s saintleo.edu/uploads/StyleGuides/.../2015_combined-Athletics Identity Guide.pdf 404s. Found a linked digital brand guide flipbook (cloud.3dissue.net/28470/28417/28664/71783/index.html); it serves only its viewer app shell (~46 lines, no document content or PDF link extractable). Checked saintleo.edu for /brand, /marketing-brand, /about-us/university-brand -- all 404. Checked the ''Creative Requests'' marketing-request page (a Wrike-embedded request form, no static content) and the athletics domain saintleolions.com (no brand/style guide link in nav). A community.saintleo.edu 2023 post references ''new brand resources'' but does not itself state colors, and the resources it points to are internal-only. Left null rather than trust an unverified third-party aggregator''s green/gold hex claim that could not be traced to an actual Saint Leo-controlled page or document.'
    ),
    (
      'murray-state-university',
      '157401',
      array['#002144','#ECAC00']::text[],
      'https://www.murraystate.edu/about/administration/advancement/branding-mkt-comm/toolkit/media/msu_guidelines_2022.pdf',
      'high',
      'Candidate URL resolved and was pdftotext''d directly. ''PRIMARY: There are two primary colors, the tried and true Murray State blue and gold.'' Murray State Blue HEX 002144, Murray State Gold HEX ECAC00 -- matches candidate exactly. Usage guidance explicitly states ''Do not use any other colors,'' reinforcing the two-color-only palette. Dropped candidate''s white, which is not part of the stated primary pair (and would conflict with the document''s own ''do not use any other colors'' instruction).'
    ),
    (
      'valdosta-state-university',
      '141264',
      array['#DA1A32','#000000']::text[],
      'https://brand.valdosta.edu/color/',
      'high',
      'Candidate''s valdosta.edu/administration/creative-services/section-3.pdf 404s. Found VSU''s current Brand Guidelines color page; its body text has no extractable hex (swatch values live only in an image, primary.png), so per constraint on not eyedropping I read the actual swatch image directly rather than OCR/guess: it prints, as literal on-image text, ''Black Swarm'' RGB 0,0,0 WEB #000000, ''Bonfire Red'' PMS 186C RGB 218,26,50 WEB #da1a32, ''Magnolia White'' WEB #FFFFFF, and ''Embers'' PMS 7427C WEB #a00c30 -- four Primary Palette swatches. Page prose singles out exactly two as dominant: ''Black Swarm and Bonfire Red should be dominant throughout any given piece.'' Wrong-swatch catch: candidate''s red (#CC0000) does not match the stated Bonfire Red (#DA1A32). Corrected to the two colors the source text itself calls dominant, dropping candidate''s white (Magnolia White is a primary swatch but not one of the two named-dominant colors) and Embers (a secondary dark-red variant).'
    ),
    (
      'william-paterson-university-of-new-jersey',
      '187444',
      null::text[],
      null,
      null,
      'Candidate''s /about-us/spirit-song page is fight-song lyrics (''Orange and black the colors ever held dear'') with zero stated hex -- the only hexes present in the page''s HTML are unrelated CSS theme colors (footer hover states, sidebar labels), not documented brand swatches, and checking a second page (mpr/wp-stationery) turned up the identical CSS-only pattern. wpunj.edu/marcom/brand/colors.html, /marcom/brand-guidelines, /brand, and /marcom/ all 404. The only located brand guidelines PDF (wpunj.edu/mpr/assets-internal/WPUNJ_brand_guidelines.pdf) is gated behind a Microsoft SAML institutional login, and wpupioneers.com athletics has no linked brand/style guide. Left null rather than treat unrelated site-chrome CSS hex values (#FF6720, #808080) as WPU''s stated brand colors.'
    ),
    (
      'university-of-alabama-in-huntsville',
      '100706',
      array['#0058A4','#2C2A29']::text[],
      'https://www.uah.edu/omc/resources/brand',
      'high',
      'Candidate''s uah.edu/omc/brand redirects live to the current /omc/resources/brand page, read directly. ''Color Palette -- Web/Screen Primary Colors: UAH BLUE HEX #0058A4, BLACK HEX #2C2A29.'' Secondary colors (also listed): #7BA4DB, #002D72, #FDDA24, #757575, #BBB1A7, #E5E5E5. Wrong-swatch catch: none of candidate''s hexes (#003DA5, #FFFFFF, #29282A) match the stated Web/Screen Primary values exactly -- corrected to the page''s own stated primary pair, dropping white (not in the primary list; white/reversed logo use is a usage note, not a swatch).'
    ),
    (
      'middle-georgia-state-university',
      '482158',
      array['#633393','#000000']::text[],
      'https://www.mga.edu/marketing-communications/docs/MGA_Brand_Guidelines-2024.pdf',
      'high',
      'Candidate''s MGA_Brand_Guidelines.pdf (no year) 404s; found and pdftotext''d the current 2024-dated edition at a sibling path. ''COLOR INFORMATION'' table lists five colors with no primary/secondary hierarchy label: PANTONE 267c Html 633393 (purple, matches candidate exactly), PANTONE 2685c Html 42337E (darker purple), PANTONE 429c Html B0B6BB (light gray), PANTONE 428c Html C9CED1 (lighter gray), Black Html 000000. No white is listed anywhere in the document. Kept the flagship purple + black as the two-color identity per prefer-1-2-chromatic, dropping the second purple/grays and candidate''s white (not present in the source at all).'
    ),
    (
      'santa-clara-university',
      '122931',
      array['#A32035','#FFFFFF']::text[],
      'https://www.scu.edu/umc/brand/colors/',
      'high',
      'Candidate''s cited path (umc/brand-visual-style/visual-identity-elements/scu-color-palette/) now 404s to SCU''s generic Error Page. Found the current colors page and read it live: ''Within this Primary Palette, Santa Clara Red and White are our main colors. Bronco Red (used most significantly by Athletics), Stone, and Black are used as supporting colors.'' Santa Clara Red HEX #A32035, White #FFFFFF (the two ''main colors''); Bronco Red HEX #862633 is a separate, explicitly-supporting athletics variant. Wrong-tier catch: candidate''s hex (#862633) is Bronco Red, the supporting athletics color, not the institution''s actual main Santa Clara Red (#A32035). Corrected to the two colors the page calls ''main.'''
    ),
    (
      'hofstra-university',
      '191649',
      array['#003594','#FFC72C','#2C2A29']::text[],
      'https://www.hofstra.edu/pdf/home/news/ur/licensing/licensing-standards-guide.pdf',
      'high',
      'Candidate URL resolved and was pdftotext''d directly -- but the live document (CLC licensing guide, current revision 05/01/25) is a different, newer edition than whatever the candidate hex was sourced from. Page 1 states colors only as PANTONE/CMYK/RGB, no hex printed: ''Hofstra Blue'' PANTONE 661C RGB 0/53/148, ''Hofstra Gold'' PANTONE 123C RGB 255/199/44, ''Black'' PANTONE Process Black RGB 44/42/41 -- presented together as the top institutional trio, distinct from a separate ''Midnight Blue / Sky Blue / Orange / Sun Yellow / Stone Gray'' palette used only for School of Medicine/Nursing sub-marks. Converted the stated RGB deterministically (not eyedropped): #003594, #FFC72C, #2C2A29. Wrong-swatch catch: candidate''s blue (#003591) and gold (#FDC82F) are close-but-imprecise roundings, not the document''s exact values; candidate''s white is not in this trio at all -- corrected white to the document''s actual third color, Black.'
    ),
    (
      'elon-university',
      '198516',
      array['#73000A','#B59A57']::text[],
      'https://www.elon.edu/u/university-communications/brand/guide/visual-identity/color-type/',
      'high',
      'Candidate''s elonphoenix.com athletics page 404s. Found and read the official Elon Brand Guide''s Color & Type page: ''Primary Colors -- Both of these colors should be present in all Elon University branded materials... Maroon should always be the most dominant color of the two.'' Maroon Pantone 188 HEX #73000a, Gold Pantone 872/7503 HEX #b59a57 -- matches candidate''s chromatic pair exactly. Dropped candidate''s white, which is not part of the two-color primary pair (a separate secondary palette exists for supplementary use, e.g. Orange #b7410e).'
    ),
    (
      'duke',
      '198419',
      array['#012169','#FFFFFF']::text[],
      'https://brand.duke.edu/colors/',
      'high',
      'Candidate''s goduke.com quick-facts page resolved live, but its text states only ''Colors: Duke Blue (PMS 287) & White'' with no hex, and the only hex present in the page''s payload (#013088) is a Sidearm CMS ''siteColorPrimaryBackground'' JSON theme value inside a Next.js data blob -- exactly the kind of unreliable CMS theme color this batch is built to catch, not a documented brand swatch. Found and read Duke''s official brand.duke.edu/colors/ page instead: ''Official Duke Blue -- The official Duke blue is a shade of navy blue... called \''Duke Navy Blue\''... the Hex color for web design is #012169. \''Duke Royal Blue\'' is the other shade of blue... has been in use since 2009 for athletics... Hex color... #00539B. Both shades of blue represent the Duke brand and at least one of them should be used somewhere in any project.'' Chose the institution-wide ''Official Duke Blue'' (#012169) + White for a general (non-athletics-specific) school glyph, over the athletics-specific Royal Blue (#00539B) that the original PMS-287 citation actually pointed to.'
    ),
    (
      'case-western-reserve-university',
      '201645',
      array['#003071']::text[],
      'https://case.edu/brand/visual-identity/color',
      'high',
      'Candidate''s case.webdamdb.com link is a gated DAM viewer (JS app shell only, no extractable content). Found and read Case Western''s public brand guidelines color page instead: ''"CWRU Blue" is the primary color of the university''s identity. Secondary blues and grays are supporting colors... Primary Color: CWRU Blue... HEX: 003071.'' Only one color is labeled Primary; CWRU Dark Blue, Force Blue, CWRU True Blue and various grays are all explicitly Secondary/Tertiary. Wrong-tier catch: candidate''s gray (#626262) and white are secondary-tier, not primary -- corrected to the single stated Primary Color.'
    ),
    (
      'southeast-missouri-state-university',
      '179557',
      array['#C8102E','#212121']::text[],
      'https://semo.edu/marketing-communications/brand/brand-guidelines',
      'high',
      'Candidate''s ovcsports.com OVC_Style_Guide.pdf is a conference-produced (not SEMO-authored) reference document; it lists SEMO''s red as RGB(206,17,38) = #CE1126, matching the candidate but not SEMO''s own domain. Found and read SEMO''s own official Brand Guidelines page instead: ''Primary Palette -- SEMO Red PMS: 186 Hex: #C8102E ... Charcoal PMS: Black 4 Hex: #212121 ... Copper ... Dark Copper ... Vibrant Red.'' Wrong-swatch/wrong-source catch: SEMO''s own stated Pantone 186 value (#C8102E) differs from the conference document''s RGB-derived #CE1126 -- the school''s own domain wins per source priority. Primary Palette has 5 members; kept the flagship SEMO Red + Charcoal (dark neutral) per prefer-1-2-chromatic, dropping Copper/Dark Copper/Vibrant Red variants.'
    ),
    (
      'university-of-wisconsin-green-bay',
      '240277',
      array['#0F5640','#FFFFFF']::text[],
      'https://www.uwgb.edu/licensing/visual-identity/uwgb-style-guide/',
      'high',
      'Candidate''s citation is a JPEG image (GB_Athletics_LogoSheet2.jpg) with no extractable text -- treated as a dead source per the brief''s own flag. Found UW-Green Bay''s official style guide page and read it live: ''Official Colors -- The official school colors of the University of Wisconsin-Green Bay are Phoenix Green and white.'' Phoenix Green PMS 343 HEX #0F5640, White HEX #FFFFFF. Major wrong-swatch catch: none of candidate''s hexes (#006A4D, #FFFFFF, #183029) match the actual official Phoenix Green -- corrected to the two colors literally named ''the official school colors.'' Secondary colors (Bright Green #1BA72E, Black, 60% Black, etc.) excluded.'
    ),
    (
      'university-of-rochester',
      '195030',
      array['#001E5F','#FFD82B']::text[],
      'https://brand.rochester.edu/visual-identity/color-system/',
      'high',
      'Candidate URL resolved live and was read directly. ''Primary Colors -- Our primary colors are URochester navy blue and dandelion yellow... officially adopted by the Board of Trustees in 1954.'' URochester Navy HEX #001E5F, Dandelion Yellow HEX #FFD82B -- matches candidate''s two chromatic hexes exactly. Dropped candidate''s white, which is not part of the stated two-color primary pair (secondary blues/yellows exist for accent use, e.g. Meliora Blue #021BC3).'
    ),
    (
      'southern-connecticut-state-university',
      '130493',
      array['#001489','#97999B']::text[],
      'https://scsuowls.com/sports/2019/7/10/scsu-athletics-logo-library.aspx',
      'high',
      'Candidate''s sidearm.sites S3 URL is a genuine NoSuchKey at both us-east-1 and us-east-2 endpoints (bucket rejects the key entirely). Found the athletics domain''s own current Logo Library page and read it live: ''The Pantone Colors for Southern Connecticut State University Athletics'' logo marks are Blue 2766 C, Blue 2726 C, Reflex Blue C and Cool Grey 7 C.'' Web Hex Colors table: #141B4D, #485CC7, #001489 (Reflex Blue), #97999B (Cool Grey 7C). Matches candidate''s Reflex Blue and Cool Grey exactly. Dropped candidate''s white, which is not in the stated four-color list.'
    ),
    (
      'eastern-washington-university',
      '235097',
      array['#B7142E','#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/ewu.sidearmsports.com/documents/2023/10/2/EWU_Athletics_Brand_Style_Guide.pdf',
      'high',
      'Candidate''s cdn.ewu.edu logo-usage-guide PDF 404s. Found and pdftotext''d EWU Athletics'' current Brand Style Guide instead: ''COLOR INFORMATION -- The official colors of Eastern Washington University are Red and White.'' Table gives two hex values for red depending on conversion path (CMYK-derived #C8102E vs. the RGB row''s #B7142E, RGB 183/20/46); used the RGB-derived value, which matches the candidate exactly. Black (#000000) is in the same swatch table but the prose explicitly says the official colors are only ''Red and White'' -- dropped candidate''s black to match the stated two-color pair (white qualifies for the narrow exception here).'
    ),
    (
      'indiana-state-university',
      '151324',
      array['#224E92','#CECFCE']::text[],
      'https://gosycamores.com/sports/2021/5/10/athletic-communications.aspx',
      'high',
      'Candidate URL resolved live and was read directly. Quick Facts text: ''Colors: Royal Blue - (RGB 34, 78, 146) White - (RGB 0, 0, 0) Cool Gray - (RGB 206, 207, 206)'' -- the source itself has an internal data-entry error (the entry labeled ''White'' carries RGB 0,0,0, which is black, while its own CMYK on the same line reads 0,0,0,0, which is white -- contradictory and untrustworthy as printed). Royal Blue RGB(34,78,146) converts deterministically to #224E92 (matches candidate exactly); Cool Gray RGB(206,207,206) converts to #CECFCE (also matches candidate''s third hex exactly). Dropped the ambiguous ''White'' entry rather than resolve its internal RGB/CMYK contradiction by guessing, keeping the two colors whose stated RGB is internally consistent.'
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
