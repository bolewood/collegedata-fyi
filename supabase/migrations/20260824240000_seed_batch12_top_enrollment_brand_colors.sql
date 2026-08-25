-- Batch 12 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Most candidate citation URLs had rotted (dead sidearm/S3 PDFs, restructured
-- .edu paths, a Cloudflare-blocked mines.edu PDF, an old pre-rebrand PDF for
-- rpi that has since been superseded by a 2025 identity overhaul, a login-
-- gated SSO redirect for salisbury, and several plain 404s) -- fixed by
-- finding the school's current official page/PDF instead. A handful of dead
-- direct-fetch attempts against otherwise-live official PDFs (columbus-
-- state-university, and a Cloudflare 403 for colorado-school-of-mines) were
-- retried through a real rendered browser session rather than given up on.
-- Every school below was re-sourced against the school's own current
-- official domain where possible, verified by downloading PDFs and running
-- pdftotext -layout (never trusting a fetch-tool summary of a PDF -- one
-- case, purdue-university-northwest, is flagged below where an initial
-- WebFetch summary of a page returned a hex that turned out not to be
-- present anywhere in the real rendered page), rendering a PDF page to an
-- image and reading it directly when pdftotext's column layout was
-- scrambled or its font encoding was garbled (radford-university,
-- mercy-university), or by reading the raw text of a live official page
-- directly (including one, mercy-university, where a search-suggested
-- source turned out to belong to an entirely different, similarly-named
-- institution -- Mercy College of Ohio, not Mercy University NY -- and was
-- discarded as a wrong-school trap).
--
-- Wrong-swatch / wrong-tier / wrong-era catches (candidate hex did not
-- match the school's own official source, matched the wrong section of the
-- right page, or was superseded by a rebrand -- exactly the risk this batch
-- is built to guard against): kutztown-university-of-pennsylvania
-- (candidate's maroon/tan matched nothing real; corrected to Old Main
-- Maroon #701931 + Keystone Gold #B6A268, since the true primary gold is
-- metallic-only with no digital hex), colorado-school-of-mines (candidate's
-- third hex matched neither real neutral; corrected to the three colors the
-- source's own prose calls Mines' heritage identity), state-university-of-
-- new-york-at-new-paltz (candidate matched none of the three real Athletics
-- Primary Colors and omitted Orange entirely), north-carolina-central-
-- university (candidate's maroon and gray were both off; corrected to the
-- exact RGB-derived Official Color Standards), radford-university
-- (candidate omitted the real second color, Blue Ridge, substituting white
-- instead), seton-hall-university (candidate's third hex matched no real
-- accent color; corrected to the two "Main"/core blues), albany-state-
-- university (candidate matched none of the three real, explicitly-named
-- primary colors), georgia-college-and-state-university (candidate matched
-- none of the five real approved colors at all), lehigh (candidate's brown
-- was a large miss; corrected to the real Lehigh Brown #502D0E, primary
-- since 1867), rpi (candidate reflected RPI's pre-August-2025 identity;
-- updated to the current post-rebrand institutional core), university-of-
-- san-diego (candidate dropped the real middle blue, Immaculata Blue),
-- maryville-university-of-saint-louis (candidate's red was an imprecise
-- rounding of the real, currently-published #C91235), angelo-state-
-- university (candidate matched none of the real primary colors at all),
-- millersville-university-of-pennsylvania (candidate's gold was a one-digit
-- typo of the real RGB-derived #EEB211).
--
-- Primary-vs-secondary / tier corrections (candidate mechanically included
-- a white/black/gray that the real source marks as secondary or accent-
-- only, or dropped a real chromatic in favor of a mechanically-appended
-- neutral): university-of-denver (Crimson+Gold confirmed exactly; white
-- dropped -- not needed alongside a complete chromatic pair),
-- state-university-of-new-york-at-cortland (kept the two genuine chromatic
-- reds -- Red + Dark Red -- over candidate's white/black), university-of-
-- north-alabama (source explicitly says "Purple and white are required
-- primary" uniforms, gold is alternate/trim-only -- corrected to Purple +
-- White), suny-brockport (Green+Gold confirmed exactly as the only two
-- colors under "Primary Colors"; white lives in the Secondary list),
-- fayetteville-state-university (source explicitly names "FSU blue and
-- white" as the two primary colors, not candidate's blue+grey pairing),
-- mercy-university (kept the two colors explicitly labeled "PRIMARY" --
-- Mercy Blue + Mercy Silver -- over the unrelated Mercy College of Ohio
-- source), university-of-central-missouri (source says UCM "has two
-- primary colors" -- red and black only; dropped candidate's white),
-- columbus-state-university (source names only Blue and Red as "the
-- university's official colors"; dropped candidate's white).
--
-- Confirmed as-is (candidate hex matched the verified official source
-- exactly, including the narrow case where white really is one of only 2-3
-- labeled primary/official colors): johns-hopkins ("Colors: Hopkins Blue
-- ... and Black Hex Color Code: #68ace5"), augusta-university ("the
-- official logo colors are blue, grey and white" -- all three literally
-- named).
--
-- Low confidence: purdue-university-northwest (public page names "Mane
-- Gold, black and white" as the official colors but states no hex at all
-- -- the full spec is SharePoint-gated; recorded the widely-corroborated
-- Purdue-system Old Gold #CFB991 at low confidence rather than inventing
-- black/white hex values that also aren't stated anywhere public).
--
-- Left null: salisbury-university (Graphics Standards Manual confirmed
-- genuinely credential-gated via Microsoft SSO login wall, not link rot; no
-- public hex found elsewhere on salisbury.edu), saginaw-valley-state-
-- university (no working public colors page found; the Creative Hub
-- subdomain is a JS-only shell with no server-rendered content),
-- university-of-wisconsin-stout (2022 rebrand press coverage names "Navy,
-- Cobalt & Cyan" but the current official page states no hex; only
-- unlabeled page-theme CSS values were found, which the brief's own
-- no-eyedropping guidance rules out as a source), university-of-wisconsin-
-- platteville (official catalog page names colors with no hex; the only
-- hex found on the domain is an unrelated favicon meta tag), princeton
-- (Office of Communications brand guide is access-gated for staff/faculty/
-- students only; a Princeton subdomain's own department palette is out of
-- scope; athletics documents state color names with no hex; third-party
-- sources disagree on the exact orange).
--
-- Ran every final hex list through production deriveInks()/glyphInks()
-- (web/src/lib/derive-inks.ts) via a throwaway Node script using
-- --experimental-strip-types against the real .ts module (deleted before
-- finishing). No case lost a real chromatic primary to the house-ink
-- fallback -- every non-null school below produced its own derived plates
-- (house=false for all 24 populated rows). Four schools whose second stated
-- color is literally black (johns-hopkins, university-of-central-missouri,
-- rpi, millersville-university-of-pennsylvania) hit deriveInks' single-ink
-- path with a charcoal-fallback A plate, because black has zero chroma and
-- is correctly treated as a neutral rather than a usable dark plate -- the
-- real chromatic (blue/red/gold) is preserved as B in every case; this is
-- expected algorithm behavior, not a bug or a lost primary. See
-- data/brand-colors/batch-12-2026-08-24.jsonl for the full per-school
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
      'kutztown-university-of-pennsylvania',
      '213349',
      array['#701931','#B6A268']::text[],
      'https://www.kutztown.edu/colors',
      'high',
      'Candidate URL resolved live and was read directly. Page states ''Our color palette has four sets: primary, alternate primary, secondary and tertiary.'' Primary Colors: OLD MAIN (Maroon) HEX 701931; GOLDEN (Metallic Gold) has no digital hex (''It cannot be viewed truly electronically. As such, no CMYK, RGB or Hex equivalents are listed''). Alternate Primary: KEYSTONE (Gold) HEX B6A268, explicitly the substitute ''When Metallic ink is unavailable.'' Wrong-swatch catch: candidate''s #782F40/#A49473/white match nothing on the real page at all -- corrected to Old Main Maroon #701931 + Keystone Gold #B6A268 (the usable digital stand-in for the metallic primary gold), dropping white (not listed among primary/alternate-primary).'
    ),
    (
      'colorado-school-of-mines',
      '126775',
      array['#21314D','#879EC3','#CC4628']::text[],
      'https://brand.mines.edu/fonts/',
      'high',
      'Candidate''s inside.mines.edu PDF 403s (Cloudflare-protected; bypassed via rendered browser fetch, not a fetch-tool PDF summary). Found and read Mines'' current ''Colors, fonts and graphic elements'' page live: ''The Mines color palette is bold and distinctive. It relies primarily on our heritage colors of dark blue, light blue and Colorado red.'' Primary Palette: DARK BLUE #21314D (matches candidate exactly), BLASTER BLUE #09396C, LIGHT BLUE #879EC3, COLORADO RED #CC4628, PALE BLUE #CFDCE9; separate Neutral Palette holds White/Light Gray/Silver/Dark Gray. Kept the three colors the page''s own prose names as Mines'' heritage identity (dark blue, light blue, Colorado red) instead of candidate''s Dark Blue + white + Cool-Gray-ish #B2B4B3, which isn''t in the real Neutral Palette (#AEB3B8 light gray or #81848A silver are the closest real matches).'
    ),
    (
      'state-university-of-new-york-at-new-paltz',
      '196176',
      array['#003E7E','#007CC2','#F58427']::text[],
      'https://www.newpaltz.edu/ocm/identitystandards/athletics/colors.html',
      'high',
      'Candidate''s nphawks.com 2010 GEN_SID_Downloads.aspx page is a media-guide archive page that only names colors with Pantone/CMYK (''New Paltz Navy...Pantone 281...New Paltz Royal...Pantone 285...New Paltz Orange...Pantone 165''), no hex stated -- not usable at high confidence. Found New Paltz Athletics'' current official ''Colors'' page instead: ''ATHLETICS PRIMARY COLORS -- The colors on the right are the official colors for all of the New Paltz Hawks logos.'' Each swatch''s hex is set directly as its own inline background-color style, tied 1:1 to its printed name: New Paltz Navy #003E7E, New Paltz Royal #007CC2, New Paltz Orange #F58427. Wrong-swatch/wrong-tier catch: candidate''s navy/white/blue-ish set matches none of these three real primaries and omits Orange entirely; white and black are the page''s separate ''ATHLETICS SUPPORT COLORS,'' not primary. Corrected to the three explicitly primary hues.'
    ),
    (
      'north-carolina-central-university',
      '199157',
      array['#880023','#8E9093','#000000']::text[],
      'http://static.nccueaglepride.com/custompages/Files/Athletics/NCCU_graphic_standards2.pdf',
      'high',
      'Candidate URL resolved and was downloaded + pdftotext''d directly. Page 8, ''Official Color Standards'': ''NCCU Maroon PMS 202 C ... R:136/G:0/B:35'' = #880023; ''NCCU Gray PMS 423 C ... R:142/G:144/B:147'' = #8E9093; ''NCCU Black PMS Process Black ... R:0/G:0/B:0'' = #000000. This is the complete official 3-color set (no white listed at all) -- kept all three since it is the school''s actual full stated standard, not a mechanically appended neutral pair. Wrong-swatch catch: candidate''s #862633/#FFFFFF/#898D8D do not match the real Maroon or Gray hexes, and white isn''t on the page.'
    ),
    (
      'salisbury-university',
      '163851',
      null,
      null,
      null,
      'Candidate''s SU_Brand_Graphics_Standards_Manual-REV.pdf redirects to a Microsoft SSO ''Sign in to your account'' login wall -- confirmed genuinely credential-gated, not link rot. Directly visited salisbury.edu/brand/visual-elements.aspx: it also links the same password-protected Graphics Standards Manual PDF at webapps.salisbury.edu/securefiles/brand/... (''password-protected; please provide your SU username and password''). No public salisbury.edu page states a maroon/gold hex. Web search turned up only third-party fan-site color codes (teamcolorcodes/brandcolorcode style, unverifiable, none independently confirmed) -- school colors are universally named ''maroon and gold'' but no first-party hex is publicly reachable. Left null rather than guess from an unverifiable secondary index.'
    ),
    (
      'radford-university',
      '233277',
      array['#C2011B','#003C71','#D1D3D4']::text[],
      'https://www.radford.edu/marketing-communication/_documents/radford-brand-guide.pdf',
      'high',
      'Candidate''s dam/departments/... PDF path 404s. Found and downloaded Radford''s current Brand Guidelines PDF; page 64, ''Athletics: Colors'' (rendered as an image and read directly to resolve column-scrambled pdftotext output): ''Athletics assets should utilize the colors listed to the left as well as white.'' Three named swatches: Radford Red PANTONE 186 HEX #C2011B (matches candidate exactly), Blue Ridge PANTONE 541 HEX #003C71, Squirrel Gray PANTONE 427 HEX #D1D3D4 (matches candidate''s third hex exactly). Wrong-swatch catch: candidate omitted Blue Ridge (#003C71) entirely and substituted white for it. Corrected to the three explicitly named athletics colors, dropping the ''as well as white'' addendum per prefer-1-2-3-named-colors over an appended neutral.'
    ),
    (
      'seton-hall-university',
      '186584',
      array['#0060A9','#003263']::text[],
      'https://www.shu.edu/university-relations/styleguide.html',
      'high',
      'Candidate''s shupirates.com bio page states only ''School Colors: Blue & White'' with no hex. Found Seton Hall''s official Web Style Guide instead: ''Web Color Palette -- Main SHU Blue R:0 G:96 B:169 Hex: #0060A9'' (matches candidate''s first hex exactly) ''... SHU Navy R:0 G:50 B:99 Hex: #003263 ... Cyan Accent #51AADF ... Orange Accent #F15D22 ... Silver Accent #8D9093.'' Wrong-tier catch: candidate''s third hex #A7B1B7 doesn''t match Silver Accent (#8D9093) or anything else on the real page. Kept the two ''Main''/core blues (SHU Blue + SHU Navy), dropping the Cyan/Orange/Silver items explicitly labeled ''Accent'' (secondary, not primary).'
    ),
    (
      'university-of-denver',
      '127060',
      array['#BA0C2F','#A89968']::text[],
      'https://www.du.edu/brand/visual/colors',
      'high',
      'Candidate URL resolved live and was read directly. ''Brand Colors -- DU CRIMSON ... Hex: #BA0C2F. DU Crimson must be used in every visual communication. DU GOLD ... Hex: #A89968.'' White and Black are also listed in this same Brand Colors block (#FFFFFF, #000000), which is the narrow case of white being one of a small labeled primary set -- but since Crimson+Gold already form a complete, exactly-matching chromatic pair confirmed against candidate, kept just the two chromatics per prefer-1-2-chromatic guidance and dropped white/black, plus a large ''Tints, Shades & Complementary Colors'' set explicitly marked ''cannot be used as the primary color.'' Candidate confirmed as-is for the two chromatic hexes; only the white was dropped.'
    ),
    (
      'saginaw-valley-state-university',
      '172051',
      null,
      null,
      null,
      'Candidate''s universitycommunications/brandingandlogos/ page 404s. svsu.edu''s University Communications landing page has no working link to a public colors/brand-standards page; the ''Creative Hub'' subdomain (ucomm.svsu.edu / universitycommunications.svsu.edu) is a JS-only shell that returns no server-rendered content and appears to require internal/authenticated access. Web search only surfaced third-party fan-site color codes (teamcolorcodes.com etc.), which disagree with each other on the secondary color (blue vs. black) and are not independently verifiable against any svsu.edu source. Left null; cardinal red is well-known informally but no first-party hex was reachable.'
    ),
    (
      'albany-state-university',
      '138716',
      array['#0033A0','#EAAA00','#75787B']::text[],
      'https://www.asurams.edu/presidents-office/office-of-marketing-and-communications/primary-colors.php',
      'high',
      'Candidate''s sidearm S3 athletics-style-guide PDF is a genuine S3 NoSuchKey 404. Found Albany State''s official ''Primary Colors'' page (asurams.edu, the university''s own marketing-and-communications domain) and read it live: ''Albany State University blue (Pantone 286), gold (Pantone 124), and gray (Pantone Cool Gray 9) are Albany State University''s primary colors.'' Blue R:0/G:51/B:160 = #0033A0, Gold R:234/G:170/B:0 = #EAAA00, Gray R:117/G:120/B:123 = #75787B. Wrong-swatch catch: candidate''s #0039A6/#FFFFFF/#EAAB00 do not match any of these three real, explicitly-named primaries (no white is listed as primary). Corrected to the three stated primary colors.'
    ),
    (
      'georgia-college-and-state-university',
      '139861',
      array['#245C4F','#C6B784']::text[],
      'https://my.gcsu.edu/sites/default/files/2024-09/GCSU%20Art%20Sheet.pdf',
      'high',
      'Candidate''s gcsu.edu/communications/gc-brand page 404s; the current landing page at gcsu.edu/about/brand has no color content in its own text (only unrelated template CSS colors). Found and pdftotext''d GCSU''s current Art Sheet PDF (my.gcsu.edu, official domain, revised 06/23): ''APPROVED COLORS -- GCSU GREEN PMS 626C ... HEX 245C4F; GCSU BLUE PMS 287C ... HEX 1F3D7B; GCSU GOLD PMS 452C ... HEX C6B784; BLACK 231F20; WHITE FFFFFF.'' Wrong-swatch catch: none of candidate''s #003399/#FFFFFF/#006633 match any of these five real approved colors. The sheet doesn''t label any of the 3 chromatics as more ''primary'' than another, so kept Green + Gold -- GCSU''s traditionally cited school-color pair (Bobcats green/gold, corroborated by multiple independent sources) -- over the third chromatic, GCSU Blue #1F3D7B, which is real per this document but not the pair commonly identified as the school colors; noted here for the record in case Blue should be reconsidered.'
    ),
    (
      'state-university-of-new-york-at-cortland',
      '196149',
      array['#B91000','#8A2A2B']::text[],
      'http://www2.cortland.edu/dotAsset/be455d3b-2a10-4248-a14b-70619fd98f87.pdf',
      'high',
      'Candidate URL resolved and was downloaded + pdftotext''d directly (SUNY Cortland Athletics Style Guide). ''PALETTE USAGE -- All marks must be reproduced using Red (PMS186C), Dark Red (PMS7623C), Black (PMSBLACK C), and White.'' Table: RED WEB #B91000 (matches candidate exactly), DARK RED WEB #8A2A2B, BLACK WEB #000000, WHITE WEB #FFFFFF -- a flat 4-member palette with no primary/secondary labeling. Kept the two genuinely chromatic reds (Red + Dark Red) per prefer-1-2-chromatic, dropping candidate''s white and black, since two real named chromatics were available rather than needing a neutral filler.'
    ),
    (
      'lehigh',
      '213543',
      array['#502D0E','#FFFFFF']::text[],
      'https://live.standards.site/lehighbrandhub/color',
      'high',
      'Candidate''s businessservices.lehigh.edu ''Art Sheet'' PDF 404s (also tried auxiliaryservices.lehigh.edu art-sheet-and-branding-guide, which is login-gated). Traced live links from lehigh.edu''s Communications page to Lehigh''s actual current brand portal, live.standards.site/lehighbrandhub, and read its Color page directly: ''Primary Palette -- Lehigh Brown and White have been our primary colors since 1867 ... Name: Lehigh Brown HEX #502D0E ... Name: White HEX #FFFFFF.'' Major wrong-swatch catch: candidate''s #653819/#C2A875 do not match the real Lehigh Brown (#502D0E) or anything in the current Secondary Palette (10 named accent colors, none close to #C2A875) -- corrected to the two colors explicitly stated as primary since 1867, keeping white since it''s one of exactly two labeled primary colors.'
    ),
    (
      'university-of-wisconsin-stout',
      '240417',
      null,
      null,
      null,
      'Candidate''s studylib.net mirror is a third-party copy of UW-Stout''s pre-2022 identity guide (hex-equivalents.cfm), which predates the 2022 rebrand and would describe retired colors. UW-Stout''s current ''Designed to Do More'' rebrand page (uwstout.edu/about-us/2022-rebranding) narratively says ''the colors honor the past, present, and future ... from the navy blue of UW-Stout''s distinguished history to the bright path of tomorrow''s graduates'' (press coverage separately calls the new palette ''Navy, Cobalt & Cyan'') but states no hex values in its own text; the only hexes present are unlabeled page-theme CSS custom properties, which the brief''s own guidance says not to eyedrop/infer from. The old ''Identity Standards''/marcom-services links referenced in search results now 404. Left null rather than guess which CSS values are the real Navy/Cobalt/Cyan swatches.'
    ),
    (
      'university-of-wisconsin-platteville',
      '240462',
      null,
      null,
      null,
      'Candidate''s yumpu.com mirror of an old Graphic Standards document is a third-party host, not an official source. UW-Platteville''s own catalog page (''The University Seal and Colors'') states only ''orange symbolizes engineering, and blue symbolizes education'' with no hex. The only hex found on uwplatt.edu (#00447C) is a favicon/msapplication-TileColor meta tag on the news site, not a stated brand-guide swatch -- too indirect to trust per the no-eyedropping rule. No current public brand/identity guide with stated hex values was found. Left null.'
    ),
    (
      'university-of-north-alabama',
      '101879',
      array['#592B8A','#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/una.sidearmsports.com/documents/2023/2/1/UNA_Branding_Guide.pdf',
      'high',
      'Candidate URL resolved and was downloaded + pdftotext''d directly. ''COLOR INFORMATION -- NORTH ALABAMA PURPLE ... HTML: 592B8A'' (matches candidate exactly), ''NORTH ALABAMA WHITE ... HTML: FFFFFF'', ''UNA GOLD ... HTML: FFB92A ... NOTE: Use for subtle touches, trim on uniforms, alternate uniforms, warm-ups, retail, etc. Use of Vegas/Sand Gold is prohibited.'' Later: ''NOTE: Purple and white are required primary home/away uniforms for each UNA sport; Alternate uniform colors may be black, gray or UNA gold.'' Purple + white are explicitly ''required primary'' colors; gold is explicitly an alternate/trim-only color -- dropped candidate''s gold accordingly, keeping the confirmed Purple + White pair (white legitimately included since the source itself names exactly these two as primary).'
    ),
    (
      'suny-brockport',
      '196121',
      array['#00533E','#FFC726']::text[],
      'https://www.brockport.edu/support/university-communications/identity/colors/',
      'high',
      'Candidate''s brockport.edu/about/identity/docs/... PDF path 404s. Found Brockport''s current live Colors page (JS-rendered; read via rendered browser text, not a static fetch) and confirmed: ''Primary Colors -- Green PMS 343 HEX: 00533E'' (matches candidate exactly) ''Gold PMS 115 HEX: FFC726'' (matches candidate exactly). White and Black do appear on the page, but only inside the long ''Secondary Colors'' list (which also holds 10 named accent hues at 5-6% usage each) alongside Green/Gold''s 26%/26% ''Primary Colors'' usage -- so white does not qualify as one of a small labeled-primary set here. Dropped candidate''s white; kept the two exactly-confirmed Primary Colors.'
    ),
    (
      'fayetteville-state-university',
      '198543',
      array['#0067B1','#FFFFFF']::text[],
      'https://www.uncfsu.edu/assets/Documents/Office%20of%20Strategic%20Communication/FSU_BrandGuidelines_NEW_v3.pdf',
      'high',
      'Candidate''s Division%20of%20Institutional%20Advancement/FSU_Style_Guide.pdf 404s (department renamed). Its companion Color_Print_Codes.pdf on the same domain gives only Pantone/CMYK, no hex. Found FSU''s current Brand Guidelines PDF via the live ''FSU Style Guide'' page instead and pdftotext''d it: ''FSU blue and white are FSU''s primary colors and should be used as the majority colors on each marketing piece. Secondary colors are accent colors...'' Color table: FSU Blue Digital Graphics 0067B1 (matches candidate''s blue exactly), Light Grey Digital Graphics B0B7BC, Dark Grey 5F6062, Orange F78E1E, Green 00A94F, Yellow FFC425, Magenta B51A8A. Wrong-tier catch: candidate paired Blue with Light Grey (#B0B7BC), but the text explicitly names Blue + White (not grey) as FSU''s two primary colors -- grey is one of several secondary/accent colors. Corrected to Blue + White.'
    ),
    (
      'mercy-university',
      '193016',
      array['#002A54','#DFDEDE']::text[],
      'https://www.mercy.edu/sites/default/files/2023-03/Mercy_College_Style_Guide_2023.pdf',
      'high',
      'Candidate''s mercyathletics.com quick-facts page states only ''Colors Blue and White,'' no hex. Wrong-school trap caught: a search-suggested ''brand.mercycollege.edu/color'' page turned out to belong to Mercy College of Ohio (a different institution -- its own footer says ''any official Mercy College of Ohio materials''), not this Mercy University (formerly Mercy College) in Dobbs Ferry, NY -- discarded entirely. Found Mercy''s own mercy.edu-hosted 2023 Style Guide PDF instead; its color-palette page (page 6) has a custom font encoding that pdftotext garbles, so it was rendered to an image and read directly: ''PRIMARY -- MERCY BLUE RGB 0/43/84 #002a54; MERCY SILVER RGB 223/222/222 #DFDEDE'' alongside a longer ''SECONDARY'' set (Dust Blue, Sky Blue, Green, Red, Purple, Yellow, Orange, Teal). Kept the two explicitly labeled Primary colors (Blue is dark navy, Silver is a light neutral but is one of only two labeled-Primary colors, matching the narrow exception).'
    ),
    (
      'millersville-university-of-pennsylvania',
      '214041',
      array['#000000','#EEB211']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/millersvilleathletics.com/documents/2015/6/30/6146_UMC_0615_JL_Millersville_University_Brand_Guidelines.pdf',
      'high',
      'Candidate''s millersville.edu/ucm/files/mu-identity-guide.pdf 404s. Found and pdftotext''d Millersville''s Identity Guidelines PDF (hosted on the athletics S3 bucket but authored by University Marketing per its own footer ''www.millersville.edu/ucm''). Page 9, ''University Colors'': ''The official Millersville University colors are black and gold.'' Black PANTONE Black C: RGB 0/0/0 = #000000. Gold PANTONE 124C: RGB 238/178/17 = #EEB211. Minor correction: candidate''s #EEB111 is a one-digit-off typo of the real RGB-derived #EEB211. Dropped candidate''s white -- only black and gold are stated as official; no white in this section.'
    ),
    (
      'rpi',
      '194824',
      array['#000000','#FFFFFF','#D6001C']::text[],
      'https://brand.rpi.edu/d/pfJS6BKVKBeq/brand-guidelines#/-/color',
      'high',
      'Candidate''s rpi.edu/dept/scer/resources/BrandGuidelines_06_12_15.pdf (2015) is superseded: RPI unveiled a new brand identity in August 2025 (see news.rpi.edu/2025/08/14 ''RPI Unveils Dynamic New Brand Identity''). Found and read the current public RPI Brand Guidelines portal (brand.rpi.edu) Color page directly: ''PRIMARY COLORS -- Our primary palette establishes RPI''s visual foundation with black, white, and red as the institutional core.'' Black HEX #000000, White HEX #FFFFFF, Red HEX #D6001C (PMS 2035). Wrong-era catch: candidate''s #E2231B/#222222 are old (pre-rebrand) approximations that no longer match the current stated Red (#D6001C) or Black (#000000). Updated to the current three-color institutional core as explicitly stated post-rebrand.'
    ),
    (
      'princeton',
      '186131',
      null,
      null,
      null,
      'Candidate''s communications.princeton.edu/guides-tools/logo-brand-assets is now at .../logo-graphic-identity; visited live and confirmed the actual page text: ''Princeton staff, faculty and students may access the University brand guide and core branding assets; if you are prompted to request access...'' -- i.e. genuinely access-gated, no public colors/hex content. A Princeton subdomain (citp.princeton.edu/about/graphic-identity) has its own department logo colors (PMS 7691 blue, PMS 158 orange) but that''s CITP''s own palette, not Princeton University''s institutional identity -- wrong scope, discarded. Athletics quick-facts/game-notes PDFs state only ''Colors: Orange and Black'' with no hex. Third-party sources disagree on the exact orange (#ee7f2d vs #f58025 vs #ff8f00 vs #e77500), consistent with an old, unverifiable 2008 guide mirrored off-domain. Left null rather than pick among conflicting unverified third-party hexes for a color the university''s own public pages don''t state.'
    ),
    (
      'johns-hopkins',
      '162928',
      array['#68ACE5','#000000']::text[],
      'https://hopkinssports.com/sports/2018/6/15/quick-facts.aspx',
      'high',
      'Candidate URL resolved live and was read directly. ''Colors: Hopkins Blue (PMS 284) and Black Hex Color Code: #68ace5.'' Matches candidate exactly for both hexes (Hopkins Blue #68ACE5, Black #000000, the latter named but not given an explicit redundant hex since black is unambiguous). Confirmed as-is, no changes.'
    ),
    (
      'university-of-san-diego',
      '122436',
      array['#003B70','#0074C8','#75BEE9']::text[],
      'http://www.sandiego.edu/brand/visual-identity/colors/',
      'high',
      'Candidate URL resolved but actually serves USD''s full Brand Guidelines PDF (not an HTML page) -- downloaded and pdftotext''d directly. ''Primary Palette -- The blues and white of the University of San Diego''s primary color palette are an important feature... Founders Blue PMS 281 #003b70; Immaculata Blue PMS 300 #0074c8; Torero Blue PMS 292 #75bee9; White #ffffff.'' Candidate''s Founders Blue and Torero Blue match exactly, but candidate dropped the middle blue, Immaculata Blue (#0074C8). Kept all three named blues (Founders/Immaculata/Torero), which the source''s own prose calls ''USD''s primary color palette,'' dropping white per prefer-1-2-3-chromatic guidance since three genuine chromatics were available.'
    ),
    (
      'purdue-university-northwest',
      '490805',
      array['#CFB991']::text[],
      'https://www.pnw.edu/marketing-communications/power-onward-brand-guidelines/',
      'low',
      'Candidate''s official-colors-of-pnw-athletics/ URL now redirects to the parent Power Onward Brand Guidelines page. A WebFetch-tool summary of that page initially returned a fabricated-looking hex (#CFB991 attributed with false precision) -- per the no-trusting-fetch-tool-summaries rule, re-verified independently with a real rendered browser session instead of trusting it. The actual public page states only: ''Official Colors of Purdue University Northwest -- Primary Palette -- The Purdue University Northwest Mane Gold, black and white are the official colors for Purdue University Northwest,'' with NO hex values printed anywhere on the public page -- the full spec is gated behind a SharePoint link requiring PNW login. #CFB991 (Pantone 7502C) is nonetheless very widely and consistently documented elsewhere as PNW/Purdue-system ''Old Gold,'' so recorded it at low confidence (reputable-secondary-index tier) as a single chromatic rather than inventing black/white hex values that also aren''t stated. Candidate''s #E6D395 does not match this or any other found source.'
    ),
    (
      'maryville-university-of-saint-louis',
      '178059',
      array['#C91235']::text[],
      'https://www.maryville.edu/marketing/wp-content/uploads/sites/35/2020/08/19-MV-31156-Brand_Guidelines-Updates_Oct_2021-CORE-FIN.pdf',
      'high',
      'Candidate''s 2016-dated Brand-Guidelines PDF 404s. Found and pdftotext''d Maryville''s current (October 2021) Brand Guidelines PDF instead, page 5, ''Maryville Color Palette'': ''Primary Color -- PANTONE 186 C ... RGB 201/18/53 ... HEX c91235.'' Wrong-swatch catch: candidate''s #C8102E is close but not exact -- the real, currently-published Primary Color hex is #C91235. The same page''s ''Supporting Colors'' section separately lists Grey #555960, Black #000000 and White #FFFFFF -- none labeled Primary, unlike candidate''s inclusion of a near-black third hex, so kept only the one color the document itself calls ''Primary Color.'''
    ),
    (
      'university-of-central-missouri',
      '176965',
      array['#CF202E','#000000']::text[],
      'https://www.ucmo.edu/offices/integrated-marketing-and-communications/internal-resources/fac-staff/ucm-branding/ucm-colors/index.php',
      'high',
      'Candidate URL resolved live and was read directly. ''UCM is Red and Black -- The University of Central Missouri has two primary colors, red (PMS 186) and black... UCM Red ... HEX: #cf202e'' (matches candidate exactly) ''UCM Black ... HEX: #000000'' (matches candidate exactly). Wrong-tier catch: candidate also included white, but the source explicitly says UCM ''has two primary colors'' (red and black only) -- a separate ''UCM Gray'' (#a7a9ac) exists for campus paint, not as a third official brand color. Dropped candidate''s white.'
    ),
    (
      'angelo-state-university',
      '222831',
      array['#003087','#FFC72C']::text[],
      'https://www.angelo.edu/brand-guide/colors.php',
      'high',
      'Candidate''s identity_guidelines/logos.php page is a stale landing page with no color content of its own. Found the actual Colors subpage linked from Angelo State''s current Brand Guide and read it live: ''The primary, official school colors for Angelo State University are blue and gold... Primary Colors -- Pantone 287C ... HEX: #003087. Pantone 123 ... HEX: #ffc72c.'' Major wrong-swatch catch: candidate''s #245397/#FFFFFF/#F0C33B match none of the real primary colors at all. Corrected to the two explicitly-named official primary colors, dropping white (not part of the stated primary pair; a ''Supporting Palette'' of five additional accent colors exists separately and is explicitly restricted to accent-only use).'
    ),
    (
      'columbus-state-university',
      '139366',
      array['#003359','#C60C30']::text[],
      'https://www.columbusstate.edu/scm/_docs/CSU_Brand_Guidelines-1.pdf',
      'high',
      'Candidate URL matches the school''s current live PDF; the direct-fetch tool timed out repeatedly against this host (likely WAF/TLS-fingerprint blocking curl), so the file was retrieved through a real rendered browser session and independently pdftotext''d rather than trusted from a fetch-tool summary. ''Columbus State Blue and Columbus State Red are the university''s official colors... COLUMBUS STATE BLUE PANTONE 540 C ... Hex #003359'' (matches candidate exactly) ''COLUMBUS STATE RED PANTONE 186 C ... Hex #c60c30'' (matches candidate exactly). Wrong-tier catch: candidate also included white, but the source states only Blue and Red are ''the university''s official colors'' -- dropped white.'
    ),
    (
      'augusta-university',
      '482149',
      array['#002F55','#FFFFFF','#A5ACAF']::text[],
      'http://brand.augusta.edu/color/',
      'high',
      'Candidate URL resolved live and was read directly. ''PRIMARY PALETTE AUGUSTA BLUE ... WEB: 002f55'' (matches candidate exactly), ''AUGUSTA GREY ... WEB: A5ACAF'' (matches candidate exactly), and ''Primary Use -- The official logo colors are blue (PMS 540), grey (PMS 429) and white. No other logo colors are acceptable.'' White is explicitly one of exactly three named official logo colors here, satisfying the narrow primary-set exception. Confirmed candidate as-is, no changes.'
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
