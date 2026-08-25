-- Batch 28 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given (only trimmed to the 3-hex cap or
-- kept as literally stated): kentucky-wesleyan-college (Official Color
-- Palette lists 4 colors -- purple/white/medium gray/light gray -- kept
-- candidate's purple+white+medium gray, dropped the document's 4th color to
-- stay within the cap), monmouth-college (RGB stated in the page's own
-- quick-facts prose converts exactly to candidate's red, white named
-- alongside it), centenary-college-of-louisiana (on-domain CSS custom
-- properties --bs-primary/--bs-secondary/--bs-tertiary match candidate's
-- three hexes exactly, after the candidate's issuu.com citation and the
-- college's own manual-download link both proved dead).
--
-- Corrected (candidate hex, color set, or source did not match the
-- school's own current official source): newman-university (image-based
-- PDF rendered to pages and read directly; official 3-color athletics
-- palette is Navy/Red/Light Blue with no white at all -- dropped
-- candidate's fabricated white, added the missing Light Blue),
-- university-of-saint-joseph (page's own prose frames white/black as mere
-- accents to the two "most prominent" colors Navy+Yellow -- dropped
-- white), westminster-university (site only names "Colors: Purple"; both
-- hexes corrected via the athletics site's own site_colors JSON), gallaudet-
-- university (candidate's second blue was actually the document's
-- Secondary-palette "Darker Blue", not part of the primary buff/blue pair --
-- corrected to the primary pair), malone-university (malone.edu's own PDF
-- and style-guide page are both dead; recovered the identical document
-- mirrored on the college's print vendor's domain; red and blue corrected,
-- white confirmed as the document's explicit third official color), thiel-
-- college (Web Equivalent table hex corrected for both colors; dropped
-- candidate's white, absent from the document entirely), tusculum-
-- university (logos page states no hex; its embedded Adobe-InDesign brand-
-- guide publication required a real browser to page through -- found
-- Primary Colors Orange [hex computed from stated RGB] and Black [hex
-- explicitly printed]; dropped candidate's white, only a logo-reversal
-- option, not a listed color), keystone-college (Primary Colors: blue hex
-- printed exactly, orange hex computed from stated RGB since no hex string
-- was printed for it; dropped candidate's white, absent from that
-- section), university-of-the-ozarks (malformed "hhttps://" URL fixed;
-- purple+white confirmed as the document's own PRIMARY row exactly;
-- dropped candidate's gray, explicitly SECONDARY on the same document),
-- erskine-college (candidate paired a primary color with a secondary one;
-- corrected to the document's actual two PRIMARY COLORS, black+garnet;
-- dropped candidate's white, absent from the document), whittier-college
-- (both hexes corrected via the page's own stated "School Colors" hex
-- codes; dropped candidate's white, not one of the two named colors),
-- ohio-dominican-university (black+gold confirmed via the page's own
-- Primary/University Colors hex; dropped candidate's white, which the page
-- names in heritage prose but never gives a hex or RGB for anywhere),
-- young-harris-college (both hexes corrected via the athletics site's own
-- site_colors JSON; dropped candidate's white), menlo-college (all three
-- known menlo.edu brand-guidelines URLs are dead; re-sourced to the
-- official athletics site's site_colors JSON, which confirms candidate's
-- blue exactly; dropped candidate's white and gray, neither grounded on any
-- reachable domain), la-roche-university (official site states colors by
-- name only, never hex, and laroche.edu's own brand-guidelines page 404s;
-- fell back to a reputable secondary color index for hex, one digit
-- different from candidate's red; dropped candidate's third near-black,
-- not part of the on-domain "Red and White" statement -- low confidence),
-- southern-wesleyan-university (candidate's hex is actually the athletics-
-- only "Warrior Blue"; corrected to the university's own stated primary
-- "University Blue" for this institution-wide record), lane-college
-- (candidate's FactBook PDF citation is dead; found the college's real,
-- current Brand Standards Guide PDF linked from its own marketing page --
-- navy and red both corrected completely, white confirmed as the
-- document's literal third logo color), martin-luther-college (candidate's
-- athletics-site red does not match either the athletics site's own
-- site_colors JSON or a secondary index, and the college's new
-- institutional brand -- launched Nov 2025, explicitly distinct from the
-- unchanged Knights athletic mark -- has no separate color-swatch page;
-- used the hex repeatedly applied on the official brand-launch page itself
-- as its own accent color; dropped candidate's black/white as ungrounded
-- for the new brand), massachusetts-college-of-liberal-arts (candidate's
-- citation 404s; found MCLA's actual Color Palette PDF, whose three
-- co-equal Primary colors replace candidate's entirely unmatched guesses),
-- north-central-university (both hexes corrected via the athletics site's
-- own site_colors JSON; dropped candidate's white), notre-dame-of-maryland-
-- university (candidate's malformed citation URL 404s; corrected to the
-- site's homepage, whose sitewide site_colors JSON gives two blues that do
-- not match candidate's blue+green at all -- candidate's green appears to
-- be an unrelated wrong pull; dropped candidate's white), elmira-college
-- (candidate's citation and both known official style-guide PDFs are all
-- dead; college's main site confirms "Purple and Gold" in prose with no
-- hex; fell back to the athletics subdomain's site_colors JSON, whose 2019
-- rebrand article confirms it stayed "true to the Purple and Gold" --
-- candidate's three-hex guess was entirely unmatched and replaced),
-- warren-wilson-college (candidate's citation domain warnerroyals.com is
-- confirmed via og:site_name to be Warner University, not Warren Wilson --
-- exactly the flagged wrong-school trap; re-sourced to the real
-- warrenwilsonowls.com, whose site_colors JSON happens to match candidate's
-- blue and green exactly; dropped candidate's white), ripon-college (page's
-- own two-color "School colors: Red and White" prose is authoritative over
-- candidate's three; red corrected via site_colors JSON, black dropped),
-- ursuline-college (candidate's blue does not match the athletics site's
-- own site_colors JSON at all; corrected, gold confirmed exact, white
-- dropped), earlham-college (candidate's citation PDF is dead; found the
-- college's current Visual Guidelines PDF, whose three co-equal PRIMARY
-- PALETTE colors replace candidate's red+white -- red corrected, maroon and
-- navy added, white dropped as not part of the Primary Palette), william-
-- peace-university (page's own "Official Brand Colors" list gives directly
-- printed hex for green, white, and black -- all three corrected to the
-- document's exact values, including a near-white rather than pure
-- #FFFFFF).
--
-- See data/brand-colors/batch-28-2026-08-24.jsonl for the full per-school
-- record. No rows were left null in this batch -- every school had a
-- usable source once dead/wrong-school citations were worked around; one
-- row (la-roche-university) landed at low confidence for lack of any
-- official on-domain hex.

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
      'newman-university',
      '155335',
      array['#051C48', '#B32D33', '#7BAFD4']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/newmanjets.com/documents/2022/6/9/NU_Athletics_Brand_Guide_2021.pdf',
      'high',
      'Candidate PDF confirmed live but has no extractable text layer (image-based); rendered pages to images and read directly. Page 8 ''NU Athletics Color Palette'' lists exactly three swatches with stated hex: Newman Navy #051C48, Newman Red #B32D33, Newman Light Blue #7BAFD4 -- no white anywhere in the palette (candidate''s white was fabricated/not on the page). Corrected: dropped candidate''s white, added the document''s actual third color Newman Light Blue.'
    ),
    (
      'kentucky-wesleyan-college',
      '157076',
      array['#392082', '#FFFFFF', '#A7A8AA']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/kwcpanthers.com/documents/2022/2/1/KWC_Athletics_Guidelines.pdf',
      'high',
      'Candidate PDF confirmed live and extracts cleanly. ''Official Color Palette'': Wesleyan Purple PMS Violet C HEX #392082, White HEX #FFFFFF, Medium Gray (Cool Gray 6C) HEX #A7A8AA, Light Gray (Cool Gray 2C) HEX #D0D0CE -- four colors listed with equal weight, no primary/secondary split. Confirmed candidate''s exact 3-of-4 selection (purple, white, medium gray); dropped the document''s fourth color (light gray) to stay within the 3-hex cap.'
    ),
    (
      'university-of-saint-joseph',
      '130314',
      array['#002D62', '#FFD200']::text[],
      'https://www.usj.edu/about/administrative-offices/division-of-enrollment-management/office-of-marketing-and-communications/usj-brand-guidelines/colors-patterns/',
      'high',
      'Candidate''s citation confirmed live. ''Primary Colors ... 1932 Blue (Navy) and Crown Yellow are the two most prominent colors in our brand, and White and Black are to be used as accents when appropriate. 1932 Blue (Navy) and Crown Yellow are the only colors to be used in the USJ logo.'' Navy HEX #002d62, Crown Yellow HEX #ffd200 -- both confirmed exact match to candidate. Dropped candidate''s white: the page''s own prose explicitly frames white/black as accents, not co-equal primaries, and the two-color logo statement singles out navy+yellow only.'
    ),
    (
      'westminster-university',
      '230807',
      array['#46166B', '#947750']::text[],
      'http://westminstergriffins.com/sports/2015/4/16/GEN_0416154901.aspx',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''Westminster University Athletics''). Its own quick-facts prose states ''Colors: Purple'' (singular, no second named color), and its Sidearm site_colors JSON declares primary_background #46166B, secondary_background #947750 (tan/bronze). Corrected candidate''s guessed purple (#380E56, not found on-domain) and tan (#BC9B6B, not found on-domain) to the site''s actual configured values; dropped candidate''s white as not part of the stated palette.'
    ),
    (
      'gallaudet-university',
      '131450',
      array['#00457C', '#E8D4A2']::text[],
      'https://storage.googleapis.com/gal-media/documents/University-Communications/Gallaudet_Visual_Identity_Guide.pdf',
      'high',
      'Candidate PDF confirmed live and extracts cleanly. ''The traditional Gallaudet colors are buff and blue.'' The document''s own ''Two-Colors (RGB value)'' table -- the actual primary pair -- states Blue HEX #00457C and Buff HEX #E8D4A2, both exact matches to two of candidate''s three hexes. Candidate''s third hex (#002A5C, ''Darker Blue'') is listed several rows down under a separate ''Secondary Colors'' table, not the primary two-color pair -- dropped as it is explicitly secondary, not primary.'
    ),
    (
      'malone-university',
      '203775',
      array['#0031AD', '#CC002B', '#FFFFFF']::text[],
      'https://usaqp.com/wp-content/themes/USA%20Quickprint/docs/MU-Visual-Identity-Standards-9-24.pdf',
      'medium',
      'Candidate''s malone.edu PDF is dead (soft-404 CMS error), and malone.edu''s own /style-guide/ page is a hard 404 too. Located the identical, current ''Malone University Visual Identity Standards Fall 2024'' document mirrored on the University''s print vendor''s domain (usaqp.com) -- verified by title and content as Malone''s own authored guide, just off-domain hosting. ''Malone University''s official school colors are red, white, and blue.'' Primary color palette: Pioneer Red PMS 187 HEX #CC002B, White HEX #FFFFFF, Malone Blue PMS 281 HEX #0031AD. Corrected candidate''s red (#C41230) and blue (#003E7E); white confirmed exact. Medium confidence because the verified PDF, while genuinely Malone''s own document, is not hosted on malone.edu itself.'
    ),
    (
      'thiel-college',
      '216357',
      array['#0D204A', '#998643']::text[],
      'https://resources.thiel.edu/news/documents/COMPLETESTYLEGUIDE2012_UPDATED_001.pdf',
      'high',
      'Candidate PDF confirmed live and extracts cleanly. ''The College colors are blue and gold.'' The apparel color table gives Web Equivalent hex: Navy Blue (PMS 2768) #0d204a, Old Gold (PMS 4505) #998643, plus a third Light Blue (PMS 283) #97beff explicitly framed as a secondary/apparel-only accent, not one of the two named college colors. Corrected candidate''s near-match hexes to the document''s exact values; dropped candidate''s white, which does not appear anywhere in this document.'
    ),
    (
      'tusculum-university',
      '221953',
      array['#F26724', '#000000']::text[],
      'https://www3.tusculum.edu/pr/brand-guide/',
      'high',
      'Candidate''s /tusculum-university-logos/ page confirmed live but states no hex at all. That page itself links an embedded Adobe-InDesign-hosted ''Brand Guide'' publication; used a real browser to page through it (curl cannot render the JS viewer) and found its ''COLORS'' page: ''Primary Colors'' -- Orange PMS 165C, CMYK 1-73-98-0, RGB 242-103-36 (hex not printed, computed precisely from the stated RGB triplet: #F26724) and Black (PMS Process Black), HEX explicitly printed as 00-00-00. Corrected candidate''s orange (#FF651C, not on the page); dropped candidate''s white, which appears only as a reversed/knockout logo option in the guide, never as a listed primary color.'
    ),
    (
      'keystone-college',
      '213303',
      array['#001680', '#F79239']::text[],
      'https://www.keystone.edu/wp-content/uploads/2016/11/BRAND-GUIDELINES.pdf',
      'medium',
      'Candidate PDF confirmed live; text-extraction of the swatch page failed (image-based), rendered to images and read directly. ''PRIMARY COLORS'': PMS Reflex Blue, Hex/HTML explicitly printed as 001680; PMS 021 Orange, RGB 247/146/57 stated but no Hex/HTML line printed for it (unlike the Admissions-substitute PMS 138 Orange, which does have a printed hex) -- orange hex computed by exact RGB-to-hex conversion (not a Pantone lookup): #F79239, which happens to match candidate exactly. Blue corrected to the printed hex; dropped candidate''s white, which never appears in the Primary Colors section. Medium confidence since one of the two hexes (orange) was derived from stated RGB rather than a literally printed hex string.'
    ),
    (
      'university-of-the-ozarks',
      '107558',
      array['#4B316B', '#FFFFFF']::text[],
      'https://ozarks.edu/wp-content/uploads/UofOzarks_VENDORGuide_PMS-269C.pdf',
      'high',
      'Stripped the stray ''h'' prefix from the given URL; PDF confirmed live and extracts cleanly. ''COLOR PALETTE'' explicitly splits into a PRIMARY row (Purple PMS 269C HEX #4b316b, White HEX #FFFFFF) and a SECONDARY row (Black HEX #000000, Cool Gray 8 HEX #88898c). Purple and white confirmed exact matches to candidate; dropped candidate''s third hex (#88898C, Cool Gray) since the document explicitly labels it Secondary, not Primary -- the brief''s exception for a stated white-inclusive primary set applies to purple+white only.'
    ),
    (
      'erskine-college',
      '217998',
      array['#6F1931', '#231F20']::text[],
      'https://erskinecollege.wpenginepowered.com/wp-content/uploads/2022/07/ErskineFlyingFleet_BrandGuidelines_2022.pdf',
      'high',
      'Candidate PDF confirmed live and extracts cleanly. ''PRIMARY COLORS'': Black (Pantone Black C) Hex #231F20, Garnet (PMS 195C) Hex #6F1931. ''SECONDARY COLORS'': Gold (PMS 466C) Hex #B8A46A, plus a Gray with no printed hex. Garnet matched candidate exactly; corrected the pairing by swapping candidate''s gold (secondary) for black (the document''s actual second primary color); dropped candidate''s white, which does not appear anywhere in the document.'
    ),
    (
      'whittier-college',
      '125763',
      array['#652D89', '#EDB50F']::text[],
      'https://www.whittier.edu/communications/styleguide',
      'high',
      'Candidate''s citation confirmed live. ''School Colors: Purple (Pantone 526) Hex Code: 652d89 ... Gold (Pantone 7405 uncoated/Pantone 124 coated) Hex Code: edb50f''. Corrected candidate''s purple (#661C78) and gold (#EDB200) to the page''s exact stated hex values; dropped candidate''s white, which is not part of the two named School Colors (only mentioned as an allowed logo-reversal option elsewhere on the page).'
    ),
    (
      'ohio-dominican-university',
      '204617',
      array['#000000', '#FFC72C']::text[],
      'http://www.ohiodominican.edu/future-students/who-we-are/directories/offices/marketing-public-relations/ODUbrand',
      'high',
      'Candidate''s citation confirmed live. Page prose: ''The colors of ODU are white, black and gold'' (heritage description, no hex given for white anywhere on the page). The stated ''Primary Colors'' / ''University Colors'' sections both give explicit hex: Pantone 123 (yellow) HEX FFC72C, Pantone Black HEX 000000 -- exact match to candidate''s black+gold. Dropped candidate''s white since no hex or RGB for white is stated anywhere on the page, only named in general heritage prose.'
    ),
    (
      'young-harris-college',
      '141361',
      array['#330066', '#D1D1D3']::text[],
      'http://yhcathletics.com/sports/2015/7/10/quickfacts.aspx',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''Young Harris College Athletics''). Its own Sidearm site_colors JSON declares primary_background #330066 (purple), secondary_background #D1D1D3 (light silver/gray). Corrected candidate''s guessed purple (#260053, not found on-domain); silver essentially matched candidate''s guess (#C7C6C9 vs. the site''s actual #D1D1D3, corrected to the exact configured value). Dropped candidate''s white.'
    ),
    (
      'menlo-college',
      '118693',
      array['#003A70']::text[],
      'https://menloathletics.com/',
      'medium',
      'Candidate''s menlo.edu color-palette page 404s, and both known menlo.edu/c4.menlo.edu brand-guidelines URLs are dead (confirmed via curl and a real browser -- one hard-404s, the other times out entirely). Re-sourced to the official athletics site menloathletics.com (og:site_name: ''Menlo College''), whose site_colors JSON declares primary_background #003A70 -- exact match to candidate''s blue. Its secondary_background is #F2F2F2, an off-white/near-neutral, not a distinct gray; dropped candidate''s white and gray as ungrounded (no genuine ''Menlo Gray'' hex was found anywhere on-domain).'
    ),
    (
      'la-roche-university',
      '213358',
      array['#EE2E23', '#FFFFFF']::text[],
      'https://teamcolorcodes.com/la-roche-college-redhawks-color-codes/',
      'low',
      'Candidate''s larochesports.com citation confirmed live but states only ''Colors: Red and White'' with no hex anywhere; laroche.edu''s own /brand-guidelines/ page is a 404, and no other official brand page with stated hex was found after search. Fell back to a reputable secondary color index, whose ''Primary Colors'' table lists Red (PMS Bright Red C) #EE2E23, White #FFFFFF, and Black (PMS Black 4C) #251A06. Corrected candidate''s red by one digit (#EE2E24 -> #EE2E23) to match this source; kept white per the athletics page''s own ''Red and White'' prose; dropped the secondary source''s third color (black), which is not mentioned in the on-domain ''Colors: Red and White'' statement. Low confidence: hex sourced entirely from a third-party index, no official on-domain hex exists.'
    ),
    (
      'southern-wesleyan-university',
      '217776',
      array['#21376D']::text[],
      'https://www.swu.edu/marketing-communications/brand-toolkit/color-palette/',
      'high',
      'Candidate''s cited URL redirects to a generic marketing landing page with no color content; found the real current path. ''University Blue is the official university color and should be the primary color in university branded pieces ... Pantone 288 ... Hexcode: #21376D.'' Separately, ''Warrior Blue is the official color for Warrior Athletics ... Pantone 286 ... Hexcode: #0033A0'' -- candidate''s hex (#0033A0) is actually the athletics-only color, not the university''s own primary color. Corrected to University Blue for this institution-wide record; no white or second color is stated as paired with University Blue anywhere on the page, so dropped candidate''s white and the athletics-only blue.'
    ),
    (
      'lane-college',
      '220598',
      array['#003057', '#BA0C2F', '#FFFFFF']::text[],
      'https://s3.us-east-1.amazonaws.com/lanecollegeedu/WA1126-Lane-College-Brand-Standards-Guide.pdf',
      'high',
      'Candidate''s FactBook1415.pdf citation is dead (returns the site''s HTML shell, not a PDF). Found the college''s current, actual Brand Standards Guide linked from lanecollege.edu''s own Communications & Marketing page. ''Lane College uses three colors in its logo: navy blue, cardinal red, and white.'' Core Colors table: Navy Blue (Pantone 540C) HEX #003057, Cardinal Red (Pantone 200C) HEX #BA0C2F; white is the third named logo color (no separate hex table row needed, literal white = #FFFFFF). Corrected candidate''s navy (#000080) and red (#990000) completely; white confirmed.'
    ),
    (
      'martin-luther-college',
      '173452',
      array['#E31937']::text[],
      'https://mlc-wels.edu/brand/',
      'medium',
      'Candidate''s mlcknights.com citation confirmed live but is the Knights ATHLETIC site, whose site_colors JSON gives a different red (#CE1126) than a third-party index''s Knights red (#DE1B22) -- neither matches candidate''s #C8102E, and MLC''s official announcement page states ''The Knights athletic logo will not change at this time'' when the college''s new INSTITUTIONAL brand launched (Nov 2025), i.e. athletics and institutional branding are explicitly two different color sets. No formal color-swatch page with stated hex was found for the new institutional brand, but the official mlc-wels.edu/brand/ launch page itself repeatedly uses #E31937 as its own inline-styled accent color on the brand tagline (''You: Knighted for Ministry''). Used this on-domain, repeatedly-applied color rather than either athletics-site or third-party guess; dropped candidate''s black and white as ungrounded for the new institutional brand.'
    ),
    (
      'massachusetts-college-of-liberal-arts',
      '167288',
      array['#002B49', '#0085CA', '#88DBDF']::text[],
      'https://www.mcla.edu/Assets/MCLA-Files/Administrative-Offices/Marketing-Commun/MCLA%20Typography%20and%20color%20guide.pdf',
      'high',
      'Candidate''s citation page 404s; found MCLA''s actual ''Brand Typography and Color Palette Guidelines'' PDF via the college''s current Brand Guidelines page. ''Color Palette / Primary'': PMS 318C HEX #88DBDF, PMS Process Blue C HEX #0085CA, PMS 7463C HEX #002B49 -- three co-equal Primary colors, none of which match candidate''s guessed hexes at all. Secondary/accent colors (green, yellow-green, gold) are explicitly for ''spirit and athletic materials'' use only, ''sparingly'' -- dropped. Replaced candidate''s entire set with the document''s actual three Primary colors.'
    ),
    (
      'north-central-university',
      '174437',
      array['#003D7D', '#CBB576']::text[],
      'https://ncurams.com/sports/2018/8/29/athletics-history',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''North Central University Athletics''). Its own Sidearm site_colors JSON declares primary_background #003D7D (blue), secondary_background #CBB576 (gold/tan). Corrected candidate''s guessed blue (#002857) and gold (#B4A169) to the site''s actual configured values; dropped candidate''s white.'
    ),
    (
      'notre-dame-of-maryland-university',
      '163578',
      array['#2A6EBB', '#13355B']::text[],
      'https://notredamegators.com/',
      'medium',
      'Candidate''s citation URL has a malformed space-encoded path that 404s; corrected to the site''s homepage (og:site_name: ''Notre Dame of Maryland University Athletics''), whose sitewide Sidearm site_colors JSON declares primary_background #2A6EBB, secondary_background #13355B -- both blues. Candidate''s guessed hex set (#003768 blue + #64C295 green) does not match anything found on this domain at all; the green in particular appears to be a wrong pull with no evidence on the actual site. Replaced with the two verified blues; dropped candidate''s white.'
    ),
    (
      'elmira-college',
      '190983',
      array['#4A2467', '#EEB51D']::text[],
      'https://athletics.elmira.edu/news/2019/7/10/elmira-college-athletics-unveils-new-visual-identity.aspx',
      'medium',
      'Candidate''s elmira.edu/Student/... citation 404s; the college''s main site confirms ''College Colors: Purple and Gold'' in prose but with no hex. Both known official branding-style-guide PDFs (ecbrandingstyleguide2.pdf and the 9/24/25-dated version) are 404. Fell back to athletics.elmira.edu (an official Elmira subdomain), whose sitewide site_colors JSON declares primary_background #4A2467, secondary_background #EEB51D, and whose own 2019 rebrand article states the new athletics mark ''remains true to the Purple and Gold'' of the college. Replaced candidate''s entire three-hex guess (none matched) with these two verified, on-domain, correctly-named colors.'
    ),
    (
      'warren-wilson-college',
      '199865',
      array['#004976', '#006A4E']::text[],
      'https://warrenwilsonowls.com/sports/2023/7/13/information-quick-facts.aspx',
      'medium',
      'Candidate''s citation domain warnerroyals.com is confirmed via og:site_name to be Warner University Athletics -- a completely different school (Royals, not Owls) -- exactly the wrong-school trap flagged for this batch. Re-sourced to the real Warren Wilson College athletics site, warrenwilsonowls.com (og:site_name: ''Warren Wilson College''), whose site_colors JSON declares primary_background #004976 (blue), secondary_background #006A4E (green) -- both values happen to match candidate''s blue and green exactly, suggesting the underlying colors were right even though the citation URL pointed at an unrelated school''s site. Dropped candidate''s white, not evidenced anywhere on the real domain.'
    ),
    (
      'monmouth-college',
      '147341',
      array['#D3282F', '#FFFFFF']::text[],
      'https://monmouthscots.com/sports/2012/5/25/BB_0525123609.aspx',
      'high',
      'Candidate''s citation confirmed live (og:site_name: ''Monmouth College Athletics''). Its own quick-facts prose states ''Nickname/Colors: Fighting Scots/Red (RGB 211-40-47; CMYK 0-97-75-0) and White'' -- RGB 211,40,47 converts exactly to #D3282F, corroborated by the page''s own site_colors JSON (primary_background #D3282F). Confirmed candidate''s exact pair as given; both colors explicitly named in the school''s own quick-facts prose.'
    ),
    (
      'ripon-college',
      '239628',
      array['#BE0D34', '#FFFFFF']::text[],
      'https://riponredhawks.com/sports/2012/7/17/GEN_0717120504.aspx',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''Ripon College Athletics''). Its own quick-facts prose states ''School colors: Red and White'' (only two named colors, no black), and its site_colors JSON declares primary_background #BE0D34, secondary_background #000000. Corrected candidate''s guessed red (#C31D36) to the site''s actual configured value; dropped candidate''s black since the page''s own two-color prose statement names only red and white.'
    ),
    (
      'centenary-college-of-louisiana',
      '158477',
      array['#8A2432', '#FFFFFF', '#000000']::text[],
      'https://gocentenary.com/',
      'medium',
      'Candidate''s issuu.com citation 404s (confirmed dead via both curl and a real browser); centenary.edu''s own Brand & Graphic Standards page describes a manual but provides no working download link. Re-sourced to the official athletics site gocentenary.com (og:site_name: ''Centenary Athletics''), whose on-domain CSS custom properties explicitly declare --bs-primary:#8a2432, --bs-secondary:#000000, --bs-tertiary:#ffffff -- an exact match to candidate''s three hexes. Confirmed candidate''s set exactly as given via this on-domain CSS evidence.'
    ),
    (
      'ursuline-college',
      '206349',
      array['#2E56A5', '#FFDD00']::text[],
      'https://ursulinearrows.com/news/2017/2/8/general-ursuline-athletics-unveils-new-athletic-logo.aspx',
      'medium',
      'Candidate''s citation confirmed live (og:site_name: ''Ursuline College Athletics''); the article itself is narrative only with no hex, but the site''s own site_colors JSON declares primary_background #2E56A5 (blue), secondary_background #FFDD00 (gold). Corrected candidate''s guessed blue (#143173, not found on-domain and not matching this configured value); gold confirmed exact. Dropped candidate''s white.'
    ),
    (
      'earlham-college',
      '150455',
      array['#8B1B3F', '#651C32', '#00263E']::text[],
      'https://earlham.edu/wp-content/uploads/2021/10/EarlhamCollege_VisualGuidelines.pdf',
      'high',
      'Candidate''s styleguide/Earlham_Brand_Guide.pdf citation is dead (404); found the college''s current Visual Guidelines PDF instead. ''PRIMARY PALETTE'': Earlham Red (Pantone 208C) HEX #8b1b3f, Maroon (Pantone 7421C) HEX #651c32, Navy (Pantone 2965C) HEX #00263e -- three co-equal primary colors, none including white. Corrected candidate''s near-match red (#861F41) to the document''s exact value and added the other two stated primary colors; dropped candidate''s white, which is not part of the Primary Palette (a separate Secondary Palette of golds/slates/earth-tones/grays exists and was not used).'
    ),
    (
      'william-peace-university',
      '199272',
      array['#006341', '#FBFCFC', '#231F20']::text[],
      'https://gopeacepacers.com/sports/2015/7/10/Sports%20Information.aspx',
      'high',
      'Candidate''s citation confirmed live (og:site_name: ''William Peace University Athletics''; corrected a space-encoding issue in the URL). The page''s own text explicitly lists ''Official Brand Colors: Peace Green #006341, Black #231F20, Black 90% #414042, Black 60% #85888A, White #FBFCFC'', and separately states ''School Colors: Peace Green, White & Black'' -- three named school colors with directly-printed hex for each. Corrected candidate''s green (#006944), white (#FFFFFF -> the document''s actual near-white #FBFCFC), and near-black (#181617 -> the document''s actual #231F20).'
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
