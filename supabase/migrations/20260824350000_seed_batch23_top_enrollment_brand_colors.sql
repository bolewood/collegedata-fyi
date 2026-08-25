-- Batch 23 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a dropped
-- mechanically-attached white/neutral: the-university-of-the-south (Purple/
-- Vegas Gold RGB-exact match on Sewanee's own athletics brand identity PDF,
-- recovered via Wayback, white dropped -- explicitly secondary not
-- primary), ouachita-baptist-university (Purple/Gold RGB-exact match,
-- recovered via Wayback, white dropped), illinois-wesleyan-university
-- (Green/White exact 2-of-2 "official colors" match, gray dropped -- a
-- separate support color), university-of-evansville (Purple/Orange exact
-- match on the live Missouri Valley Conference-wide style guide, white
-- dropped), concordia-university-irvine (Green/Gold/White exact 3-of-3
-- match, recovered via Wayback, white explicitly one of only three
-- labeled primary colors), whitman-college (Blue/Gold exact match at the
-- brief's own Wayback URL, candidate's "black" corrected away -- it was
-- actually a secondary 90%-tint gray, not primary), virginia-military-
-- institute (Red/Yellow/White exact 3-of-3 match on VMI's current Brand
-- Guide, replacing candidate's dead specific URL), oklahoma-city-
-- university (Blue/White/Black exact 3-of-3 match, recovered via
-- Wayback after the live site redesigned away from the candidate's
-- citation), university-of-puget-sound (Maroon/White exact match on
-- Puget Sound's own Visual Identity Standards PDF -- candidate's
-- underlying hex values were correct, but the candidate's citation URL
-- pointed to an unrelated school, Purchase College; corrected the
-- citation via a fresh search, not the color values).
--
-- Corrected (candidate hex, color set, or source did not match the
-- school's own current official source): pomona-college (candidate's
-- citation loads live but has zero color content; found the real
-- Graphic Standards Manual page instead, single Pomona Blue #0057B8,
-- candidate's guessed hex and orange were both wrong), wagner-college
-- (candidate's citation dead; live Colors page confirms the green and
-- supplies the real gold, replacing candidate's guessed white/gray),
-- linfield-university (candidate's purple+red confirmed exactly on the
-- current Brand Guidelines PDF, but white demoted -- explicitly
-- SECONDARY, not one of the two labeled PRIMARY colors), mcdaniel-
-- college (candidate's citation is a dead Sidearm SPA shell; its own
-- embedded site-config JSON supplied the school's actual configured
-- green/gold, correcting candidate's approximate hexes, medium
-- confidence), adrian-college (candidate's citation dead; the current,
-- live official Brand Guidelines PDF confirms "black and gold" but
-- states only Pantone/CMYK with zero hex/RGB anywhere in 30 pages;
-- fell back to a reputable secondary color-code index, low confidence),
-- st-marys-college-of-maryland (candidate's citation dead, recovered via
-- Wayback; "college colors are blue and white" confirmed exactly,
-- candidate's guessed gold dropped -- not part of the college colors,
-- only appears in an explicitly-separate complementary-colors table
-- under a different, uncorroborated hex), willamette-university
-- (candidate's citation URL is actually live and correct, but both of
-- candidate's guessed hexes were wrong; corrected to the page's own
-- stated Cardinal/Gold values), western-colorado-university (candidate's
-- citation dead, recovered via Wayback; kept Crimson + Western Slate as
-- the two colors prose explicitly calls "historically core," dropping
-- candidate's mechanically-attached white from the larger 8-color
-- primary swatch group), rockhurst-university (candidate's citation
-- dead; the current live Brand Guidelines PDF has only ONE color under
-- "PRIMARY PALETTE" -- Rockhurst Blue #0058A6 -- correcting candidate's
-- wrong hex and dropping its white/black), university-of-lynchburg
-- (candidate's citation dead with no Wayback capture; the official PDF
-- states only Pantone 185 for "Hornet Red," no hex anywhere, so used the
-- site's own Elementor global-color CSS custom properties as an
-- on-domain fallback, medium confidence), lancaster-bible-college,
-- fresno-pacific-university, lincoln-university-pa, and neumann-
-- university (all four candidates cite dead/empty Sidearm SPA shells;
-- each shell's own embedded site-config JSON supplied the school's
-- actual configured primary/secondary theme colors, correcting
-- candidate's approximate hexes, medium confidence in all four cases),
-- chadron-state-college (candidate's guessed hex and its black/white
-- were all wrong; the current live Quick Brand Guide states a single
-- official color, Cardinal #872046, with black/gray/white explicitly
-- secondary), benedict-college (candidate's citation dead with only a
-- bot-blocked Wayback capture; used the site's own Elementor
-- global-color CSS custom properties, medium confidence), sarah-
-- lawrence-college (a corrupted/truncated Wayback capture of candidate's
-- dead citation was replaced with a clean 2022 capture; confirmed
-- candidate's Dark/Medium Green exactly but corrected its guessed white
-- -- not a named school color -- to the missing third true "SCHOOL
-- COLOR," Light Green), ohio-wesleyan-university (candidate's citation
-- is a live web-design-system reference rather than a formal brand book,
-- listing 4 different reds with none singled out as official; used the
-- first-listed red + black, medium confidence given the ambiguity),
-- pacific-university (candidate's citation dead, recovered via Wayback;
-- "primary colors ... are red, black and grey" -- corrected candidate's
-- white, which the source explicitly treats as an apparel add-on, not
-- one of the three named primaries, to the real third primary, Grey).
--
-- Left null (no hex/RGB found anywhere on the school's own domain, only
-- Pantone or nothing at all -- see per-school notes in the JSONL for
-- exactly what was searched): union-university (candidate's own exact
-- citation recovered via Wayback states only "Cardinal (194)," no hex;
-- full CDX search of uu.edu/styleguide turned up nothing better),
-- lincoln-memorial-university (candidate's citation turned out to be
-- LMU's editorial writing-style manual, not a color/brand guide; its one
-- relevant line states only Pantone 288/421, no hex anywhere on
-- lmunet.edu; note "brand.lmu.edu" is a different school, Loyola
-- Marymount, sharing the acronym -- not used).
--
-- Derive-inks note: western-colorado-university's second color, Western
-- Slate (#565A5C), is desaturated enough that deriveInks' neutral-
-- rejection rule (chroma < 0.035) treats it as a neutral and rejects it
-- despite being a genuine named brand color, falling back to a
-- single-ink path with a synthesized bright B rather than using the
-- stated slate directly -- expected deriver behavior given how close to
-- gray that particular ink is, not a data error. The same neutral-
-- rejection rule correctly drops a stored black/white/gray from several
-- other single-chromatic schools (adrian-college, st-marys-college-of-
-- maryland, university-of-puget-sound, illinois-wesleyan-university,
-- university-of-lynchburg, lancaster-bible-college, ohio-wesleyan-
-- university, pacific-university, oklahoma-city-university), leaving a
-- single ink to drive a synthesized A or B plate -- also expected
-- behavior, not a data error; the neutral value is still retained in
-- brand_colors when it was explicitly one of the school's own named
-- primary colors.
--
-- See data/brand-colors/batch-23-2026-08-24.jsonl for the full per-school
-- record, including the two null entries.

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
      'pomona-college',
      '121345',
      array['#0057B8']::text[],
      'https://www.pomona.edu/administration/communications/logos-guidelines/graphic-standards-manual',
      'high',
      'Candidate''s cited Cecil Image and Athletics Color Usage Guidelines page loads live but contains zero color/hex/Pantone content anywhere in its body (confirmed via raw HTML text extraction and WebFetch, which independently found no colors on that page). Candidate''s guessed hex (#20438F) and orange (#F7941D) don''t match anything published. Found Pomona''s official Graphic Standards Manual page instead (linked from the same Office of Communications section): "Approved Colors / Pomona Blue: Pantone 2935 ... Web: R-0/G-87/B-184 or Hex #0057b8. For most uses, the preferred color is Pomona Blue (Pantone 2935) or black." No orange/gold is named anywhere on the domain as an approved color. Kept the single confirmed blue; dropped candidate''s white/orange entirely.'
    ),
    (
      'wagner-college',
      '197197',
      array['#004331','#AA8E3C']::text[],
      'https://wagner.edu/communications/visual-identity/colors/',
      'high',
      'Candidate''s citation (wagner.edu/communications/graphic-identity/) is dead. Found the current live Colors page instead: "Primary Colors / Wagner Green ... Hexadecimal: #004331 / Wagner Gold ... Hexadecimal: #AA8E3C." Confirms candidate''s green exactly; corrected candidate''s white+gray (not mentioned anywhere in the two-color Primary Colors section) to the real second primary color, Wagner Gold.'
    ),
    (
      'linfield-university',
      '209065',
      array['#470A68','#D50032']::text[],
      'https://www.linfield.edu/assets/files/stratcom/brand-guidelines-v1.pdf',
      'high',
      'Candidate''s inside.linfield.edu citation redirects/404s. Found Linfield''s current Brand Guidelines PDF (linked from the live brand-guidelines.html page): "PRIMARY COLOR: Purple #470A68, Red #d50032" vs "SECONDARY COLOR: Lavender #825dc7, Gold #aa9050, White #ffffff." Purple and Red are explicitly the only two PRIMARY colors; White is explicitly SECONDARY. Confirms candidate''s purple+red exactly; dropped candidate''s white per the explicit primary/secondary split in the document.'
    ),
    (
      'mcdaniel-college',
      '164270',
      array['#054731','#F5D116']::text[],
      'https://www.mcdanielathletics.com/releases/2011-12/newlogo/index',
      'medium',
      'Candidate''s citation is a dead Sidearm ''newlogo'' announcement page, loading only as an empty Sidearm SPA shell (title "Sidearm Sports, opens a new window"). The shell''s own embedded site-config JSON states the athletics department''s configured theme colors: "primary_background":"#054731","secondary_background":"#F5D116" — an on-domain CSS/site-config value, not a formal brand PDF, hence medium rather than high. No brand/identity PDF found elsewhere on mcdaniel.edu or mcdanielathletics.com. Corrected candidate''s approximate green/gold (#00674D/#F6D016) to the exact configured values; dropped candidate''s white (not part of the 2-color site config).'
    ),
    (
      'union-university',
      '221971',
      NULL::text[],
      NULL,
      NULL,
      'Candidate''s citation (uu.edu/styleguide/colorstype.cfm) is dead live; recovered the exact same page via Wayback (2012 capture): "The standard university colors are Cardinal (194) and Cream (White). Black is to be used as an accent or background color." No hex or RGB is stated anywhere on that page or on any other captured uu.edu styleguide page found via a full CDX search (only the Pantone number "194" is given; the color swatches on that era''s page are an image, not text). Current live uu.edu/styleguide/colors/ page and its predecessor both 404. Per the no-Pantone-conversion rule, left null rather than using a third-party PMS-to-hex conversion.'
    ),
    (
      'the-university-of-the-south',
      '221519',
      array['#582C83','#CEB888']::text[],
      'https://www.sewanee.edu/media/offices/marketing--communications/019_15_athletics-brand-identity-guide_v4-(2).pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback (2017 capture). "Purple is the primary color in the Sewanee Athletics palette. Secondary colors are: Vegas Gold, White, and Process Black." Purple HEX #582C83 and Vegas Gold HEX #CEB888 both confirm candidate''s guesses exactly; White is explicitly listed as one of three SECONDARY colors (not primary), so dropped per the narrow-exception rule.'
    ),
    (
      'adrian-college',
      '168528',
      array['#000000','#FFC72C']::text[],
      'https://teamcolorcodes.com/adrian-college-bulldogs-color-codes/',
      'low',
      'Candidate''s citation is dead; found Adrian''s current, live Brand Guidelines PDF instead (adrian.edu/files/assets/adriancollegebrandguidelines.pdf). "The official colors of Adrian College are black and gold" — but the Primary Colors table states only PMS/CMYK builds (PMS 123 C gold, process black), no hex or RGB anywhere across the full 30-page document (confirmed by full-text search). Per the no-Pantone-conversion rule this cannot be medium/high; fell back to a reputable secondary color-code index for the standard black/PMS-123-gold hex pair, which matches the modern-era gold candidate guessed. Low confidence.'
    ),
    (
      'st-marys-college-of-maryland',
      '163912',
      array['#00205C','#FFFFFF']::text[],
      'https://www.smcm.edu/brand-resources/wp-content/uploads/sites/62/2014/07/smcm-identity-guide-revised-2016.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback. "The St. Mary''s college colors are blue and white ... Warm gray is an accent color." WEB HEX: Navy Blue - 00205c (confirms candidate exactly). White is explicitly one of the two college colors named in prose. Candidate''s third hex (gold #FEC10D) does not appear anywhere in the document — gold only appears in a separate "COMPLEMENTARY COLORS" table explicitly stated to not replace the college colors, and even there the real value (#FFB81D) differs from candidate''s guess. Dropped gold and the accent warm-gray; kept only the two explicitly-named college colors.'
    ),
    (
      'ouachita-baptist-university',
      '107512',
      array['#552988','#FFC627']::text[],
      'http://www.obu.edu/files/2013/12/OuachitaAthleticsStyleGuide.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback. "PRIMARY COLOR: Purple RGB 85/41/136 (=#552988) ... SECONDARY COLOR: Gold RGB 255/198/39 (=#FFC627)" — both RGB-derived (not Pantone-table guesses), confirming candidate''s two chromatic hexes exactly. White and Graphite are both listed as further SECONDARY colors, not primary; dropped candidate''s mechanically-attached white.'
    ),
    (
      'university-of-puget-sound',
      '236328',
      array['#660000','#FFFFFF']::text[],
      'https://www.pugetsound.edu/sites/default/files/2022-07/COM22VISUALIDENTITYSTANDARDS_June2022.pdf',
      'high',
      'Candidate''s citation URL is for an unrelated school (Purchase College''s athletics rebrand announcement) — a wrong-citation error, not used; ran a fresh search per the brief''s instruction instead. Found Puget Sound''s own official Visual Identity Standards PDF: "The official primary colors of University of Puget Sound are maroon and white ... MAROON PANTONE 188 HEX: 660000 ... HEX: FFFFFF" — both explicitly the two named primary colors, matching candidate''s guessed hex exactly (candidate''s underlying color values were right, just cited to the wrong school).'
    ),
    (
      'willamette-university',
      '210401',
      array['#791716','#C0AC7E']::text[],
      'http://wubearcats.com/information/sportsinformation/downloads/index',
      'high',
      'Candidate''s citation URL is actually live and correct (an active Willamette Athletics Identity Guidelines page), but its stated hex values differ from candidate''s guesses: "Colors / Cardinal Gold / Web — HEX #791716 [Cardinal] #c0ac7e [Gold] / Print — CMYK ... (Pantone 202) ..." Corrected both of candidate''s hexes to the page''s own stated values; no white/black is part of this explicit 2-color spec, so dropped candidate''s mechanically-attached white.'
    ),
    (
      'western-colorado-university',
      '128391',
      array['#A71930','#565A5C']::text[],
      'http://www.western.edu/sites/default/files/media/raw/Western_Brand_Identity_Guidelines_083013.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback. "Colors - Primary" page states 8 colors as one labeled group (Crimson #A71930, Bright Red #E00034, Shadowed White #D1D3D4, White #FFFFFF, Medium/Light Western Slate, Black #000000, Western Slate #565A5C), but prose narrows this to the true core: "The Western brand colors historically have been crimson and slate." Kept Crimson + Western Slate — both confirm candidate''s exact chromatic hexes — and dropped candidate''s mechanically-attached white, which is one of 8 in the broader primary group but not one of the two ''historically core'' colors.'
    ),
    (
      'illinois-wesleyan-university',
      '145646',
      array['#006747','#FFFFFF']::text[],
      'https://www.iwu.edu/identity/athletics-branding-guide.pdf',
      'high',
      'Candidate''s citation is live and confirmed. "PRIMARY PALETTE / IWU Green and white are the official colors for Illinois Wesleyan athletics ... Hex Code: #006747" paired with White #FFFFFF — explicitly the two-color primary palette. A separate "SUPPORT COLORS" section lists IWU Gray (#C1C6C8) as a support color, not primary; dropped candidate''s gray accordingly.'
    ),
    (
      'rockhurst-university',
      '179043',
      array['#0058A6']::text[],
      'https://www.rockhurst.edu/sites/default/files/media/files/2026-02/2024%20Brand%20Guide%20Print.pdf',
      'high',
      'Candidate''s citation URL is dead. Found Rockhurst''s current live Brand Guidelines PDF (linked from the live /brand/color page). "PRIMARY PALETTE: Rockhurst Blue PMS 2388 HEX 0058A6" is the sole entry under Primary; "SECONDARY PALETTE: Kansas City Blue #A2DCED, Wisdom Green #7CCCBD" is a separate, distinct tier, with a further Accent tier below that. Candidate''s guessed hex (#0046AD) and white/black were all wrong or unconfirmed; corrected to the single true primary blue.'
    ),
    (
      'university-of-lynchburg',
      '232609',
      array['#EA0029','#A7A8AA']::text[],
      'https://www.lynchburg.edu/about/marketing-and-communications/brand-and-style-guidelines/',
      'medium',
      'Candidate''s citation URL 404s and has no Wayback capture. The live Brand & Style Guidelines page and its linked logos-and-marks PDF both name "Hornet Red" but state only Pantone 185, no hex anywhere. The site''s own Elementor global-color CSS custom properties (loaded on every lynchburg.edu page) define "--e-global-color-primary:#EA0029" and a repeated anchor-link gray of "#a7a8aa" matching the standard PMS Cool Gray 6 conversion candidate guessed almost exactly. Used as on-domain CSS custom properties per the medium-confidence allowance; corrected candidate''s red slightly and dropped white (not present in the CSS kit).'
    ),
    (
      'lincoln-memorial-university',
      '220631',
      NULL::text[],
      NULL,
      NULL,
      'Candidate''s citation is dead. Recovered the school''s PDF at its original URL via Wayback, but it turned out to be LMU''s editorial *writing* Style Manual (AP-style/abbreviation guide), not a color/brand guide — a wrong-citation trap. It does contain one relevant line: "The University''s colors for print are blue (PMS 288) and gray (PMS 421)" — Pantone/CMYK only, no hex or RGB anywhere in the document. Checked the live lmunet.edu Style Guide and Logos page and found no color content (JS-rendered, no PDF link, no hex). Note: "brand.lmu.edu" found via search is Loyola Marymount University, a different school sharing the LMU acronym — not used. Left null per the no-Pantone-conversion rule.'
    ),
    (
      'lancaster-bible-college',
      '213400',
      array['#C8102E','#BDC2C2']::text[],
      'https://lbcchargers.com/sports/2012/9/11/GEN_0911123444.aspx',
      'medium',
      'Candidate''s citation is a dead Sidearm page, loading only as an empty SPA shell (title "Sidearm Sports, opens a new window"). The shell''s embedded site-config JSON states: "primary_background":"#c8102e","secondary_background":"#bdc2c2" — on-domain CSS/site-config (medium confidence, not a formal brand PDF). No brand/identity guide found elsewhere on lbc.edu. Corrected candidate''s approximate red to the exact configured value and its gray; dropped candidate''s black (not part of the 2-color site config).'
    ),
    (
      'fresno-pacific-university',
      '114813',
      array['#00205B','#FF6114']::text[],
      'http://www.fpuathletics.com/sports/2009/3/27/quickfacts.aspx',
      'medium',
      'Candidate''s citation is a dead Sidearm page, loading only as an empty SPA shell. The shell''s embedded site-config JSON states: "primary_background":"#00205b","secondary_background":"#ff6114" — on-domain CSS/site-config (medium confidence). No brand PDF found elsewhere on fresno.edu or fpuathletics.com. Corrected candidate''s approximate blue/orange to the exact configured values; dropped candidate''s white.'
    ),
    (
      'chadron-state-college',
      '180948',
      array['#872046']::text[],
      'https://www.csc.edu/media/website/content-assets/documents/pdf/college-relations/Quick-Brand-Guide.pdf',
      'high',
      'Candidate''s citation page is live but names colors without stating hex; it links to a current "Quick Brand Guide" PDF: "Chadron State College''s official color is Cardinal. Black, Crites Gray, and White are the secondary colors." MAIN COLORS table: Cardinal (PMS 208) RGB #872046. Candidate''s guessed hex (#660033) and its black/white are all wrong or explicitly secondary, not the singular official color; corrected to the one true official Cardinal.'
    ),
    (
      'university-of-evansville',
      '150534',
      array['#470A68','#ED8B00']::text[],
      'https://s3.amazonaws.com/sidearm.sites/mvc.sidearmsports.com/documents/2022/8/29/Style_Guide_Full_Version.pdf',
      'high',
      'Candidate''s citation (a Missouri Valley Conference-wide sidearm style guide PDF covering all member schools including UE) is live and confirmed. "EVANSVILLE BRANDING / COLORS ... HEX #470A68 [Purple] HEX #ED8B00 [Gold/Orange]" — exact match to candidate''s two chromatic hexes. Dropped candidate''s mechanically-attached white, not part of the document''s 2-color entry for Evansville.'
    ),
    (
      'lincoln-university-pa',
      '213598',
      array['#16234D','#FC6C0F']::text[],
      'https://lulions.com/',
      'medium',
      'Candidate''s citation (lulions.com homepage) has no visible color content in raw HTML, loading as an empty Sidearm SPA shell. The shell''s embedded site-config JSON states: "primary_background":"#16234d","secondary_background":"#fc6c0f" — on-domain CSS/site-config (medium confidence). No brand PDF found elsewhere on lincoln.edu. Corrected candidate''s guessed navy/orange to the exact configured values; dropped candidate''s white.'
    ),
    (
      'benedict-college',
      '217721',
      array['#3E1865','#F5C650']::text[],
      'https://www.benedict.edu/',
      'medium',
      'Candidate''s citation (cms node/25) 404s live; its only Wayback capture is a bot-verification JS loader with no real content. Found benedict.edu''s own Elementor global-color CSS custom properties instead: "--e-global-color-primary:#3E1865" paired repeatedly with "#f5c650" in the site''s own header/menu highlight styling (the same gold used site-wide against the purple) — on-domain CSS custom properties, medium confidence. No formal brand PDF found. Corrected candidate''s guessed purple/gold to the site''s actual configured values; dropped candidate''s white.'
    ),
    (
      'concordia-university-irvine',
      '112075',
      array['#004C23','#FDB724','#FFFFFF']::text[],
      'https://www.cui.edu/Portals/0/uploadedimages/fte/brand/Concordia-Athletic-Style-Guide-022.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback. "Primary Colors / Green, gold and white are the official colors for Concordia University Athletics ... #004C23 / #FDB724 / #FFFFFF" — confirms candidate''s 3-of-3 exactly, with white explicitly one of only three labeled primary colors.'
    ),
    (
      'neumann-university',
      '214272',
      array['#003F72','#FFD100']::text[],
      'https://www.neumannathletics.com/sports/2008/8/1/GEN_0801083615.aspx',
      'medium',
      'Candidate''s citation is a dead Sidearm page, loading only as an empty SPA shell. The shell''s embedded site-config JSON states: "primary_background":"#003f72","secondary_background":"#ffd100" — on-domain CSS/site-config (medium confidence). No brand PDF found elsewhere on neumann.edu. Corrected candidate''s blue; candidate''s gold (#FFD102) was already nearly exact. Dropped candidate''s white.'
    ),
    (
      'whitman-college',
      '237057',
      array['#001F5B','#FFC627']::text[],
      'https://web.archive.org/web/20190424011421/https://www.whitman.edu//communications/graphic-design/visual-identity/color-palette',
      'high',
      'Fetched the exact Wayback URL given in the brief. "Primary Colors / Whitman''s primary colors are ''Whitman blue'' and gold ... Whitman Blue #001F5B / Whitman Yellow #FFC627" — confirms candidate''s blue+gold exactly. Candidate''s third color is neither pure black nor primary: the document''s "Whitman Black" is actually a 90%-tint gray (#333333) listed under SECONDARY colors, not primary; dropped it.'
    ),
    (
      'sarah-lawrence-college',
      '195304',
      array['#3D6229','#6E9A43','#CFD95F']::text[],
      'https://www.sarahlawrence.edu/marketing-communications/sarah-lawrence-college-visual-identity-style-guide.pdf',
      'high',
      'Candidate''s citation is dead; a 2022 Wayback capture parses cleanly (an earlier/later capture was truncated/corrupted by Wayback''s own WARC length limit and unusable — retried with qpdf repair, still broken, so used the clean 2022 capture instead). "SCHOOL COLORS ... Light Green / Medium Green / Dark Green" are named as the College''s actual school colors, cross-referenced to the document''s own Extended Palette table (GREEN column: light #CFD95F, medium #6E9A43, dark #3D6229). Confirms candidate''s Dark Green and Medium Green exactly; corrected candidate''s white (not a named school color — the document separately notes ''White ... should also be considered as a color,'' generic paper-color guidance, not a school color) to the missing third true school color, Light Green.'
    ),
    (
      'virginia-military-institute',
      '234085',
      array['#AE122A','#FFD619','#FFFFFF']::text[],
      'https://www.vmi.edu/media/content-assets/documents/communications-and-marketing/VMI-Brand-Guide.pdf',
      'high',
      'Candidate''s specific dead URL (VMIIdentityStandards2017.pdf, 404) replaced with VMI''s current live Brand Guide PDF found via search on vmi.edu. "Primary Colors: VMI Red, VMI Yellow, and White" and "PRIMARY COLOR PALETTE / HEX: AE122A / HEX: FFD619 / HEX: FFFFFF" — confirms candidate''s 3-of-3 exactly (a 4th color, Black #000000, also appears in the same palette table but is not named among the three prose-stated ''Primary Colors,'' so not added).'
    ),
    (
      'ohio-wesleyan-university',
      '204909',
      array['#A51C33','#111C24']::text[],
      'https://www.owu.edu/about/offices-services-directory/university-communications/web-services/website-style-guide-best-practices/colors-and-fonts/',
      'medium',
      'Candidate''s citation is live but the page is a web-content-editor''s "Colors and Fonts" design-system reference (Website Style Guide & Best Practices), not a formal institutional brand book, and lists a "Primary Colors" table with 8 swatches (Black #111c24, Dark Gray, four distinct reds — Red 1 #A51C33, Red 2 #7B1426, Red 3 #651525, Bright Red #D32D27 — and 3 grays), none of which matches candidate''s guessed #C51230 exactly. No single color is singled out in prose as ''the'' official red among the four; used the first-listed red (Red 1) and the first-listed dark (Black) as the closest reading of a primary pair, medium confidence given the ambiguity among reds. Candidate''s white was not present anywhere in the table, so dropped.'
    ),
    (
      'pacific-university',
      '209612',
      array['#B51217','#000000','#696969']::text[],
      'https://www.pacificu.edu/about/pacific-directory/offices-departments/university-advancement/marketing-communications/pacific-university-brand/colors',
      'high',
      'Candidate''s live URL 404s; recovered the identical page via Wayback. "The primary colors for Pacific University are red, black and grey ... Boxer Red HEX #B51217 / Boxer Black HEX #000000 / Boxer Grey HEX #696969 / Boxer White HEX #FFFFFF" — White is explicitly described as an add-on (''The primary colors, plus white, should be used for apparel and gear''), not one of the three named primary colors. Corrected candidate''s white to the real third primary color, Grey.'
    ),
    (
      'oklahoma-city-university',
      '207458',
      array['#004B87','#FFFFFF','#000000']::text[],
      'https://www.okcu.edu/admin/communications/internal/colors',
      'high',
      'Candidate''s live URL 404s (site redesigned); recovered the identical page via Wayback (2021 capture). "PRIMARY COLOR - PMS 301 C ... Hex Code: 004B87 / PRIMARY COLOR - BLACK ... Hex Code: 000000 / PRIMARY COLOR - WHITE ... Hex Code: FFFFFF" — all three explicitly labeled PRIMARY COLOR, confirming candidate''s 3-of-3 exactly.'
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
