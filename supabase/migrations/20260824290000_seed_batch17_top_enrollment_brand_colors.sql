-- Batch 17 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given (hex matched the official source
-- verbatim once a live copy was located): houston-christian-university
-- (Royal Blue/Orange, official athletics style guide), lynn-university
-- (blue/white/gray -- explicit 3-color "primary color palette" statement),
-- yeshiva-university (blue/black/gray -- explicit 3-color identity system
-- with literal HTML values), babson-college (single stated "primary
-- color," Babson Green), manhattan-college (Primary green + Metallic gold,
-- recovered via Wayback of the exact candidate PDF).
--
-- Wrong-swatch / wrong-tier corrections (candidate hex did not match the
-- school's own official source, or mixed colors from different
-- primary/secondary/flag/metallic tiers of the same document):
-- southeastern-oklahoma-state-university (both blue and gold corrected
-- against the current Aug-2026 branding guide), university-of-indianapolis
-- (crimson corrected and re-picked from the current official "Primary
-- Palette" page, replacing a dead 2016 PDF citation), university-of-
-- west-alabama (red corrected by one digit against the current 2025
-- graphic standards), university-of-portland (purple substantially
-- corrected -- candidate's hex did not match any official source; white
-- swapped for the document's actual second primary color, gray),
-- iona-university (gold corrected against the athletics site's own stated
-- "Web ready colors" text), widener-university (blue and yellow corrected
-- against the school's current "Brand Colors" page, replacing a dead 2015
-- PDF), robert-morris-university (navy corrected by one digit), charleston-
-- southern-university (True Blue and Buccaneer Gold corrected against the
-- school's current 2024 Brand Guide, read via rendered page images since
-- Issuu has no extractable text layer), illinois-institute-of-technology
-- (red corrected; candidate's #DE2626 does not appear on the official
-- "University Colors" page at all), university-of-tulsa (candidate paired
-- blue with a color from the document's separate "Tulsa Flag Colors" box;
-- corrected to the document's actual "Primary Colors" box, blue + gold),
-- azusa-pacific-university (red corrected against the current graphic
-- standards quick guide, recovered from a working apu.edu path after the
-- candidate's static.apu.edu subdomain stopped resolving), fitchburg-
-- state-university (both green and yellow substantially corrected against
-- the current official branding-requirements page's stated hex), bethune-
-- cookman-university (both maroon and gold substantially corrected against
-- the current Sep-2025 official Brand Guidelines, replacing an
-- unextractable Adobe Spark citation), middlebury-college (blue
-- substantially corrected against the current Visual Identity System PDF's
-- single stated "Official Color"), southern-arkansas-university-main-
-- campus (gold corrected against the on-domain style-guide PDF; medium
-- confidence kept because the document states two unlabeled color pairs
-- with no primacy statement between them), university-of-north-carolina-
-- asheville (candidate's citation was dead; recovered "Bulldog Blue" via
-- an on-domain CSS custom property, medium confidence since no printed
-- HEX label was found), longwood-university and university-of-richmond
-- (both confirmed their chromatic pair exactly against a live official
-- source; only the fabricated white needed to be dropped), lipscomb-
-- university and jacksonville-university (confirmed/lightly corrected
-- against their official PDFs; jacksonville-university's hex was derived
-- directly from the document's own stated RGB triples, not a Pantone
-- lookup), pennsylvania-state-university-penn-state-abington (kept
-- candidate's navy/white and added the document's third labeled Primary
-- color, Beaver Blue).
--
-- Fabricated-neutral / wrong-tier-neutral catches (candidate white/black
-- had no support in the real source, or belonged to a different tier, and
-- was dropped): southeastern-oklahoma-state-university, longwood-
-- university, university-of-indianapolis, lipscomb-university,
-- university-of-richmond, university-of-west-alabama, university-of-
-- portland (white replaced with the real second color, gray), iona-
-- university, widener-university, jacksonville-university (white replaced
-- with the real third color, gray), university-of-north-carolina-
-- asheville, robert-morris-university, charleston-southern-university,
-- houston-christian-university, savannah-state-university, illinois-
-- institute-of-technology (white replaced with the real official gray),
-- azusa-pacific-university (white replaced with the real second color,
-- black), fitchburg-state-university, manhattan-college, middlebury-
-- college, bethune-cookman-university (white is real but explicitly
-- Secondary, not Primary), babson-college.
--
-- Dead-link / access-blocked recoveries (original citation 404/403'd,
-- redirected to a generic shell, or rendered nothing extractable; found
-- the school's current official page, a same-domain PDF at a corrected
-- path, or a Wayback Machine capture instead): southeastern-oklahoma-
-- state-university, university-of-indianapolis, lipscomb-university
-- (Wayback), university-of-richmond, university-of-west-alabama,
-- university-of-portland, widener-university, university-of-north-
-- carolina-asheville, robert-morris-university, charleston-southern-
-- university (Issuu flipbook, no PDF text layer -- read via rendered page
-- images), pennsylvania-state-university-penn-state-abington (candidate
-- link was live and correct), savannah-state-university,
-- illinois-institute-of-technology, university-of-tulsa, azusa-pacific-
-- university (DNS failure on candidate's subdomain), fitchburg-state-
-- university, manhattan-college (Wayback), middlebury-college,
-- bethune-cookman-university (candidate JS-only page; a first replacement
-- /comms/ path also 404'd and its Wayback capture was truncated at a 5MB
-- crawl cap; found the real current path via the school's creative-
-- services page), southern-arkansas-university-main-campus.
--
-- Low/medium confidence flags: university-of-north-carolina-asheville is
-- medium -- the official graphic-standards page's actual swatch image was
-- not eyedropped; corroborated "Bulldog Blue" instead via an on-domain CSS
-- custom property naming the same color, independently corroborated by a
-- web search. southern-arkansas-university-main-campus is medium -- the
-- on-domain style-guide PDF states two full color pairs (Athletic
-- Blue/Yellow and Royal Blue/Yellow Gold) with no text distinguishing
-- which is "primary"; kept the pair matching candidate's blue.
--
-- Left null: south-carolina-state-university (both the 2011 style manual
-- and a newer scsu.edu strategic-communications PDF give only Pantone
-- numbers, and the two documents even disagree with each other on the
-- blue's Pantone number -- no hex anywhere, and no safe way to pick a
-- Pantone conversion). roosevelt-university (candidate citation, a
-- located 2025 athletics brand-guide PDF, and two separate Wayback
-- captures of that PDF are all the same Incapsula bot-wall shell; no
-- institutional roosevelt.edu color page found). lafayette-college (both
-- the candidate's 2010 athletics guide and the college's full 2011 Visual
-- Identity System state only Pantone numbers, with an explicit disclaimer
-- that the printed swatches aren't accuracy-checked; no hex or RGB
-- anywhere in either document).
--
-- Ran every final hex list through production deriveInks()/glyphInks()
-- (web/src/lib/derive-inks.ts) via a throwaway tsx script (deleted before
-- finishing). Every one of the 27 populated rows produced its own derived
-- plates (house=false) -- no school in this batch lost its chromatic
-- primary to the house forest/ochre fallback. See
-- data/brand-colors/batch-17-2026-08-24.jsonl for the full per-school
-- record, including the three null entries.

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
      'southeastern-oklahoma-state-university',
      '207847',
      array['#005DA6','#FFD100']::text[],
      'https://www.se.edu/university-marketing/wp-content/uploads/sites/60/2026/08/Branding-Style-Guide-2026-2.pdf',
      'high',
      'Candidate citation (2015 Athletic-Graphic-Standards.pdf) 404s. Found the current Aug-2026 Branding Style Guide linked from se.edu/university-marketing; its "UNIVERSITY COLORS" section states "two primary colors and one accent color": University Blue #005DA6 and University Gold #FFD100 are explicitly labeled Primary; University Gray #C1C1C1 is labeled Secondary and was dropped. Candidate''s blue/gold (#0033A0/#FFDD00) and fabricated white did not match; both corrected.'
    ),
    (
      'longwood-university',
      '232566',
      array['#002147','#A2A4A3']::text[],
      'http://www.longwood.edu/fileshare/marketing/Longwood_Visual_Brand_Guide_2021.pdf',
      'high',
      'PDF confirmed live and text-extracted. "Primary Colors" section states exactly Longwood Blue HEX 002147 and Longwood Gray HEX A2A4A3; a 5-color "Secondary Colors" set follows separately. Candidate''s blue/gray matched exactly; fabricated white (not in either official list) dropped.'
    ),
    (
      'university-of-indianapolis',
      '151263',
      array['#B20A38','#77777A']::text[],
      'https://uindy.edu/communications-marketing/brand-guidelines',
      'high',
      'Candidate citation (2016 athletics Media Supplement PDF) is dead, redirected to a generic Sidearm Sports shell with no extractable content. Found UIndy''s current official Brand Guidelines page with an explicit "Primary Palette" section stating PMS 201 Crimson HEX #B20A38, PMS Cool Gray 6 #A9A8A9, PMS Cool Gray 9 #77777A, and PMS Black #1A1A1A (4 colors). Picked the crimson plus the darker, more-used Cool Gray 9 as the well-known "Crimson and Grey" 2-color identity, staying within the 1-2-chromatic preference; candidate''s #9D2136/#FFFFFF/#C0BFBA did not match any of these and were replaced.'
    ),
    (
      'lipscomb-university',
      '219976',
      array['#331E54','#F4AA00']::text[],
      'http://web.archive.org/web/20181007111421/https://www.lipscomb.edu/uploads/28032.pdf',
      'high',
      'Candidate citation live-403''s (Cloudflare bot wall); recovered via Wayback Machine capture of the exact same PDF. "Full-Color Logos" section states Purple PMS 2695C HEX #331E54 and Gold PMS 130C HEX #F4AA00 exactly, matching candidate. Text also names black/white as acceptable one-color logo variants (not a stated hex pair); fabricated white dropped, keeping the two chromatic primaries.'
    ),
    (
      'university-of-richmond',
      '233374',
      array['#000066','#990000']::text[],
      'https://brand.richmond.edu/visual/color/',
      'high',
      'Candidate citation (/elements/color/palettes.html) 404s; found the current Brand Center color page. Its "Primary Palette" states exactly RED Pantone 200 HEX #990000 and BLUE Pantone 281 HEX #000066, matching candidate''s two chromatic values exactly. Fabricated white (not part of the stated 2-color Primary Palette; Secondary Palette is teal/gray tones) dropped.'
    ),
    (
      'university-of-west-alabama',
      '101587',
      array['#AA182C','#000000']::text[],
      'https://www.uwa.edu/app/uploads/2025/03/UWA20Graphic20Standards2025.pdf',
      'high',
      'Candidate citation (uploadedFiles/Graphics/graphicstandards.pdf) 404s; found the current March-2025 Graphic Standards Brand Guidelines PDF on uwa.edu. "Primary Colors" page states Red HTML AA182C (Pantone 187C) and Black HTML 000000; "REVERSED (WHITE)" only describes a reversed-logo application, not a third official color, so candidate''s fabricated white was dropped. Candidate''s red (#A6192E) was close but not exact; corrected to the document''s stated #AA182C.'
    ),
    (
      'university-of-portland',
      '209825',
      array['#1E1656','#5E6A71']::text[],
      'https://ww1.up.edu/marketing/files/brand-boook-2024-05-09.pdf',
      'high',
      'Candidate citation is a 2014 athletics news article with no hex at all (only prose naming "purple"); the hex in candidate data appears fabricated/pulled from an unrelated source. Found the current (May 2024) official Visual Brand Identity Guide PDF, which states in prose "The University of Portland has two primary colors: purple and gray" with a table giving Purple (PMS 275C) HEX #1E1656 and Gray (PMS 431C) HEX #5E6A71. Both candidate values (#330072 purple, white) were wrong and replaced.'
    ),
    (
      'iona-university',
      '191931',
      array['#661E2B','#FFCC00']::text[],
      'http://www.icgaels.com/sports/2017/6/26/logo-library.aspx',
      'high',
      'Citation page loads live and states "Web ready colors: Maroon: RGB (102, 30, 43) or HEX #661E2B; Gold: RGB (255, 204, 0) or HEX #FFCC00." Candidate''s maroon matched exactly but candidate''s gold (#EAAF0F) did not match the stated #FFCC00 and was corrected. No white is stated on the page; fabricated white dropped.'
    ),
    (
      'widener-university',
      '216852',
      array['#0072BC','#FFE500']::text[],
      'https://www.widener.edu/widener-brand-identity-logos-imagery',
      'high',
      'Candidate citation (2015 graphics_standards PDF) 404s. Found Widener''s current "Brand Colors" section on widener.edu, which states 4 colors with hex: WU Blue #0072BC, WU Yellow #FFE500, WU Dark Blue #00053E, WU Light Blue #7BAFDE (no primary/secondary labels given). Picked the two listed first (Blue, Yellow), matching the athletics logo guide''s "royal blue... yellow" framing, staying within the 1-2-chromatic preference. Candidate''s #0057B8/#FFC845/white did not match any of the 4 stated values and were replaced.'
    ),
    (
      'south-carolina-state-university',
      '218733',
      null::text[],
      null,
      null,
      'Searched the candidate''s cited 2011 SCSU Style Manual and a newer strategic-communications "SCSU Branding-revised.pdf" on scsu.edu -- both give only Pantone numbers, never a hex or RGB, for the school''s garnet/blue/black colors. The two official documents even disagree with each other on the blue''s Pantone number (2011 manual: PMS 2747; current doc: PMS 294), so a third-party Pantone-to-hex conversion would be guessing which spec is current. No usable on-domain hex found; left null per the brief rather than fabricate or guess a conversion.'
    ),
    (
      'jacksonville-university',
      '134945',
      array['#004D43','#C8B783','#B3B2B1']::text[],
      'https://www.ju.edu/brand/download/assets/dolphins-brandguide-2018.pdf',
      'high',
      'PDF confirmed live. "Color Information" page states literal RGB (not just Pantone) for all 3 colors: Pantone 3305c R0/G77/B67 = #004D43, Pantone 4525c R200/G183/B131 = #C8B783, Pantone Cool Gray 5c R179/G178/B177 = #B3B2B1 -- hex derived directly from the document''s own stated RGB triples, not a third-party Pantone lookup. All 3 are presented together with no primary/secondary split, so all 3 were kept (matches candidate''s slot count). Candidate''s #004E42/#C5B783 were close approximations; corrected to the document''s exact RGB-derived hex. No white/black stated; candidate''s fabricated white dropped in favor of the actual third stated color, gray.'
    ),
    (
      'university-of-north-carolina-asheville',
      '199111',
      array['#003DA5']::text[],
      'https://go.unca.edu/communication/branding/graphic-standards/',
      'medium',
      'Candidate citation (/color-palette) redirects to the department homepage, dead. Found the current Graphic Standards page, which states in prose "Our signature Bulldog Blue should appear as the primary color" and separately embeds an on-domain CSS custom property "--bulldog-blue: #003DA5" in the same page''s stylesheet -- an on-domain CSS custom property naming the color, not eyedropped from the actual swatch image (which is a PNG, not read). Only this one confirmed chromatic value was kept; candidate''s fabricated white/black dropped. Medium tier because the hex comes from a CSS variable rather than a printed HEX label on a formal swatch.'
    ),
    (
      'robert-morris-university',
      '215655',
      array['#011E41','#AA182C']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/rmu.sidearmsports.com/documents/2023/3/15/RMU_Brand_style_guide__1_.pdf',
      'high',
      'Candidate''s exact URL 404s; the same document exists at this s3 path with a "__1_" suffix. "Color Palette" page states HEX 011E41 (Navy), HEX AA182C (Red), HEX B0B3B2 (PMS 421 gray), HEX D9D8D6 labeled "(Optional Gray)", and White. Kept the two un-labeled-optional chromatic colors (Navy, Red); candidate''s navy (#001E41) was off by one digit from the stated #011E41 and was corrected; fabricated/optional white and gray dropped per the 1-2-chromatic preference.'
    ),
    (
      'charleston-southern-university',
      '217688',
      array['#002D5B','#AD9E6E']::text[],
      'https://issuu.com/csumagazine/docs/csu-brand_guide-2024_digital_',
      'high',
      'Candidate''s s3 Athletics_Style_Guide.pdf (both live and Wayback) is a logo-usage-only doc with no color swatches. Found CSU''s official 2024 Brand Guide (published by csumagazine on Issuu); rendered and read the actual "Color Palette" page image (not eyedropped -- printed HEX labels were read directly): "The primary CSU colors remain True Blue and Buccaneer Gold" with True Blue HEX 002d5b and Buccaneer Gold HEX ad9e6e; Ocean Blue (#5eb6cd, explicitly barred from athletics use) and Cutlass Gray (#383838) are separate, non-primary entries. Candidate''s #002855/#A89968 were close but not exact; corrected. Fabricated white dropped.'
    ),
    (
      'houston-christian-university',
      '225399',
      array['#062F87','#FA4D09']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/hbu.sidearmsports.com/documents/2023/4/18/HCU_Athletics_Style_Guide_2023.pdf',
      'high',
      'PDF confirmed live and text-extracted. "SCHOOL COLORS" section states exactly Royal Blue #062f87 and Orange #fa4d09, matching candidate''s two chromatic values exactly. Only two colors are listed; fabricated white dropped.'
    ),
    (
      'pennsylvania-state-university-penn-state-abington',
      '214801',
      array['#001E44','#1E407C','#FFFFFF']::text[],
      'https://brand.psu.edu/design-toolkit/design-essentials',
      'high',
      'Confirmed live, university-wide brand page (applies across all Penn State campuses including Abington, which has no separate brand microsite). States explicitly: "Primary Nittany Navy HEX #001E44 ... Beaver Blue HEX #1e407c ... White out HEX #ffffff" as exactly 3 labeled Primary colors, with Pugh Blue #96BEE6 called out separately as Secondary. Candidate had only navy+white; added the third stated primary, Beaver Blue, since white is explicitly one of only 3 labeled PRIMARY colors here (falls under the brief''s stated exception, not the no-neutral-append bar).'
    ),
    (
      'lynn-university',
      '132657',
      array['#003DA5','#FFFFFF','#B1B3B3']::text[],
      'https://www.lynn.edu/uploads/brand/guide/style-guide-V2-low-res.pdf',
      'high',
      'Candidate citation (athletics "Fighting Knights Identity" page) names blue/white/gray in prose but states no hex. Found Lynn''s official University Brand Guide PDF, which explicitly states "Lynn University''s official colors are blue and white. Our primary color palette is blue, white and gray" with Lynn Blue Web #003DA5, White Web #FFFFFF, Lynn Gray Web #B1B3B3 -- confirming candidate exactly. White is kept because it is explicitly one of only 3 labeled primary colors (brief''s stated exception).'
    ),
    (
      'yeshiva-university',
      '197708',
      array['#325A89','#555150','#85878A']::text[],
      'https://www.yu.edu/sites/default/files/inline-files/_FINAL_YU_Branding_Guide3%202017_0.pdf',
      'high',
      'Candidate citation page (marketing/branding) itself states only Pantone (294, Cool Gray 9) with no hex, but links directly to the official YU Branding Guide PDF on the same domain, which states "1.2 Identity Color -- There are three main colors in the Yeshiva University identity system: Yeshiva Blue (PMS 294), black, and PMS Cool Gray 9" with explicit HTML values HTML325A89, HTML555150, HTML85878A -- confirming candidate exactly. All 3 kept since the document itself names them as the 3 official identity colors (dominant/secondary/black), not a fabricated neutral append.'
    ),
    (
      'roosevelt-university',
      '148487',
      null::text[],
      null,
      null,
      'Candidate citation redirects to a generic "Gameday" Sidearm shell. Located a real 2025 Roosevelt Athletics Brand Guide PDF at rooseveltlakers.com, but the live URL and two separate Wayback captures of it all return the same Incapsula/bot-wall HTML shell rather than the PDF (confirmed via file/pdftotext, not just an HTTP error). Web search for an institutional (non-athletics) roosevelt.edu brand/color page with a stated hex turned up only third-party team-color sites. No usable on-domain hex found; left null.'
    ),
    (
      'savannah-state-university',
      '140960',
      array['#002395','#FF5800']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/ssuathletics.com/documents/2020/5/22/Savannah_State_Athletics_Logo_and_Branding_Guide.pdf',
      'high',
      'Candidate citation (2014 news article page) redirects to a generic Sidearm shell. Found the current "2026 Branding Guide" PDF at the athletics s3 bucket (a newer document at a related path); its "COLORS" page states Reflex Blue HEX #002395 (matches candidate exactly) and Orange (PMS 021) HEX #FF5800 -- candidate''s orange (#F24D17) did not match and was corrected. Black #000000 and Cool Gray 6 #A7A8AA are also listed but grouped separately from Blue/Orange; dropped per the 1-2-chromatic preference (candidate''s fabricated white also dropped).'
    ),
    (
      'illinois-institute-of-technology',
      '145725',
      array['#CC0000','#76777B','#000000']::text[],
      'https://www.iit.edu/marketing-communications/resources/university-colors',
      'high',
      'Candidate citation (cloudfront student-athlete handbook PDF) has no color content at all. Found IIT''s official "University Colors" page, which states "Official University Colors" as exactly 3: Illinois Tech Red HEX #CC0000, Illinois Tech Gray HEX #76777B, Illinois Tech Black HEX #000000 (a separate "Alternate Color Palette" orange #FF9900 is explicitly non-official, used only for the Scarlet Hawks athletics logo). Candidate''s red (#DE2626) did not match the stated #CC0000 and was corrected; fabricated white dropped in favor of the actual official gray. All 3 official colors kept since explicitly labeled as such.'
    ),
    (
      'university-of-tulsa',
      '207971',
      array['#003595','#D0B787']::text[],
      'https://tulsahurricane.com/documents/download/2026/1/29/Tulsa_StyleGuide_26.pdf',
      'high',
      'Candidate citation (2022 style guide PDF) 404s; found the current 2026 Tulsa Brand Guide PDF. Rendered the color page as an image to resolve column alignment: it has 3 separately boxed groups -- "PRIMARY COLORS" (Blue PMS 661C HEX #003595, Flat Gold Pantone 7502 HEX #D0B787), "TULSA FLAG COLORS" (Red PMS 186C HEX #CE0E2D, Black HEX #000000), and "METALLIC APPLICATIONS". Candidate paired blue with red and white, but red is explicitly a "flag color" group, not "primary colors"; corrected to the actual Primary Colors pair, blue + gold.'
    ),
    (
      'azusa-pacific-university',
      '109785',
      array['#A8353A','#000000']::text[],
      'https://www.apu.edu/files/graphic_standards_quick_guide.pdf',
      'high',
      'Candidate citation domain (static.apu.edu) does not resolve at all (DNS failure); recovered the same document under www.apu.edu/files/. States in prose: "The university''s official colors are brick and black. Gray and silver are acceptable accent colors" with Brick Pantone 1807C HEX #A8353A stated; Gray is given as HEX #CCCCCC (accent, not primary) and Silver (Pantone 877, no hex given). Candidate''s red (#990000) did not match the stated brick #A8353A and was corrected; fabricated white dropped (not mentioned anywhere in the doc) in favor of the actual second official color, black.'
    ),
    (
      'lafayette-college',
      '213385',
      null::text[],
      null,
      null,
      'Checked both the candidate''s cited 2010 Athletics Identity guide and Lafayette''s full 2011 Visual Identity System PDF (communications.lafayette.edu) -- both state only Pantone numbers ("Lafayette Gold: PANTONE 873", "Lafayette Maroon: PANTONE 202", "Lafayette Black: PANTONE Process Black") with an explicit disclaimer that the printed color swatches "have not been evaluated by Pantone, Inc. for accuracy." No hex or RGB value appears anywhere in either document. Left null rather than convert Pantone numbers via a third-party table.'
    ),
    (
      'fitchburg-state-university',
      '165820',
      array['#0A5640','#FFC72A']::text[],
      'https://www.fitchburgstate.edu/about/marketing-and-integrated-communications/university-branding-and-visual-identity-requirements',
      'high',
      'Candidate citation redirects to a login page, dead. Found the current "University Branding and Visual Identity Requirements" page, which states in prose: "The university colors are green and yellow... Green RGB (10 86 64) or HEX (0A5640). Yellow RGB (255 199 42) HEX (FFC72A)." This differs from a slightly different green (#00563F) used in the site''s own favicon meta tags; the explicit prose statement of the two official colors was treated as authoritative over the favicon accent. Candidate''s #00563F/#E9AF2F/white did not match and were corrected/dropped.'
    ),
    (
      'manhattan-college',
      '192703',
      array['#00703C','#A39161']::text[],
      'http://web.archive.org/web/20160304105320/http://manhattan.edu/sites/default/files/athletic_colors_0.pdf',
      'high',
      'Candidate''s exact citation URL 404s live; recovered via Wayback capture of the same PDF. "COLORS - PRIMARY" states Green PMS 349C HEX 00703c exactly matching candidate. "COLORS - METALLIC" states PMS 871C HEX a39161, also matching candidate''s third value exactly; kept as the real second official color instead of candidate''s fabricated white, since it is explicitly stated (not invented) even though labeled Metallic rather than Primary. A "COLORS - NONMETALLIC" group (PMS 4505C, Cool Gray 8) was not used.'
    ),
    (
      'middlebury-college',
      '230959',
      array['#0D395F']::text[],
      'https://www.middlebury.edu/sites/default/files/2022-05/Middlebury%20Identity%20Manual_Rev072319%204-2020.pdf',
      'high',
      'Candidate''s exact citation URL 404s; found the current (Rev. 7/23/19) Middlebury Visual Identity System PDF at the same institutional domain. Its "Color Conversion Tables" page states a single "Official Color": PMS 294, HEX 0D395F -- this does not match candidate''s #003882, which was corrected. A separate list of "Accent Colors" follows, none of which is white; no "official colors are blue and white" statement exists anywhere in the document (white only appears as a logo-reversal option), so candidate''s fabricated white was dropped, leaving the single official chromatic color.'
    ),
    (
      'bethune-cookman-university',
      '132602',
      array['#860038','#FDB913']::text[],
      'https://www.cookman.edu/creative-services/documents/b-cu-brand-guidelines.pdf',
      'high',
      'Candidate citation (Adobe Spark page) is JS-rendered with no extractable text/hex. Located the current (Sep 2025 v3) official B-CU Brand Guidelines PDF via the school''s creative-services page (a prior /comms/ path 404s; a Wayback capture of that dead path was also truncated at a 5MB crawl cap, so the live creative-services copy was used instead and fully text-extracted). Its "Colors" page explicitly labels "Primary": B-CU Blood Maroon HEX #860038, B-CU Sun Gold HEX #FDB913; "Secondary": Black #000000, White #FFFFFF. Candidate''s #6F263D/#FFFFFF/#F2A900 did not match any of these; corrected to the actual Primary pair and dropped white since it is explicitly Secondary, not Primary.'
    ),
    (
      'babson-college',
      '164580',
      array['#006644']::text[],
      'https://www.babson.edu/college-marketing/babson-college-brand-guidelines/color-palette/',
      'high',
      'Candidate''s exact citation URL 404s; found the live official Color Palette page at the same domain. States "Babson Green (PMS 3425) is the primary color for the institution... should be the dominant color" with Hex #006644 -- confirms candidate''s green exactly. The rest of the extensive palette is explicitly secondary/accent, and no black or white appears anywhere in the palette list; candidate''s fabricated white/black dropped, leaving the single stated primary.'
    ),
    (
      'southern-arkansas-university-main-campus',
      '107983',
      array['#003DA5','#FAE053']::text[],
      'https://web.saumag.edu/communications/style-guide/',
      'medium',
      'Candidate''s exact citation (/colors/ subpage) 404s on both saumag.edu subdomains; the parent style-guide URL resolves to a real, on-domain "SAU Style Design" licensing/trademark PDF (Nov 2015) with a "COLOR INFORMATION" table listing 4 colors with no primary/secondary labels: Athletic Blue HTML 003DA5, Athletic Yellow HTML FAE053, Royal Blue HTML 003087, Yellow Gold HTML DAAA00. Candidate''s blue (#003DA5) matches "Athletic Blue" exactly; candidate''s gold (#FFD100) matches neither stated gold and was corrected to Athletic Yellow. Kept the Athletic Blue/Yellow pairing over the alternate Royal Blue/Yellow Gold pairing; medium confidence because the source doc does not designate either pair as primary.'
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
