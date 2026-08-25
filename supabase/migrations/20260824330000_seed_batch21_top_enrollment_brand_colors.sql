-- Batch 21 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a dropped
-- mechanically-attached white/neutral: hamilton (Continental Blue/Buff
-- exact hex match on the official graphic-identity page), western-new-
-- mexico-university (Royal Purple/Golden Yellow exact hex match, recovered
-- via Wayback, "the two primary WNMU colors"), moravian-university
-- (Blue/Grey exact hex match, "the primary colors of the University's
-- identity" -- kept the grey, dropped candidate's mechanical white),
-- black-hills-state-university (Green/Gold exact hex match, recovered via
-- Wayback, "the official colors are"), st-lawrence-university
-- (Scarlet/Brown exact hex match, recovered via Wayback, explicit PRIMARY
-- COLORS heading), depauw-university (Gold/Black exact hex match,
-- recovered via Wayback, "DePauw Colors" distinct from "Website Accent
-- Colors"), oklahoma-christian-university (Maroon exact hex match on the
-- live "Official Logos and Colors" athletics page; kept Tan as the second
-- chromatic value from the same official 5-color list, dropped Silver/
-- Black/White), gustavus-adolphus-college (Gold exact hex match on the
-- live PDF's "GUSTAVUS GOLD -- the main College color"; no black/white
-- named anywhere, single ink), occidental-college (Orange/Black exact hex
-- match, recovered via Wayback, explicit "Core Colors" section), gardner-
-- webb-university (Red/Black/White exact 3-of-4 match on the live
-- "primary color palette" of red/black/white/gray), rhodes-college
-- (Red/Black exact hex match on the live PDF's "PRIMARY PALETTE").
--
-- Corrected (candidate hex or source did not match the school's own
-- current official source): fairleigh-dickinson-university-florham-campus
-- (hexes corrected to the live page's literal "corresponding HEX Codes"),
-- wilkes-university (both hexes off by one digit, corrected via Wayback
-- to the "PRIMARY COLOR PALETTE"), la-salle-university (hexes corrected
-- via Wayback to "PMS 540 Blue and PMS 7406 Gold"), saint-marys-college-
-- of-california (confirmed exact via Wayback; white/black were a separate
-- reproduction row, not named Primary colors, so dropped), nazareth-
-- university (both hexes substantially corrected to the live page's
-- literal Purple/Gold values), pennsylvania-state-university-penn-state-
-- berks (added the second "primary brand blue," Beaver Blue, and dropped
-- White out -- the page explicitly frames Navy+Beaver Blue, not Navy+
-- White, as the pair "central to the Penn State brand"), whitworth-
-- university (Red/Black confirmed, white dropped -- not part of the
-- document's "Primary Brand Colors"), washington-and-lee (both candidate
-- hexes were wrong -- corrected via Wayback to W&L Blue #003087 and the
-- second official color, a named grey (Liberty Hall Grey #707372), not
-- white).
--
-- Wrong-swatch / wrong-tier / off-domain-Pantone corrections, no literal
-- hex found on the school's own domain for an on-domain-CSS medium-
-- confidence substitute: university-of-mount-union (candidate's PDF is
-- dead with no full Wayback capture; the current Identity Standards PDF
-- gives only PMS/CMYK for purple, no hex; corrected to mountunion.edu's
-- own dominant site-wide CSS purple #752F8A; gold dropped -- no on-domain
-- hex found for PMS 871), northwood-university (the cited 2011 PDF's RGB-
-- derived hexes matched the candidate exactly but are superseded by a
-- clearly different, dominant, current on-domain palette defined in the
-- school's own "northwood-blocks" WordPress plugin CSS -- treated as a
-- likely rebrand and corrected to the live #0076BB/#F79713), augustana-
-- university (cited athletics quick-facts page only names "Navy Blue &
-- Gold (PMS 282, 109)" in prose; corrected via the same domain's Sidearm
-- site-color config to #002147/#FED100, which does not match the
-- candidate's approximated hexes), st-marys-university (candidate's cited
-- PDF is permanently gone -- every Wayback capture is an HTML error page,
-- not a PDF; corrected via the linked rattlerathletics.com domain's
-- Sidearm site-color config), vanguard-university-of-southern-california
-- (hex corrected one digit via the cited page's own Sidearm site-color
-- config), southern-university-at-shreveport (WRONG-SCHOOL FLAG:
-- candidate's citation is Southern University and A&M College at Baton
-- Rouge's system-wide style guide, a different sister institution, and
-- gives only Pantone numbers with no hex anywhere; corrected via SUSLA's
-- own susla.edu domain CSS, which is bespoke, not a generic template),
-- davidson-college (candidate's cited PDF states only "Red (PMS 186) and
-- Black" with no hex; the domain's CSS contains a decoy -- #003057/
-- #E87722 are the Sidearm Sports vendor's own footer-logo colors, not
-- Davidson's -- correctly avoided; corrected via the site's actual
-- serialized page-config data, siteColorPrimaryBackground #CF102D /
-- siteColorSecondaryBackground #373534), coppin-state-university
-- (candidate's cited PDF, recovered via a full untruncated Wayback
-- capture, states only "Reflex Blue and Gold PMS 871" with no hex;
-- confirmed via coppin.edu's own Bootstrap theme CSS custom properties
-- --primary:#FFC915 / --secondary:#003056, which do match the candidate's
-- exact hexes).
--
-- Left null (no usable on-domain hex/RGB found after a documented search;
-- see data/brand-colors/batch-21-2026-08-24.jsonl for full detail):
-- bowdoin (candidate's cited page is dead with no usable Wayback capture;
-- the parent directory 403s; no live bowdoin.edu page found stating
-- official colors with hex/RGB, despite widely-repeated secondary claims
-- of a black/white identity -- left null rather than assert an unverified
-- pairing; flagged for human review).
--
-- Every populated row was run through the production deriveInks()/
-- glyphInks() (web/src/lib/derive-inks.ts) via a throwaway tsx script
-- before finishing (deleted, not committed). All 29 populated rows produce
-- their own derived plates (house=false). Four rows lose a real chromatic
-- primary to a synthesized fallback because deriveInks judges the second
-- ink too close in hue/lightness to the first (documented per-row in the
-- JSONL notes): st-lawrence-university (Scarlet -> synthetic bright red),
-- washington-and-lee (Liberty Hall Grey rejected as neutral -> synthetic
-- bright blue), pennsylvania-state-university-penn-state-berks (Beaver
-- Blue -> synthetic bright blue), davidson-college (near-black secondary
-- rejected as neutral -> synthetic bright red). This is expected deriver
-- behavior, not a data error.
-- See data/brand-colors/batch-21-2026-08-24.jsonl for the full per-school
-- record, including the one null entry.

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
      'hamilton',
      '191515',
      array['#002F86','#D6BA8B']::text[],
      'https://www.hamilton.edu/styleguides/graphicidentity/college-colors',
      'high',
      'Live page states "Continental Blue & Buff" with literal hex: Blue RGB 0/47/134 Hexadecimal #002f86; Buff RGB 214/186/139 Hexadecimal #d6ba8b (both match candidate exactly). Candidate''s mechanically-attached white dropped -- the page names exactly two colors, no white anywhere in the swatch text.'
    ),
    (
      'western-new-mexico-university',
      '188304',
      array['#42196F','#FEBE10']::text[],
      'http://web.archive.org/web/20160603233813/http://www.wnmu.edu/IdentityStandards/files/WNMU_IDStandards.pdf',
      'high',
      'Candidate''s live wnmu.edu PDF link is dead (404) and the closest Wayback capture was truncated to 1MB by the archive''s size cap; recovered a full, untruncated 2016 capture of the same identity-standards PDF (same digest as the 2012-2016 captures, so stable/unchanged). "The two primary WNMU colors are Royal Purple and Golden Yellow." HEX: #FEBE10 (Golden Yellow), HEX: #42196F (Royal Purple) -- both match candidate exactly. Candidate''s mechanically-attached white dropped -- not part of the two-color primary statement.'
    ),
    (
      'university-of-mount-union',
      '204185',
      array['#752F8A']::text[],
      'https://www.mountunion.edu/',
      'medium',
      'Candidate''s cited PDF (mountunion.edu/content/u/...) 404s live and has no usable Wayback capture; a separately-found current "University Identity Standards Policy" PDF on the same domain also gives no hex, only Pantone/CMYK (''Mount Union purple is PMS 526... CMYK C=79 M=94 Y=11 K=0''). No literal hex/RGB found anywhere on mountunion.edu for purple or the metallic-gold PMS 871 second color, so per the no-off-domain-Pantone-conversion rule, gold and white were dropped rather than guessed. Purple corrected/confirmed via mountunion.edu''s own site-wide CSS custom color #752f8a, used consistently (95+ occurrences in the main stylesheet) as the dominant brand accent across the live domain -- on-domain CSS custom property, medium confidence per source-priority tier 3. Single chromatic ink only; no reliable third color found.'
    ),
    (
      'fairleigh-dickinson-university-florham-campus',
      '184694',
      array['#28334A','#70273D']::text[],
      'https://www.fdu.edu/about/university-leadership-offices/office-of-communication/graphic-standards-guide/color-font/',
      'high',
      'Live page body text (current, though the cached meta description is stale and cites different Pantone numbers): "Identity Colors -- The University colors for use in the logo, seal and the identity marks using FDU are Pantone 2380 and Pantone 2042... The corresponding HEX Codes for the University colors are: Pantone 2380:#28334A and Pantone 2042:#70273D." This is the university-wide identity page (applies to all FDU campuses including Florham); candidate''s approximated hexes (#22324B/#712A3C) corrected to the document''s literal values. No white/black named as an identity color.'
    ),
    (
      'wilkes-university',
      '216931',
      array['#002856','#FFCE00']::text[],
      'http://web.archive.org/web/20190927172316/https://www.wilkes.edu/about-wilkes/offices-and-administration/marketing-communications/creative-services/_logos/WILKES_style_guide.pdf',
      'high',
      'Candidate''s live PDF link is dead (404); recovered via Wayback. "WILKES UNIVERSITY PRIMARY COLOR PALETTE": Primary Blue PMS 295 HEX 002856; Primary Yellow PMS 116 HEX ffce00 -- "Wilkes University''s central colors." Candidate''s hexes were off by one digit each (#002855/#FFCD00); corrected to the document''s literal values. White dropped -- not part of the primary palette.'
    ),
    (
      'northwood-university',
      '171492',
      array['#0076BB','#F79713']::text[],
      'https://www.northwood.edu/',
      'medium',
      'Candidate''s cited PDF is dead (404); the closest Wayback capture (2011) gives RGB Navy 9/49/97 (#093161) and Medium Blue 0/128/195 (#0080C3) matching candidate exactly, but the live northwood.edu domain''s current CSS (a bespoke ''northwood-blocks'' WordPress plugin, not a generic theme) defines a completely different, dominant palette: --wp--preset--color--primary:#0076BB (used 312x across the homepage) and --secondary:#F79713, superseding the 2011 identity. Treated the 13-year-old archived PDF as stale per a likely rebrand and corrected to the current on-domain CSS custom properties (medium confidence, tier 3). Flag for human review: could not find a current prose-stated color page to corroborate the CSS values directly.'
    ),
    (
      'augustana-university',
      '219000',
      array['#002147','#FED100']::text[],
      'https://goaugie.com/',
      'medium',
      'Candidate''s cited goaugie.com quick-facts page is live but only states "School Colors Navy Blue & Gold (PMS 282, 109)" in prose, no hex. Corrected via the same athletics domain''s site-wide Sidearm site_colors config (consistent across multiple pages): primary_background #002147, primary_text #FED100 -- both plausible conversions of PMS 282/109 and consistent domain-wide. Candidate''s hexes (#002D62/#FFDD00) did not match this on-domain config and were corrected; candidate''s white dropped. The main augie.edu site''s inline colors were noisy/inconsistent (icon strokes, card borders) and not used as corroboration.'
    ),
    (
      'la-salle-university',
      '213367',
      array['#003356','#FFCE00']::text[],
      'http://web.archive.org/web/20230210021128/https://www.lasalle.edu/wp-content/uploads/sites/254/3429-Brand_Standards_Manual_072921.pdf',
      'high',
      'Candidate''s live PDF is dead (404); recovered via Wayback. "PRIMARY COLOR PALETTE -- The official University colors are PMS 540 Blue and PMS 7406 Gold." LA SALLE BLUE Hex: 003356; EXPLORER GOLD Hex: FFCE00. Candidate''s hexes (#003057/#F1C400) corrected to the document''s literal values. White dropped -- not part of the primary palette.'
    ),
    (
      'st-marys-university',
      '228149',
      array['#003366','#F2BF49']::text[],
      'https://rattlerathletics.com/',
      'medium',
      'Candidate''s cited style-guide PDF never resolves to a real PDF (live 200 is an HTML error page; every Wayback capture is also HTML, not application/pdf -- the file appears permanently gone). Official stmarytx.edu Style Guide page states colors only in prose: "Gold and blue are the school colors" (no hex/RGB anywhere on stmarytx.edu). Corrected via the athletics domain''s (rattlerathletics.com, same domain as the dead citation) site-wide Sidearm site_colors config: primary_background #003366, primary_text #F2BF49 -- medium confidence, tier 3 (official page names the colors, hex found elsewhere on the linked athletics domain). Candidate''s hexes (#004C97/#F2C75C) corrected; white dropped.'
    ),
    (
      'moravian-university',
      '214157',
      array['#00267A','#CCCCCC']::text[],
      'https://www.moravian.edu/identity/visual/colors',
      'high',
      'Live page: "Palette Primary -- Moravian Blue and Grey are the primary colors of the University''s identity." Moravian Blue HEX #00267A, Moravian Grey HEX #CCCCCC (both match candidate exactly). Candidate''s mechanically-attached white dropped -- the actual primary pair is Blue+Grey, not Blue+White; white does not appear in this page''s color list at all.'
    ),
    (
      'saint-marys-college-of-california',
      '123554',
      array['#D80024','#06315B']::text[],
      'http://web.archive.org/web/20220923093504/https://www.stmarys-ca.edu/sites/default/files/attachments/files/Style%20Guide_3.pdf',
      'high',
      'Candidate''s live PDF is dead (404); recovered via Wayback. "Primary: ... SMCC Red PMS 1797 Web HEX# d80024 ... SMCC Blue PMS 540 Web HEX# 06315b ... the distinctive SMCC Red and Blue" -- both match candidate exactly. White/Black appear in a separate reproduction-only row (CMYK 0/0/0/0 and 100K) ahead of the ''Secondary Color Palette'' header, framed as neutral base/demonstration colors rather than named identity colors ("the extended use of Primary Red provides the identity system with a clear focal point"); dropped per the prefer-1-2-chromatic guidance. Reordered Red first per the document''s own framing of Red as the focal/beacon color.'
    ),
    (
      'benedictine-university',
      '145619',
      array['#BA0C2F','#000000','#FFFFFF']::text[],
      'http://web.archive.org/web/20190929185207/http://www.ben.edu/marcom/brand-guidelines/color.cfm',
      'medium',
      'Candidate''s live page 403s (bot-walled); recovered via Wayback. Image alt text on the school''s own dedicated color page explicitly states: "Primary BenU color palette of red, black, and white" -- confirming the candidate''s exact 3-color set is the genuine, non-mechanical primary palette (corroborated by secondary sources describing BenU as historically red/white with black added in 1996). Red hex confirmed as #BA0C2F via the same archived page''s own CSS (og-bgred, used pervasively for headers/buttons/tabs sitewide) rather than literal prose HEX text, so capped at medium confidence (tier 3) rather than high.'
    ),
    (
      'connecticut-college',
      '128902',
      array['#002F5F','#FFFFFF']::text[],
      'https://www.conncoll.edu/offices/office-of-communications/visual-identity/college-colors/',
      'high',
      'CORRECTED DURING QA: the original justification for dropping light blue was factually wrong; hexes/confidence unchanged. Live page: "The College''s official colors are dark blue and white." Table gives HTML/Web #002F5F for dark blue (Pantone 295 PC) and, in a separate column, #9EC3DE (''light blue'') as its OWN independently specified color (Pantone 543 PC, full RGB/CMYK/spot spec) -- not a screen tint of dark blue. The table''s ''Black and White'' row (Solid Black / 35% Screen) is a per-color black-and-white print-reproduction instruction for each color individually, not a claim that light blue derives from dark blue. Light blue was still dropped, but for the correct reason: the page''s own prose limits the school''s ''official colors'' to exactly dark blue and white, even though light blue is a real, separately-specified accompanying color on the same page.'
    ),
    (
      'vanguard-university-of-southern-california',
      '123651',
      array['#003768','#FEC325']::text[],
      'https://vanguardlions.com/sports/2023/1/3/3224_133172544627309865.aspx',
      'medium',
      'Cited quick-facts page states "Colors Navy Blue/Gold" in prose (no literal hex), corroborated by the same page''s Sidearm site_colors config: primary_background #003768 (matches candidate exactly), secondary_background #fec325 (close to candidate''s #FFC522, corrected to the config''s literal value). White dropped -- not named in prose.'
    ),
    (
      'black-hills-state-university',
      '219046',
      array['#006233','#FFC726']::text[],
      'http://web.archive.org/web/20231009192759/https://www.bhsu.edu/Faculty-Staff/Marketing-and-Communications/Visual-Identity-Standards/Colors-and-Fonts',
      'high',
      'Candidate''s live page 404s; recovered via Wayback. "The official colors are: Green ... Hexadecimal (web version)- #006233 ... Gold ... Hexadecimal (web version)- #FFC726" -- both match candidate exactly, exactly two official colors stated. Candidate''s mechanically-attached white dropped.'
    ),
    (
      'st-lawrence-university',
      '195216',
      array['#AF1E2D','#4B2B23']::text[],
      'http://web.archive.org/web/20200823115020/http://www.stlawu.edu/sites/default/files/resource/AcademicStyleGuide_bleed_cropsV5.pdf',
      'high',
      'Candidate''s live PDF is dead (404); recovered via Wayback. "PRIMARY COLORS ... SCARLET HEX: #AF1E2D ... BROWN HEX: #4B2B23" -- both match candidate exactly; the other three colors (Burnt Orange, Golden Yellow, Green Gray) are explicitly under a separate ''SECONDARY COLORS'' heading. Candidate''s mechanically-attached white dropped -- not part of the primary pair. Derive-inks note: Scarlet and Brown are close in lightness/hue, so deriveInks treats Brown as A and synthesizes a brighter red (#fe404e) for B rather than using the real Scarlet #AF1E2D -- flagged per the brief as a case where a stored chromatic primary doesn''t survive into the derived plates unchanged.'
    ),
    (
      'southern-university-at-shreveport',
      '160649',
      array['#00263E','#FFC72C']::text[],
      'https://www.susla.edu/',
      'medium',
      'Candidate''s cited citation was actually a wrong-institution pull: the subr.edu URL is Southern University and A&M College at Baton Rouge''s (a separate sister institution in the SU System) visual style guide, not SUSLA''s; both the 2017 and current (Oct 2024) subr.edu style-guide PDFs only state Pantone numbers (PMS 292 blue / PMS 123 gold) with no hex/RGB anywhere -- off-domain Pantone conversion is barred by policy. Corrected to SUSLA''s own domain (susla.edu): its bespoke site CSS (not a generic template) uses #00263E and #FFC72C pervasively as the primary navy/gold theme colors (buttons, borders, stat accents), consistent with the ''Blue and Gold'' identity shared across the SU System. Medium confidence, tier 3.'
    ),
    (
      'depauw-university',
      '150400',
      array['#FFCF01','#111C24']::text[],
      'http://web.archive.org/web/20150923213644/http://www.depauw.edu/files/resources/dep_identitymanual-w-athletics.pdf',
      'high',
      'Candidate''s live PDF is dead (404); recovered via Wayback. "Website Colors ... DePauw Colors: Gold FFCF01, Black 111C24" -- both match candidate exactly, listed distinctly from the page''s separate ''Website Accent Colors'' (Green/Blue/Red/Orange/Gray/Purple). Candidate''s mechanically-attached white dropped -- not part of the named DePauw Colors set. Gold ordered first per DePauw''s well-documented ''Old Gold and Black'' identity.'
    ),
    (
      'oklahoma-christian-university',
      '207324',
      array['#660000','#E2D79B']::text[],
      'http://oceagles.com/sports/2014/8/5/GEN_0805142052.aspx',
      'high',
      'Live page titled "Official Logos and Colors": "The official colors for OC Athletics are Maroon, Silver, Tan, Black and White ... Hexadecimal colors (web) 660000 cccccc e2d79b" for Maroon/Silver/Tan respectively (Maroon matches candidate exactly). Of the five official colors, kept Maroon and Tan as the two chromatic values per the prefer-1-2-chromatic guidance (Silver/Black/White are neutrals); dropped candidate''s white and the achromatic Silver/Black.'
    ),
    (
      'washington-and-lee',
      '234207',
      array['#003087','#707372']::text[],
      'http://web.archive.org/web/20191211185923/https://www.wlu.edu/communications-and-public-affairs/publications-and-graphic-design/graphic-standards/complementary-typeface-and-color',
      'high',
      'Candidate''s live page is dead (404); recovered via Wayback. "Only two colors exist for the university identity. They are PMS 287 and PMS 424." W&L Blue (PMS 287) HEX 003087; Liberty Hall Grey (PMS 424) HEX 707372. Candidate''s hexes (#003399 and white) were both wrong -- corrected to the document''s literal values; the second official color is a named grey, not white. Derive-inks note: the grey is desaturated enough to be treated as a neutral by deriveInks (chroma below threshold), so the output falls back to a single-ink pair with a synthesized bright blue for B rather than the real grey.'
    ),
    (
      'gustavus-adolphus-college',
      '173647',
      array['#FFCF00']::text[],
      'https://gustavus.edu/marketing/files/graphicstandards.pdf',
      'high',
      'Live PDF: "GUSTAVUS GOLD -- The main College color is PANTONE 7406 or the equivalent in CMYK, RGB, or HEX ... HEX FFCF00" (matches candidate''s gold exactly). No black or white appears anywhere as a named color in the document''s Color Palette section (only Gold, an ''Extended Palette'' of accent colors, and neutral ''Background Colors''); candidate''s mechanically-attached black/white dropped entirely -- single chromatic ink.'
    ),
    (
      'occidental-college',
      '120254',
      array['#FF671F','#000000']::text[],
      'http://web.archive.org/web/20200223033526/https://www.oxy.edu/sites/default/files/assets/OMC/Oxy_Style_Guide_Updated_5_12_2017.pdf',
      'high',
      'Candidate''s live PDF is dead (404); recovered via Wayback. "CORE COLOR PALETTE / Core Colors ... instantly recognizable as Oxy ... OXY ORANGE PMS 165 HEX #FF671F ... Black HEX #000000" -- exactly two core colors, matches candidate''s orange/black. Candidate''s mechanically-attached white dropped -- white is not part of the Core Color Palette (a separate ''Secondary Color Palette'' follows with four different colors, none of them white).'
    ),
    (
      'nazareth-university',
      '193584',
      array['#7A3AAA','#EEAA55']::text[],
      'https://www2.naz.edu/marketing-and-communications/branding-toolkit/color-palette',
      'high',
      'Live page (candidate''s /branding-toolkit/color/ URL redirects here): "Purple Pantone 267 ... #7a3aaa Gold Pantone 7509 ... #eeaa55" listed ahead of a separate ''Secondary Colors'' (Teal/Orange/Magenta/Blue) and ''Neutral Colors'' (Light/Dark) section. Candidate''s hexes (#4B375E/#D4A66D) were substantially off and corrected to the document''s literal values. No white in the primary section.'
    ),
    (
      'pennsylvania-state-university-penn-state-berks',
      '214704',
      array['#001E44','#1E407C']::text[],
      'https://brand.psu.edu/design-toolkit/design-essentials',
      'high',
      'Live page (university-wide Penn State brand system, applies to all Commonwealth campuses including Berks): "The four colors of our Penn State Brand Palette ... consistently using the primary brand blues (Nittany Navy and Beaver Blue) strongly links your design to the Penn State brand." Nittany Navy HEX #001E44 (matches candidate exactly); Beaver Blue HEX #1e407c. Added Beaver Blue and dropped candidate''s White out (#FFFFFF is also listed on the page but the prose explicitly frames Navy+Beaver Blue, not Navy+White, as ''the primary brand blues''/the pair that ''links your design to the Penn State brand''). Derive-inks note: because Navy and Beaver Blue are close in hue/lightness, deriveInks treats them as too close and synthesizes a brighter blue (#578ff3) for B rather than using the real Beaver Blue.'
    ),
    (
      'davidson-college',
      '198385',
      array['#CF102D','#373534']::text[],
      'https://davidsonwildcats.com/',
      'medium',
      'Candidate''s cited media-guide PDF states only "Colors: Red (PMS 186) and Black" in prose, no hex/RGB anywhere in the document. The domain''s own CSS contains a decoy: #003057/#E87722 appear repeatedly but are labeled ''s-common-footer__sidearm-logo'' -- the Sidearm Sports vendor''s own footer logo colors, not Davidson''s (a clear instance of the wrong-swatch trap this task warns about; NOT used). The site''s actual serialized page-config data separately keys siteColorPrimaryBackground to #cf102d (red) and siteColorSecondaryBackground to #373534 (near-black charcoal), consistent with the ''Red and Black'' identity. Corrected candidate''s hexes and dropped white (not named in the quick-facts prose). Derive-inks note: #373534 is desaturated enough to be rejected as neutral by deriveInks, so B is a synthesized bright red rather than the true near-black secondary.'
    ),
    (
      'whitworth-university',
      '237066',
      array['#C22033','#000000']::text[],
      'http://web.archive.org/web/20250608195459/https://www.whitworth.edu/cms/media/whitworth/documents/administration/marketing-amp-communications/brand-amp-identity/whitworth-university-brand-guide.pdf',
      'high',
      'Candidate''s live PDF URL redirect-loops; recovered via Wayback. "Color Palette ... Primary Brand Colors [vs] Secondary Brand Colors" table: Primary = Pantone 200C HEX #C22033 + Base Black HEX #000000 (matches candidate''s first two values exactly); the other three swatches (#67BAAF/#007C89/#C7B683) are explicitly under ''Secondary Brand Colors''. Candidate''s mechanically-attached white dropped.'
    ),
    (
      'gardner-webb-university',
      '198561',
      array['#BB0000','#141414','#FFFFFF']::text[],
      'https://gardner-webb.edu/about/offices-and-departments/marketing-and-communications/brand-guidelines/color/',
      'high',
      'Page 403s on direct curl but a clean Wayback capture confirms live content: "Gardner-Webb''s colors of red, black, pure white and pale gray comprise the Gardner-Webb primary color palette ... GWU Red Hex #BB0000, Rich Black Hex #141414, Pure White Hex #FFFFFF, Pale Gray Hex #E6E7E8." Candidate''s exact 3-of-4 selection (Red/White/Black) confirmed as-is; Pale Gray dropped to stay within the 3-value max, following the prefer-1-2-chromatic-plus-a-neutral guidance and the document''s own listed order.'
    ),
    (
      'coppin-state-university',
      '162283',
      array['#FFC915','#003056']::text[],
      'https://www.coppin.edu/',
      'medium',
      'Candidate''s cited style-guide PDF is dead live but was recovered via a full (untruncated) 2014 Wayback capture; it names "the standard LOGO colors ... Reflex Blue and Gold PMS 871" with no hex/RGB anywhere in the document. Corrected via coppin.edu''s own domain: the live homepage''s mobile theme-color/favicon-mask meta tags declare #003056, and the site''s Bootstrap-based theme CSS explicitly sets --primary:#FFC915 and --secondary:#003056 (147/101 occurrences respectively) -- both match the candidate''s exact hexes. On-domain CSS custom property, medium confidence (tier 3, no literal on-domain hex prose). White dropped -- not named anywhere as a Coppin color (only Reflex Blue and Gold).'
    ),
    (
      'rhodes-college',
      '221351',
      array['#C4022B','#000000']::text[],
      'https://www.rhodes.edu/sites/default/files/RHODES_Brand_Standards_2020.pdf',
      'high',
      'Live PDF: "PRIMARY PALETTE -- Rhodes'' primary colors are red and black ... RHODES RED HEX C4022B ... RHODES BLACK HEX 000000" -- both match candidate exactly. Candidate''s mechanically-attached white dropped -- the primary palette is explicitly just red and black; white/neutral is discussed only as generic ''canvas'' space, not a named color.'
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