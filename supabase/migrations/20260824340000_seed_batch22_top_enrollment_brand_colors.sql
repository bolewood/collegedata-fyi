-- Batch 22 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a dropped
-- mechanically-attached white/neutral: north-park-university (Royal Blue/
-- Gold exact hex match on the live "Athletics Color Codes" page, white
-- dropped), franklin-and-marshall-college (Diplomats Blue/Light Blue/
-- White exact 3-of-3 match, recovered via Wayback), marywood-university
-- (Green/White/Gold exact 3-of-3 match, "these are our main brand
-- colors"), springfield-college (Maroon/White exact match, "PRIMARY
-- PALETTE"), hobart-william-smith-colleges (Purple/Orange exact match on
-- the live Hobart Athletics Brand Standards PDF, white dropped),
-- university-of-pittsburgh-johnstown (Pitt Blue/Gold exact match,
-- recovered via Wayback, white dropped), claflin-university (Orange/
-- Maroon RGB-exact match, recovered via Wayback -- candidate's three
-- guessed hexes were all wrong).
--
-- Corrected (candidate hex, color set, or source did not match the
-- school's own current official source): north-greenville-university
-- (Red/Black/White confirmed via a working current brand-guide PDF, the
-- dead-link candidate's citation was wrong), university-of-mount-olive
-- (Green/Gold confirmed, candidate's mechanical white replaced with the
-- real third official color, Gray), university-of-arkansas-at-pine-bluff
-- (added the missing Red from the document's 4-color primary list,
-- dropped White), roanoke-college (all three candidate hexes wrong --
-- corrected via the College's own Brand FAQ PDF to Maroon/Blue/Yellow,
-- candidate's citation was a generic Sidearm template page), bates
-- (candidate's white corrected to the real near-black secondary color,
-- both confirmed via RGB, not Pantone-table guessing), mckendree-
-- university (both hexes corrected via the school's own Brand Standards
-- PDF, white dropped), kenyon (wrong citation with no color content;
-- corrected via Kenyon's 2023 Brand User Guide to all three labeled
-- PRIMARY colors, replacing candidate's guessed white/gray), muhlenberg-
-- college (single red confirmed exactly as the site's own stated web
-- hex; gray dropped -- Pantone only, no on-domain hex), chaminade-
-- university-of-honolulu (all three candidate hexes wrong -- corrected
-- via the live Brand Center page's four named PRIMARY colors), simmons-
-- university (blue corrected, yellow dropped -- not part of the stated
-- "chief operating" primary pair, white kept per its explicit primary
-- listing), misericordia-university (both hexes corrected via the live
-- style guide's "PRIMARY ACADEMIC COLOR PALETTE," white dropped),
-- assumption-university (blue corrected, white/gray dropped -- the
-- current v2.0 guide's PRIMARY COLORS section is just Blue/Black),
-- curry-college (wrong citation -- a student handbook, not a brand
-- guide; corrected via the real Brand Standards PDF to a single primary
-- purple, substantially different from candidate's guessed hex),
-- wheaton-college-massachusetts (candidate's Sidearm-template citation
-- replaced with the College's own Brand Toolkit PDF; corrected the blue
-- and added the missing second primary color, Green, dropping candidate's
-- black/white).
--
-- Wrong-swatch / low-confidence secondary-index fallback (official
-- search exhausted, no on-domain hex found): wofford-college (Adobe
-- InDesign-hosted brand book is JS-only/inaccessible; fell back to a
-- reputable color-code index for Old Gold/Black, low confidence),
-- the-college-of-wooster (official page now redirects to the homepage
-- and the brand guide is behind an internal SharePoint login; fell back
-- to a reputable color-code index for Gold/Black only, matching the
-- school's own "black and gold" description, low confidence; index's
-- third "maroon" value not corroborated, dropped along with candidate's
-- white).
--
-- Left null (no hex/RGB found anywhere on the school's own domain, only
-- Pantone or nothing at all -- see per-school notes in the JSONL for
-- exactly what was searched): concordia-college-at-moorhead (cited PDF
-- is a course catalog with no color content; no cord.edu brand guide
-- found), lake-forest-college (Pantone-only "PMS 186 Red, PMS 871
-- Metallic Gold, and Black," no hex anywhere), hamline-university (all
-- candidate/replacement URLs dead with no Wayback capture; a rendered
-- SVG logo color was found but excluded per the no-eyedropping-SVGs
-- rule), mount-st-marys-university (Pantone-only "Mount navy blue
-- (PANTONE 295)," the actual brand-guide PDF link is dead and
-- unarchived), canisius-university (issuu-hosted style guide is a
-- JS-only viewer with no extractable text; live news pages describe
-- "blue and gold" in prose only, no hex), lebanon-valley-college
-- (candidate's citation and its parent page are both dead with no
-- Wayback capture; the only brand-guidelines doc found is issuu-hosted,
-- JS-only).
--
-- Derive-inks note: chaminade-university-of-honolulu's two blues
-- (Chaminade Blue #0E20A4 and Moonlight #091058) are close enough in
-- hue that deriveInks treats them as too-close and synthesizes a
-- brighter blue for the B plate rather than using either stated hex
-- directly -- expected deriver behavior given two similar navies in the
-- school's own primary set, not a data error. Several single-chromatic
-- schools (north-greenville-university, wofford-college, curry-college,
-- marymount-university, bates, springfield-college, muhlenberg-college,
-- the-college-of-wooster, simmons-university, assumption-university)
-- correctly have their stated black/white/gray filtered out by
-- deriveInks' neutral-rejection rule, leaving a single ink to drive a
-- synthesized A or B plate -- also expected behavior, not a data error;
-- the neutral value is still retained in brand_colors when it was
-- explicitly one of the school's own named primary colors.
--
-- See data/brand-colors/batch-22-2026-08-24.jsonl for the full per-school
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
      'north-greenville-university',
      '218441',
      array['#D60036','#000000','#FFFFFF']::text[],
      'https://ngu.edu/wp-content/uploads/2023/02/brand-guide-2019-opt-north-greenville-university.pdf',
      'high',
      'Candidate''s brand-style-guide.php citation is dead (404); its Wayback capture links out to a brand-guide PDF at a path that itself 404s. Found NGU''s current Identity Brand Guide PDF instead. "UNIVERSITY COLORS / PRIMARY AND SECONDARY COLORS" table lists Red/Dark-Gray/Light-Gray/White/Black; the red cell is independently corroborated elsewhere in the same document ("the ''NGU Sword'' logo ... is primarily NGU Red (Hex D60036)"), so used D60036 over an overlapping/ambiguous d6083b reading in the table itself. Kept Red/Black/White (candidate''s exact 3), red reordered to primary.'
    ),
    (
      'north-park-university',
      '147679',
      array['#0057A8','#FCCE0D']::text[],
      'https://athletics.northpark.edu/sports/2018/7/10/sports-information.aspx',
      'high',
      'Candidate''s citation is live (despite a generic "Sidearm Sports" <title>, the body content loads). "Athletics Color Codes" section states exactly two colors: "Royal ... Hex: #0057a8" and "Gold ... Hex: #fcce0d" -- confirms candidate''s two chromatic hexes exactly. Dropped candidate''s mechanically-attached white -- not part of the stated 2-color set.'
    ),
    (
      'wofford-college',
      '218973',
      array['#8A6E4B','#000000']::text[],
      'https://colorcodeshub.com/brand/wofford-college',
      'low',
      'Candidate''s Adobe InDesign-hosted "Wofford College Athletics Brand Book 2023" (indd.adobe.com viewer) requires JS rendering; no extractable text or direct PDF resource URL could be recovered via curl or Wayback. Searched wofford.edu/woffordterriers.com for an accessible replacement and found none. Fell back to a reputable secondary color-code index (tier 4) that converges with teamcolorcodes.com on Old Gold #8A6E4B / Black #000000 ("Wofford College''s brand colors are Old Gold and Black"); dropped candidate''s near-black #282829 (unverifiable specific shade) in favor of plain black, and dropped candidate''s white (not corroborated anywhere).'
    ),
    (
      'marymount-university',
      '232706',
      array['#10069F']::text[],
      'https://marymount.edu/marymount.edu/media/Marketing/Marymount-Braning-Graphic-Style-Guide_final.pdf',
      'high',
      'Candidate''s ver1-6-20.pdf citation is dead; found the current (larger, newer) style-guide PDF linked from Marymount''s live Brand Guidelines page instead (both hosted at .../media/Marketing/). "Primary Color Palette / Primary: Marymount Blue ... HEX: #10069f"; Orange/Yellow/Light-Blue/Light-Gray/Dark-Gray/Black are all explicitly listed under "Secondary," and white does not appear anywhere in the palette at all. Dropped candidate''s mechanically-attached white -- unconfirmed and not part of any labeled row; kept the single confirmed primary.'
    ),
    (
      'university-of-pittsburgh-johnstown',
      '215284',
      array['#1C2957','#CDB87D']::text[],
      'http://www.communications.pitt.edu/Graphic-Standards.pdf',
      'high',
      'Candidate''s URL is dead; recovered via Wayback. University of Pittsburgh system-wide Graphic Standards PDF states: "RGB values for Pitt blue are R=28, G=41, B=87 and for Pitt gold are R=205, G=184, B=125 ... Hex codes are as follows: Pitt blue - 1c2957; Pitt gold - cdb87d" -- exact match to candidate''s two chromatic hexes; "one-color identity options include ... black, and reverse" -- black/white are one-color print fallbacks, not a third named color. Dropped candidate''s mechanically-attached white. UPJ is a regional campus of the same institution and uses the same system colors.'
    ),
    (
      'university-of-arkansas-at-pine-bluff',
      '106412',
      array['#000000','#E31837','#EEB310']::text[],
      'http://www.uapb.edu/sites/www/Uploads/Advancement/UAPB-Athletic%20Brand%20Identity%20Guidelines%20OCT-2014.pdf',
      'high',
      'Candidate''s URL is dead; recovered via Wayback. "Color Information" page: "* UAPB''s primary colors" table lists four swatches with explicit HTML hex each -- Black #000000, Yellow (PMS 124C) #EEB310, Red (PMS 186C) #E31837, White #FFFFFF -- all four literally labeled primary. Kept the 3 most representative within the max-3 limit (added the missing Red the candidate omitted, dropped White) to keep two clean chromatics plus a dark anchor.'
    ),
    (
      'franklin-and-marshall-college',
      '212577',
      array['#0035AD','#73CFFF','#FFFFFF']::text[],
      'https://www.fandm.edu/uploads/files/992378552837085212-f-m-athletics-identity-guide.pdf',
      'high',
      'Candidate''s live URL now 404s ("F&M Page Not Found"); recovered a full, undamaged PDF via a 2023 Wayback capture at the same path. "Primary Colors ... The official colors of the athletics logo are Diplomats blue (PMS 286) ... PMS 286 / Web hexadecimal (HTML) #0035AD", "light blue (PMS 284) ... #73CFFF", and "white ... #FFFFFF" -- all three candidate hexes confirmed exactly as stated.'
    ),
    (
      'university-of-mount-olive',
      '199069',
      array['#005F3E','#FEC057','#959484']::text[],
      'https://umo.edu/wp-content/uploads/2017/12/UMO_GraphicStandardsGuide_05.06.2014.pdf',
      'high',
      'Candidate''s URL is dead; recovered via Wayback. "OFFICIAL COLORS -- The official colors of the University of Mount Olive are green, yellow, and gray ... RGB: 0 95 62 / HEX: 005F3E ... RGB: 254 192 87 / HEX: FEC057 ... RGB: 149 148 132 / HEX: 959484." Corrected: candidate''s mechanically-attached white does not appear anywhere in this section -- the true third official color is gray (959484), not white; swapped it in.'
    ),
    (
      'hobart-william-smith-colleges',
      '191630',
      array['#472663','#FF6418']::text[],
      'https://www.hws.edu/offices/pdf/Hobart_Athletics_Brand_Standards.pdf',
      'high',
      'Candidate''s news/graphic-standards2015.pdf citation is dead with no Wayback capture (also 404 at the time it was archived). The combined-institution Logo/Identity page states only Pantone ("Orange & Purple ... Hobart shield. Green & White ... William Smith shield"), no domain-wide hex. Found the live Hobart Athletics Brand Standards PDF instead: "The Hobart Athletics primary colors ... Pantone 2607 C / Web 472663" and "Pantone 165 C / Web ff6418" -- exact match to candidate''s purple/orange. Dropped candidate''s mechanically-attached white -- the document states exactly two primary colors.'
    ),
    (
      'marywood-university',
      '213826',
      array['#1A5632','#FFFFFF','#F5A800']::text[],
      'https://www.marywood.edu/policy/handbooks/students/Marywood-Brand-Guidelines.pdf',
      'high',
      'Candidate''s citation is live and confirmed exactly. "Primary Palette ... These are our main brand colors" lists Marywood Green (HEX #1a5632), Bright White (HEX #FFFFFF), and Pacer Gold (HEX #F5A800) together as the primary set, distinct from a separate "Secondary" Mint Green row that follows. All three candidate hexes confirmed as-is.'
    ),
    (
      'curry-college',
      '165529',
      array['#654389']::text[],
      'https://www.curry.edu/assets/Documents/Curry-College-Brand-Standards.pdf',
      'high',
      'Candidate''s handbook.pdf citation is the Curry College Student Handbook (a code-of-conduct document with zero color content), not a brand guide -- wrong citation. Found Curry''s real Brand Standards PDF: "Curry College''s primary color is Curry Purple ... HEX #654389" -- substantially different from candidate''s guessed #462C8D. "Secondary colors include Teal Blue, Lime Green, Cool Grey, Rich Black, Dark Purple, Light Purple ... Neutral colors, like Black and White" are explicitly secondary/neutral, not primary. Kept the single confirmed primary purple only; dropped candidate''s white/black.'
    ),
    (
      'wheaton-college-massachusetts',
      '168281',
      array['#1274B8','#04857E']::text[],
      'https://wheatoncollege.edu/wp-content/uploads/2023/05/Wheaton_Color_Palette-MAR2023.pdf',
      'high',
      'Candidate''s wheatoncollegelyons.com citation is a generic Sidearm-CMS athletics page; its hex list mixes true brand colors with unrelated boilerplate shared across many schools'' Sidearm sites (the wrong-swatch trap this task warns about). Found Wheaton''s own live 2023 Brand Toolkit color-palette PDF instead: "Primary color pair ... Wheaton Blue (primary) ... Hex 1274b8" and "Green (secondary) ... Hex 04857E", explicitly the two-color "Primary color pair." Corrected candidate''s slightly-off blue (#1374BA) and dropped its mechanically-attached black/white -- added the real second primary color (green), which candidate omitted entirely.'
    ),
    (
      'roanoke-college',
      '233426',
      array['#872046','#001B74','#F0B52B']::text[],
      'https://www.roanoke.edu/documents/PR/BrandFAQ-web.pdf',
      'high',
      'Candidate''s roanokemaroons.com citation is a generic Sidearm-CMS page whose hex list (#872046 not among them) is boilerplate CSS shared across unrelated Sidearm sites -- not used. Found Roanoke''s own live Brand FAQ PDF instead: "COLOR PALETTE ... Roanoke Maroon / PMS 208 C / HEX 872046 ... Mandarin Yellow / PMS 7409 C / HEX F0B52B ... National Blue / PMS 662 C / HEX 001B74." None of candidate''s three guessed hexes were correct; corrected to all three of the document''s own named colors.'
    ),
    (
      'bates',
      '160977',
      array['#B30838','#231F20','#C4C6C8']::text[],
      'https://www.bates.edu/communications-marketing/files/2023/10/SDS_Bates_Athletics_Guide_2023.pdf',
      'high',
      'Candidate''s gobatesbobcats.com PDF is blocked by a Sidearm cookie-consent gate that both curl and Wayback only capture as an HTML shell, never the real PDF. Found the identical style guide re-hosted on bates.edu directly. "BATES BOBCATS COLOR INFORMATION": Bates Garnet RGB 179,08,56 (= #B30838, exact RGB-derived match, no Pantone-table guessing needed) confirms candidate; Bates Black RGB 35,31,32 (= #231F20); Bates Athletic Gray RGB 196,198,200 (= #C4C6C8, exact match). Corrected candidate''s mechanically-attached white to the real near-black official color.'
    ),
    (
      'mckendree-university',
      '147013',
      array['#522484','#C2A204']::text[],
      'https://www.mckendree.edu/offices/marketing/brand-standards-guide.pdf',
      'high',
      'Candidate''s mckbearcats.com citation is a Sidearm page whose CSS hexes don''t match the candidate at all -- not used. Found McKendree''s own live Brand Standards Guide PDF: "the two choices of pair colors to reproduce McKendree University purple and gold are Pantone 2617C (purple) and Pantone 457C (gold) ... for ... web" with RGB breakdowns R82/G36/B127 (= #522484) and R194/G162/B4 (= #C2A204). Corrected both of candidate''s hexes (which were in the right family but numerically off) and dropped candidate''s mechanically-attached white -- the document states exactly a two-color pair.'
    ),
    (
      'springfield-college',
      '167899',
      array['#862633','#FFFFFF']::text[],
      'http://springfield.edu/sites/default/files/inline-files/springfield-college-brand-guidelines.pdf',
      'high',
      'Candidate''s citation is live and confirmed exactly. "PRIMARY PALETTE ... #862633" (Maroon) paired with "WHITE ... #FFFFFF", explicitly the two-color primary palette (a separate 8-swatch "SECONDARY PALETTE" follows on the next page and was not used).'
    ),
    (
      'kenyon',
      '203535',
      array['#4B2E84','#8F80FF','#3F7C7C']::text[],
      'https://www.kenyon.edu/files/resources/brand-guides-brand-08-30-23.pdf',
      'high',
      'Candidate''s news-archive citation (about the Kenyon Owls mascot) has no color content at all -- wrong citation. Found Kenyon''s current (Aug 2023) Brand User Guide PDF: "PRIMARY" row lists three explicitly-labeled primary colors -- Kenyon Purple HEX #4B2E84 (confirms candidate), Kenyon Bright Purple HEX #8F80FF, and Quad Dark Green HEX #3F7C7C -- distinct from a following "BRIGHTS" and "NEUTRALS" row that includes candidate''s guessed white/gray (neither of which appears in the actual Primary or Neutral rows as given). Replaced candidate''s white/gray with the two other genuine primary colors.'
    ),
    (
      'the-college-of-wooster',
      '206589',
      array['#F8C42C','#0A0B09']::text[],
      'https://teamcolorcodes.com/college-of-wooster-fighting-scots-color-codes/',
      'low',
      'Candidate''s wooster.edu/mascot/ citation now redirects to the plain homepage with no color content. Wooster''s Marketing brand/style guides live behind an internal SharePoint login (confirmed via search); no public wooster.edu page states a hex. Fell back to a reputable secondary color-code index (tier 4): Gold #F8C42C / Black #0A0B09 / Maroon #B3252F. Kept only Gold+Black, matching the school''s own repeated public description ("our black and gold") -- the index''s third "Maroon" value is not corroborated anywhere in Wooster''s own prose, so dropped along with candidate''s white.'
    ),
    (
      'muhlenberg-college',
      '214175',
      array['#A41D36']::text[],
      'https://www.muhlenberg.edu/offices/communications/campusidentity/graphicidentityprogram/',
      'high',
      'Candidate''s citation is dead (404); recovered via Wayback. "Colors: The official colors of the College are PMS 201 Red and PMS 429 Gray. The official red of the College website is Hex code: #A41D36" -- confirms candidate''s red exactly. Gray has no hex/RGB stated anywhere on the domain (Pantone-only), so per the no-third-party-Pantone-conversion rule it was dropped rather than guessed; candidate''s mechanically-attached white also dropped (not mentioned at all). Kept the single confirmed chromatic.'
    ),
    (
      'claflin-university',
      '217873',
      array['#C64200','#590917']::text[],
      'https://www.claflin.edu/docs/default-source/communications-and-marketing/claflin-graphic-standards-manual.pdf',
      'high',
      'Candidate''s athletics quick-facts PDF citation is dead ("Runtime Error"); the live Brand Identity page links the same Graphic Standards Manual, which is also dead live but was recovered via Wayback. "The Claflin colors, Orange and Maroon, are best represented ... The RGB color combinations are Orange (R198, G66, B0) and Maroon (R89, G9, B23)" (= #C64200 / #590917, exact RGB-derived conversion, not a Pantone guess). None of candidate''s three guessed hexes (black/white/red-ish) were correct; corrected to the document''s own two named colors.'
    ),
    (
      'chaminade-university-of-honolulu',
      '141486',
      array['#0E20A4','#091058','#D9D9D6']::text[],
      'https://chaminade.edu/ucm/brand-center/',
      'high',
      'Candidate''s Sidearm-hosted media-guide PDF (S3 URL) returns an XML access-denied error, not a PDF. Found Chaminade''s live Brand Center page instead: "our primary color palette -- the go-to colors for branded communications: Chaminade Blue, Quicksilver Gray, Moonlight and Chaminade Rich Black," each with a stated hex (#0E20A4, #D9D9D6, #091058, #101820 respectively). None of candidate''s three guessed hexes were correct. Kept 3 of the 4 named primaries (Blue, Moonlight, Gray), dropping Rich Black to stay within the max. Derive-inks note: Blue and Moonlight are close enough in hue that deriveInks treats them as too-close and synthesizes a brighter blue for the B plate rather than using either stated hex directly -- expected deriver behavior given two similar navies, not a data error.'
    ),
    (
      'misericordia-university',
      '214069',
      array['#0067B1','#C4932A']::text[],
      'https://resources.finalsite.net/images/v1647879966/misericordia/wt5mkx1gjnht3q3kdbg9/misericordia_style_guide_2022.pdf',
      'high',
      'Candidate''s citation is live and downloadable. "PRIMARY ACADEMIC COLOR PALETTE -- Misericordia Blue (PMS 293) and Misericordia Gold (PMS 117) are the two primary colors for use on all academic material" with HEX 0067B1 and HEX C4932A. Corrected candidate''s slightly-off hexes (#0168B3/#FED105) to the document''s literal values and dropped candidate''s mechanically-attached white -- the academic primary palette is explicitly just the two named colors (a separate Athletic palette exists but the school-identity row is the academic one).'
    ),
    (
      'simmons-university',
      '167783',
      array['#003A70','#FFFFFF']::text[],
      'https://www.simmons.edu/brand/asset-library/color-palette',
      'high',
      'Candidate''s athletics.simmons.edu press-release citation redirects to a generic editorial style guide with no color content. Found Simmons'' live Brand Asset Library Color Palette page instead: "The official colors of Simmons are dark blue and pure white ... Our chief operating colors are Simmons dark blue and pure white ... they carry the strongest brand equity" with Dark Blue HEX/HTML 003A70 and White HEX/HTML FFFFFF. Corrected candidate''s blue (#0A416A) and dropped candidate''s yellow -- the page separately lists Medium Blue, Light Blue, Black, and (in an Accent table) Medium/Dark Yellow, none of which are part of the stated "chief operating" primary pair.'
    ),
    (
      'assumption-university',
      '164562',
      array['#004B87','#000000']::text[],
      'https://www.assumption.edu/wp-content/uploads/2024/03/assumption_guidelines_9.27.2161095.pdf',
      'high',
      'Candidate''s assumptiongreyhounds.com citation is dead. Found Assumption''s current (v2.0) Brand Identity Guidelines PDF instead: "PRIMARY COLORS" section lists exactly two swatches -- Pantone 301 (HEX #004B87) and Pantone Black (HEX #000000) -- distinct from a following "SECONDARY COLORS" section (Gold/Cyan/Orange/Teal/Gray/Green). Corrected candidate''s blue (#005B99) and dropped candidate''s white/gray, which are not part of the primary pair.'
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
