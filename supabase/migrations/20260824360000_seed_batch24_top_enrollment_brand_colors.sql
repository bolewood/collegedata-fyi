-- Batch 24 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a dropped
-- mechanically-attached white/neutral: ursinus-college (Red/Old Gold exact
-- match on the school's own Visual Identity Style Guide PDF, candidate's
-- white corrected to the true third primary color, black), kings-college
-- (Red/Gold exact match on King's Athletics style guide, recovered via
-- Wayback, black dropped -- explicitly secondary/neutral not one of the
-- "two institutional colors"), luther-college (Blue/White/Black exact
-- 3-of-3 match on the current Logo Style Guide, recovered via Wayback),
-- chicago-state-university (Green/Black/White exact 3-of-3 match on the
-- school's own Brand Style Guide PDF, recovered via Wayback), college-of-
-- saint-benedict (Red exact match under the page's own "Primary Colors"
-- heading, white dropped -- not present in that section), drury-university
-- (Scarlet/Gray exact match via directly-stated RGB, not a Pantone guess;
-- white dropped -- prose limits primary colors to exactly two).
--
-- Corrected (candidate hex, color set, or source did not match the
-- school's own current official source): west-liberty-university (gold
-- corrected FFCD33->FFCE34, white kept -- explicitly one of the two
-- allowed PRIMARY pairings per the school's own og:description),
-- northwestern-oklahoma-state-university (red corrected to the school's
-- own stated web hex #d61832, white dropped), belhaven-university
-- (candidate's guessed purple/gold were both wrong; real "Color Usage"
-- swatches are Belhaven Green #144835 and Belhaven Gold #F2A900),
-- letourneau-university (navy corrected via Sidearm site-config JSON),
-- saint-marys-college (blue corrected via the domain's own favicon/
-- meta-tag color, matching the quick-facts prose "Colors: Blue and
-- White"), henderson-state-university (white dropped -- the page's own
-- "our main colors" are Red and Black only, not three), southern-
-- nazarene-university (crimson corrected 891717->841617 against the
-- school's current official color-usage page, ranked primary+secondary
-- tier kept, tertiary gold and white dropped), university-of-
-- northwestern-st-paul (both hexes corrected via Sidearm site-config
-- JSON), southwestern-university (gold corrected FFCC33->FFCD00 against
-- the school's current live Color Palette page), centre-college (gold
-- corrected FFCC00->FFCD00 against the school's current Brand Standards
-- PDF, white and black kept -- both explicitly under "Primary Colors"),
-- lawrence-university (white swapped for the true third primary color,
-- gray, per the document's own "primary colors (black, blue and gray)"
-- prose), sul-ross-state-university (both red and gray corrected against
-- the university's actual current Brand Style Guide PDF -- candidate's
-- specific cited chapter PDF only ever stated Pantone numbers, no hex),
-- lincoln-university-mo (re-sourced to the current 2021 Brand Guidebook
-- after the candidate's 2016 document proved Pantone-only; gray kept,
-- white dropped as unconfirmed on the new palette), carson-newman-
-- university (orange corrected FF671F->F9671F via the site's own named
-- WordPress theme-color custom properties, white dropped), millikin-
-- university (both candidate hexes wrong; real value is Millikin Blue
-- #003255 via Sidearm site-config JSON, kept alone -- paired value is a
-- near-white neutral), muskingum-university (genuine wrong-swatch
-- correction -- candidate's red BF2037 is actually the Athletics Logo's
-- limited-use color per the school's own site; the true primary pair,
-- stated on the University's real Color Palette page, is Muskingum
-- Magenta #DB0B5B and black), manhattanville-college (red corrected
-- A60438->A6093D against the official Brand Identity Standards PDF,
-- read via page-render to resolve a garbled table; white dropped --
-- not part of the Primary Colors block), newberry-university (candidate
-- guesses both replaced with the site's actual Sidearm site-config
-- red/gray, medium confidence), methodist-university (green confirmed
-- via an on-page inline-styled banner; gold left unconfirmed -- not
-- found anywhere on domain, single ink only, medium confidence).
--
-- Left null (no usable on-domain hex/RGB found, only bare Pantone
-- numbers or bare color names with no number at all -- see brief's
-- Pantone-only-is-not-medium rule): nebraska-wesleyan-university
-- (official page names "black and gold" in prose but states no number
-- anywhere on domain), university-of-dubuque (official PDF states only
-- "Pantone 287, 288, and 289" with no hex/RGB/CMYK), mississippi-valley-
-- state-university (current on-domain style guide states only Pantone
-- 349c/186c/124c, no hex), massachusetts-maritime-academy (branding
-- microsite names "Navy & Gold" but hex/RGB values live only inside
-- downloadable asset files, never in page text).
--
-- See data/brand-colors/batch-24-2026-08-24.jsonl for the full per-school
-- record, including all four null entries.

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
      'west-liberty-university',
      '237932',
      array['#000000', '#FFCE34', '#FFFFFF']::text[],
      'https://westliberty.edu/brand/colors/',
      'high',
      'Candidate''s live URL 403s; recovered via Wayback (2026-05-29 capture). Page''s og:description states outright: ''PRIMARY COLORS Primary Colors: Black and Gold, OR Gold and White Secondary Colors: Gray, Blue and Orange.'' Body swatches give WLU Black HEX #000000, WLU Gold (Pantone 123 C) HEX #ffce34, WLU White HEX #ffffff -- all three explicitly labeled among the two allowed PRIMARY pairings, so white is kept per the 2-3-labeled-primary carve-out. Corrected candidate''s gold guess (#FFCD33) to the page''s exact stated #FFCE34.'
    ),
    (
      'northwestern-oklahoma-state-university',
      '207306',
      array['#D61832', '#000000']::text[],
      'https://www.nwosu.edu/university-relations/publication-guidelines-and-logo-standards/',
      'high',
      'Candidate''s riderangersride.com PDF citation resolves (live and via every Wayback capture, 2022-2025) to the athletics site''s generic HTML shell, never real PDF content -- dead link with no working archive. Found NWOSU''s own Publication Guidelines page instead: ''Northwestern''s school colors are Red and Black... Red color for web: #d61832.'' Black given as standard process black. Corrected candidate''s red (#CC092F, a guess) to the school''s own stated #d61832; dropped candidate''s white -- prose names exactly two colors, Red and Black.'
    ),
    (
      'ursinus-college',
      '216524',
      array['#98012E', '#FCB034', '#000000']::text[],
      'https://www.ursinus.edu/live/files/591-visual-identity-style-guide',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly (pdftotext). ''Ursinus College Primary color palette'' table states RED PMS 202C WEB #98012e, [Old Gold] PMS 137C WEB #fcb034, PMS Black WEB #000000 -- ''All three colors should be represented together as often as possible,'' with red and old gold called the dominant pair and black following closely. Corrected candidate''s white to the actual third primary color, black; gold hex matches candidate exactly.'
    ),
    (
      'kings-college',
      '213321',
      array['#CC0033', '#FFCD00']::text[],
      'https://www.kings.edu/non_cms/pdf/graphic-standards.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback (2019 capture). Athletics color section states: ''The King''''s Athletics color palette consists of two institutional colors, two secondary accent colors, and black and white.'' Swatches give PMS 186.5C HEX CC0033 and PMS 116C/128U HEX FFCD00 as the two institutional colors; PMS 118C/117U (dark gold), PMS Cool Gray, and PANTONE Black 6C are the secondary/accent/neutral set. Confirmed candidate''s red and gold exactly; dropped candidate''s black -- prose explicitly separates the two institutional (primary) colors from the secondary accents and black/white.'
    ),
    (
      'newberry-college',
      '218414',
      array['#C8102E', '#888888']::text[],
      'https://newberrywolves.com/',
      'medium',
      'Candidate''s specific Nickname-History citation 404s live with no Wayback capture. Newberrywolves.com''s homepage carries an embedded Sidearm site-config JSON: window.site_colors = {"primary_background":"#C8102E",...,"secondary_background":"#888888",...} -- on-domain CSS/site-config JSON (medium confidence, no formal brand PDF found), consistent with Newberry''s commonly cited ''Scarlet and Gray'' colors. Corrected candidate''s red (#CE0E2D, a guess) and gray (#898A8D, a guess) to the site''s actual configured values; dropped candidate''s white.'
    ),
    (
      'belhaven-university',
      '175421',
      array['#144835', '#F2A900']::text[],
      'https://www.belhaven.edu/about/contact/logos-branding.html',
      'high',
      'Candidate''s citation confirmed live and text-extracted directly. Page''s ''Color Usage'' section (following a 2026 brand refresh) lists four swatches: Belhaven Green #144835 (PMS 3435c), Belhaven Gold #F2A900 (PMS 130c), Blazer Grass #4C8D2E (PMS 363c), and Slate #414142 (90% Black). Candidate''s original hexes (#1D3C34/#FFD100, apparent Wikipedia guesses) do not match any of the four real swatches at all. Kept the two school-name-prefixed flagship colors (Belhaven Green, Belhaven Gold); dropped the mascot-accent Blazer Grass and the near-black Slate tint, neither of which carries the ''Belhaven'' name the way the primary pair does.'
    ),
    (
      'letourneau-university',
      '226231',
      array['#F8B435', '#004B8D']::text[],
      'https://letuathletics.com/',
      'medium',
      'Candidate''s citation is a bare athletics homepage with no brand-page content; recovered via Wayback. Its embedded Sidearm site-config JSON: window.site_colors = {"safe_text_white":"#004B8D",...,"primary_background":"#F8B435",...,"secondary_background":"#004B8D",...} -- on-domain CSS/site-config JSON, medium confidence, no formal brand PDF found. Candidate''s gold (#F8B435) matches exactly; corrected candidate''s navy (#001E69, a guess) to the site''s actual #004B8D. Dropped candidate''s white.'
    ),
    (
      'saint-marys-college',
      '152390',
      array['#3D82C4', '#FFFFFF']::text[],
      'https://belles.saintmarys.edu/information/quick-facts',
      'medium',
      'Candidate''s citation confirmed live (via Wayback capture, page still renders). Page''s own Quick Facts state ''Colors: Blue and White'' -- exactly two named colors, so white is kept per the 2-labeled-primary carve-out. No hex appears in the quick-facts prose itself, but the same domain''s favicon/msapplication-TileColor meta tags give the site''s configured blue as #3d82c4 (on-domain CSS/meta, medium confidence; no formal brand PDF found for the college, which is small and athletics-site-branded).'
    ),
    (
      'henderson-state-university',
      '107071',
      array['#A91D36', '#000000']::text[],
      'http://hsu.today/visual-identity-and-style-guide/color/',
      'high',
      'Candidate''s citation confirmed via Wayback (live domain now redirects elsewhere). Page states: ''Our main colors, which are preferred for use within our master logo, are PMS (Pantone Matching System) 201 Coated and Black.'' Swatches: Reddie Red WEB #a91d36, Black WEB #000000. Blue (PMS 7470, #00586f) and three grays are explicitly grouped under a separate ''Accent color palette'' / secondary heading, not the main/core colors. Confirmed candidate''s red exactly; dropped candidate''s white -- not present anywhere on the page, and the prose names only Red and Black as the ''main colors.'''
    ),
    (
      'southern-nazarene-university',
      '206862',
      array['#841617', '#000000']::text[],
      'https://creative.snu.edu/correct-color-usage',
      'high',
      'Candidate''s snu.edu PDF citation 404s live with no Wayback capture of real PDF content. Found SNU''s current official ''Correct Color Usage'' brand page instead: ''Southern Nazarene University''''s primary institutional color is SNU Crimson. Other color options include White, Black (secondary) and Gold (tertiary).'' Swatches: SNU Crimson HEX #841617 (primary), Black HEX #000000 (secondary), Gold HEX #B87415 (tertiary), Gray HEX #999999 (unranked cool gray, not one of the four named colors). Corrected candidate''s crimson guess (#891717) to the stated #841617; kept the top two ranked tiers (primary + secondary); dropped candidate''s white and the tertiary gold to stay within the school''s own explicit primary/secondary ranking.'
    ),
    (
      'nebraska-wesleyan-university',
      '181446',
      null::text[],
      null,
      null,
      'Candidate''s citation confirmed live: ''NWU trademarked logos and brand standards'' page explicitly says the university''s colors are ''black and gold'' (''Contrast NWU''''s black and gold with bright colors''; logos should appear ''in black and gold, black only or white only'') -- but no hex, RGB, PMS number, or CSS custom property appears anywhere on the page or elsewhere on nebrwesleyan.edu that was found. NWU also announced a brand refresh in Feb 2026 (nwusports.com) with no linked hex-bearing document located. Third-party team-color sites list hex guesses but per source-priority rules those don''t clear medium/high without an on-domain number. Left null rather than convert a third-party guess or invent a value; the school''s own color *names* (black, gold) are on record but no number is.'
    ),
    (
      'wartburg-college',
      '154527',
      array['#F58025', '#000000']::text[],
      'https://vip.wartburg.edu/docs/brandguidelines.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback. Page 22, ''Primary Colors'' heading: ''Everyone knows that Wartburg is synonymous with "Be Orange"... Our Wartburg orange is a distinctive color.'' Swatches directly beneath: PMS 158 HEX #f58025 (R245 G128 B37), and a second swatch ''No PMS HEX #000000'' (R0 G0 B0). A separate, explicitly labeled ''Formal/Informal supplemental colors'' grid lower on the same page is a distinct secondary palette. Confirmed candidate''s orange exactly; dropped candidate''s white -- not part of the Primary Colors section.'
    ),
    (
      'methodist-university',
      '198969',
      array['#00573C']::text[],
      'https://mumonarchs.com/sports/2014/10/8/Quick%20Facts',
      'medium',
      'Candidate''s citation confirmed live; page''s Quick Facts prose states ''Colors: Green and Gold'' but gives no hex in the prose itself. The same page''s own quick-facts table uses an inline-styled banner (background-color:#00573c) repeatedly for its Methodist Monarchs headers -- on-domain, page-stated hex for the green, medium confidence (source-priority #3: names colors + hex found elsewhere on same page). No gold hex could be found anywhere on mumonarchs.com or methodist.edu (the SVG orange seen site-wide is Sidearm Sports'' own vendor-logo color, not Methodist''s -- confirmed identical on several unrelated schools'' Sidearm sites, so excluded as a false match). Dropped candidate''s white; left gold unconfirmed rather than guess.'
    ),
    (
      'university-of-northwestern-st-paul',
      '174491',
      array['#2E1A47', '#EAAA00']::text[],
      'https://unweagles.com/sports/2013/3/14/gen_0314134051.aspx',
      'medium',
      'Candidate''s citation confirmed live. Page''s embedded Sidearm site-config JSON: window.site_colors = {"primary_background":"#2e1a47","primary_text":"#eaaa00","secondary_background":"#eaaa00","secondary_text":"#2e1a47"} and meta theme-color #2e1a47 -- on-domain CSS/site-config JSON, medium confidence, no formal brand PDF found. Corrected candidate''s purple (#3D1A54, a guess) and gold (#E0AD12, a guess) to the site''s actual configured values; dropped candidate''s white.'
    ),
    (
      'university-of-dubuque',
      '153278',
      null::text[],
      null,
      null,
      'Candidate''s citation confirmed live and text-extracted directly. ''Primary Color Palette'' section: ''The primary color palette for the University falls within a range of three PMS colors, Pantone 287, 288, and 289 -- depending on the application'' -- Pantone numbers only, no hex, RGB, or CMYK anywhere in the document or found elsewhere on dbq.edu. Per the brief''s constraint that Pantone-only with no domain hex is not medium (and third-party Pantone-to-hex conversion is low/not preferred), left null rather than guess at which of 287/288/289 is primary or convert via a lookup table.'
    ),
    (
      'southwestern-university',
      '228343',
      array['#000000', '#FFCD00', '#FFFFFF']::text[],
      'https://www.southwestern.edu/marketing-and-communications/style-guide/color-palette/',
      'high',
      'Candidate''s live URL 404s (site restructured); found the university''s current live Color Palette page instead. Page states: ''The Southwestern University color system is comprised of four colors: black, yellow, gray and brilliant white. Black is used for most type, and yellow is used purposely as an accent... White is the main background color.'' Page''s own hex swatches: black #000000, yellow #FFCD00, gray #828282, white #FFFFFF. Corrected candidate''s yellow guess (#FFCC33) to the stated #FFCD00; kept black/gold/white (the two most functionally prominent per the page''s own description, plus white as one of only four named system colors) and dropped the least-emphasized gray, used only ''on occasion.'''
    ),
    (
      'mississippi-valley-state-university',
      '176044',
      null::text[],
      null,
      null,
      'Candidate''s specific spotedit-attachment PDF citation 404s live with no Wayback capture. Found MVSU''s current on-domain style guide (mvsu.edu/sites/default/files/mvsu_styleguide.pdf) instead and text-extracted it directly -- its ''MVSU Colors'' section gives only ''Pantone 349c, Pantone 186c, Pantone 124c'' (green/red/gold), Pantone numbers with no hex, RGB, or CMYK anywhere in the document, and none found elsewhere on mvsu.edu. Per the brief''s constraint that Pantone-only with no domain hex is not medium, left null rather than convert via a third-party lookup table.'
    ),
    (
      'centre-college',
      '156408',
      array['#FFCD00', '#FFFFFF', '#000000']::text[],
      'https://www.centre.edu/documents/brand-standards',
      'high',
      'Candidate''s live URL 404s (page restructured, no brand color content); found Centre''s current live Brand Standards PDF (Aug 2022) instead and text-extracted it directly. ''PRIMARY COLORS / The official College colors are'' Centre Gold and white, with black used heavily for contrast/legibility. Swatches: CENTRE GOLD HEX #FFCD00 (PMS 116C), White HEX #FFFFFF, Black HEX #000000 -- all three under the ''Primary Colors'' heading. Corrected candidate''s gold guess (#FFCC00) to the stated #FFCD00; kept all three per the school''s own primary-colors section (white explicitly one of only three).'
    ),
    (
      'lawrence-university',
      '239017',
      array['#003D6A', '#231F20', '#97999C']::text[],
      'https://www2.lawrence.edu/dept/communications/identity/Lawrence-University-Graphics-Standards-2015.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback. ''Primary Colors / Lawrence colors are as unique and distinctive as the logo. Therefore, consistent use of Lawrence''''s official, primary colors (black, blue and gray) is required in all communications... No variation is acceptable for use with the Lawrence logo except black and white.'' Color Palette table gives WEB values for these three named primary colors: Black #231F20, 40% Black (gray) #97999C, PMS 301 (blue) #003D6A; the remaining 9 swatches in the table are explicitly the separate ''Secondary colors'' set. Corrected candidate''s white (not one of the three named primary colors -- white is only mentioned as an acceptable *logo reversal*, not a school color) to the true third primary, gray.'
    ),
    (
      'sul-ross-state-university',
      '228501',
      array['#C8102E', '#75787B']::text[],
      'https://srinfo.sulross.edu/branding/wp-content/uploads/sites/18/brand_style_guide.pdf',
      'high',
      'Candidate''s specific chapter_2.19 PDF (both live and via Wayback) only states Pantone numbers (186C/423C) with no hex -- not usable at medium/high per the Pantone-only rule. Found Sul Ross''s actual current Brand Style Guide PDF on srinfo.sulross.edu instead and text-extracted it directly: ''Sul Ross State University Color Palette / Primary Colors'' gives PMS 186C Hex: C8102E and Cool Gray 9 Hex: 75787B. A separate ''Primary Support Colors'' group lower on the same page (Black #000000, White #FFFFFF, Cool Gray 7 #97999B) is explicitly a distinct, non-''Primary Colors'' tier, as is a further ''Accent Colors'' group (teal, sage, navy, dark green, dark red, gold). Corrected candidate''s red guess (#C70032) to the stated #C8102E and gray guess (#7D8888) to the stated #75787B; dropped candidate''s white -- it''s in the support tier, not Primary Colors.'
    ),
    (
      'massachusetts-maritime-academy',
      '166692',
      null::text[],
      null,
      null,
      'Candidate''s citation URL live but redirects into the branding microsite''s ''Maritime M'' logo subpage rather than a colors table (site is JS-rendered; fetched raw HTML and also WebFetched the live page). Text states ''The primary appearance of the "M" is in Navy & Gold'' and offers CMYK/RGB download links for Navy/Black/Gold/White logo variants, but no numeric hex or RGB value is present anywhere in the page''s text content -- values are only inside downloadable asset files, not stated on the page. Checked sibling branding pages (Logos, Icons, Athletics) via search; none surfaced a hex-bearing color-swatch page. Left null rather than guess at which shade of ''Navy'' or ''Gold'' the academy uses.'
    ),
    (
      'lincoln-university-mo',
      '177940',
      array['#102548', '#898B8E']::text[],
      'https://www.lincolnu.edu/about-lincoln/university-relations/lu_brandguidebook_fall21_final.pdf',
      'high',
      'Candidate''s document_library citation (2016 chapter PDF, both live and via Wayback) states only Pantone numbers (289/Cool Grey 8C/877C) with no hex -- not usable at medium/high. Found Lincoln''s current Fall 2021 Brand Guidebook on lincolnu.edu instead and text-extracted it directly: ''Primary Color Palette'' table gives PMS 289C HEX #102548, PMS 647C HEX #2E598C, PMS P115-9C HEX #E7F4FD, PMS Cool Gray 8C HEX #898B8E. The older 2016 document''s own prose calls the official colors ''Navy Blue and White, with grey as an accent''; no true white appears in the new table (only a very pale near-white blue tint), so kept the dominant Navy and the named accent Gray, both with exact stated hex; omitted the mid-blue and pale-blue-tint table entries and dropped candidate''s white as unconfirmed.'
    ),
    (
      'carson-newman-university',
      '219806',
      array['#F9671F', '#0C2340']::text[],
      'https://www.cn.edu/style-guide/',
      'medium',
      'Candidate''s citation confirmed live via Wayback; the page''s visible text (JS-rendered, not present in static HTML) yielded no prose about colors, but the page''s own WordPress global-styles CSS custom properties are explicitly named (not generic WP defaults): --wp--preset--color--blue: #0C2340 and --wp--preset--color--orange: #F9671F -- on-domain CSS custom properties, medium confidence, matching the precedent for site-configured theme colors. Corrected candidate''s orange guess (#FF671F) to the site''s actual configured #F9671F; confirmed navy exactly; dropped candidate''s white (a generic WP preset, not school-specific).'
    ),
    (
      'chicago-state-university',
      '144005',
      array['#006666', '#000000', '#FFFFFF']::text[],
      'https://www.csu.edu/marketingcommunications/documents/csu_brandstyleguide.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback. ''Primary Color Palette / The primary color palette of Chicago State University is CSU [green]... represented by the Pantone Matching System ink color 342 (PMS 342)... In addition to green, consider black and white key colors in our primary color palette.'' Swatches: RGB 0/102/102 Web #006666, RGB 0/0/0 Web #000000, Web #FFFFFF -- confirms candidate''s 3-of-3 exactly.'
    ),
    (
      'drury-university',
      '177214',
      array['#E31837', '#6A737B']::text[],
      'http://www.drury.edu/uc/logo/athletic-logo.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback. ''Colors / The university''''s primary colors are DU Scarlet (PMS 186) and Gray (PMS 431) and must be a prominent and integral part of any university communications.'' Directly-stated RGB values (not a third-party Pantone conversion): DU Scarlet 227r/24g/55b = #E31837 exactly matching candidate; Gray 106r/115g/123b = #6A737B, also exactly matching candidate''s existing gray. A third swatch, ''Rich Black'' (0/0/0), appears in the same table but is not named among the ''primary colors'' in prose. Dropped candidate''s white -- prose explicitly limits primary colors to exactly two, Scarlet and Gray.'
    ),
    (
      'millikin-university',
      '147244',
      array['#003255']::text[],
      'https://athletics.millikin.edu/',
      'medium',
      'Candidate''s citation confirmed live. Page''s embedded Sidearm site-config JSON and meta theme-color both give window.site_colors = {"primary_background":"#003255","primary_text":"#dedfe0",...} -- on-domain CSS/site-config JSON, medium confidence. Checked millikin.edu directly for a formal brand-guidelines page (branding-licensing-info) -- it lists no hex anywhere (Pantone 2955 only per third-party sources, not found stated on-domain). Kept only the chromatic Millikin Blue #003255; the paired ''primary_text'' #dedfe0 is a near-white neutral, not a second brand color, so dropped it rather than tack it on. Candidate''s original two hexes (#113C61/#FFFFFF) don''t match the site''s actual configured values at all.'
    ),
    (
      'luther-college',
      '153834',
      array['#004C97', '#FFFFFF', '#000000']::text[],
      'https://www2.luther.edu/creative/assets/Luther_logo_guide_2021.pdf',
      'high',
      'Candidate''s live URL timed out; recovered the identical PDF via Wayback. ''Acceptable colors for the logo / Logos may be reproduced in Pantone 2945 (blue), black, or white.'' Swatches: Blue (Pantone 2945) R0 G76 B151 = #004C97, White R255 G255 B255, Black R0 G0 B0 -- confirms candidate''s 3-of-3 exactly.'
    ),
    (
      'muskingum-university',
      '204264',
      array['#DB0B5B', '#000000']::text[],
      'https://www.muskingum.edu/brand/color',
      'high',
      'Candidate''s citation (athletics-logo page) 404s live; that page (recovered separately) actually describes the *Athletics Logo''s* limited-use red (HEX BF2037), not the university''s true primary colors. Found the university''s real Color Palette page instead: ''Muskingum University''''s primary colors are Muskingum Magenta (PMS 2040C) and black... Muskingum Magenta: HEX: DB0B5B.'' This is a genuine wrong-swatch correction -- candidate''s red (BF2037) is actually listed on this same page under ''Extended Palette'' (secondary), not the primary pair. Corrected to the real primary Magenta + Black; dropped candidate''s white.'
    ),
    (
      'college-of-saint-benedict',
      '174747',
      array['#BE0F34', '#000000']::text[],
      'https://www.csbsju.edu/marketing-communications/brand-guide/colors',
      'high',
      'Candidate''s live URL 404s; recovered the identical page via Wayback. ''Primary Colors'' heading with two swatches: CSB/SJU Red Pantone 200, RGB 190/15/52, HEX #be0f34; Black, HEX #000000. A third box labeled ''Rich Black (print)'' gives only a CMYK print build with no RGB/hex, immediately followed by a separate ''Secondary Colors'' heading (Dark Gray, Cool Light Gray, Light Taupe, Dark Teal, Powder Blue, Bright Blue, Brick Rust, Marigold, Dusty Yellow, Ultramarine Green, Spring Green). Confirmed candidate''s red exactly; dropped candidate''s white -- not present in the Primary Colors section at all.'
    ),
    (
      'manhattanville-college',
      '192749',
      array['#A6093D', '#000000']::text[],
      'https://www.mville.edu/sites/default/files/MNV727%20ManhattanvilleCollege_Branding2018_02.pdf',
      'high',
      'Candidate''s live URL 404s; recovered the identical PDF via Wayback and rendered the Color Palette page (p.5/6) as an image to resolve a garbled multi-column table. ''PRIMARY COLORS'' section: Manhattanville Red (Pantone 1945 C) HEX# A6093D; Manhattanville Black, shown as a solid black swatch with CMYK 0/0/0/100 (unambiguous process black, though the document''s own printed RGB triplet next to it appears to be a copy-paste artifact from an adjacent white swatch). Seven further ''Secondary Color Families'' (gold, green, ocean, wedgewood, lilac, slate, earth, each with light/core/dark tints) follow separately. Corrected candidate''s red guess (#A60438) to the stated #A6093D; dropped candidate''s white -- not part of the Primary Colors block.'
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
