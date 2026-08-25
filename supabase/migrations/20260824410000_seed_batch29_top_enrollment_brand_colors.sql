-- Batch 29 of brand-color scouting: verify/confirm pass over 14 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
-- This is the FINAL batch closing out the Wikipedia-crosswalk candidate
-- queue -- after this batch, no further candidates remain in the backlog
-- that fed batches 1-29.
--
-- Confirmed candidates exactly or near-exactly as given: westminster-
-- college-mo (live athletic-brand-standards PDF's own 'Official Colors'
-- table states navy/light-blue/white hex directly; white kept because the
-- document explicitly names it as one of only three Official Colors, not a
-- mechanically-appended neutral), thomas-college (candidate's dead /assets/
-- URL relocated to a live 2024-hosted copy of the same Visual Identity
-- Toolkit; confirmed candidate's exact 3-of-4 selection from the document's
-- four-color Primary Color Palette), st-joseph-s-college-of-nursing (PDF
-- 'COLOR SPECIFICATIONS' table states navy/white/gold hex exactly matching
-- candidate).
--
-- Corrected (hex, color set, or source did not match the school's own
-- current official source): pfeiffer-university (candidate's white was
-- never one of the three stated 'University Colors'; corrected to the
-- document's actual Pantone-429 gray, RGB converts exactly to #A4A9AD),
-- lyon-college (2017 Brand Logo Guide citation is dead; found the college's
-- current Sept-2025 Branding Guide, whose 'OFFICIAL BRAND COLOR PALETTE'
-- gives exact navy+crimson hex and explicitly marks gold and light-blue as
-- accent-only, not primary -- both hexes and the color set corrected;
-- dropped candidate's white), lagrange-college (candidate's live citation
-- 404s; an Internet Archive snapshot of that exact URL confirms it
-- formerly stated red+black as the two LaGrange College colors with exact
-- hex; the college's current live Brand Book supersedes with a four-color
-- equal-weight palette in two rows, Red/Near-Black on top -- kept that top
-- pairing, corrected black to the current near-black shade, dropped
-- candidate's white and the second-row grey/yellow), wheeling-university
-- (candidate's homepage citation has no color content; found the site's own
-- Quick Facts page stating the two-color 'Red & White', with red hex
-- recovered from the same domain's site_colors JSON; dropped candidate's
-- near-black, not part of the two-color statement), spalding-university
-- (candidate's citation 404-redirects to a generic staff page; found the
-- athletics site's own live 'Brand & Style Guide' page stating exact
-- hex for its two Official Colors; dropped candidate's white),
-- saint-elizabeth-university (malformed 'ht' URL prefix stripped; Quick
-- Facts names three colors including white explicitly, 'Navy Blue, White
-- and Gray' -- navy hex recovered from site_colors JSON, no locatable hex
-- for the named Gray anywhere on any Saint Elizabeth domain so it was
-- dropped; kept the explicitly-named white), maranatha-baptist-university
-- (candidate's citation 404s; found the current live Quick Facts page
-- naming three colors, 'Navy (primary), Gold, Crimson', no white at all --
-- navy+gold hex recovered from site_colors JSON matching the labeled
-- primary/secondary pair; dropped candidate's fabricated white and the
-- named-but-hex-less Crimson), sweet-briar-college (candidate's citation's
-- own prose calls out pink+green as core with navy as an accent, but the
-- only hex values configured anywhere on any official Sweet Briar domain
-- are navy+pink; no official green hex exists anywhere and two third-party
-- indexes disagreed with each other on one, so green was not usable --
-- corrected pink by one digit, swapped in the on-domain navy for the
-- ungrounded green, dropped white), salem-college (candidate's citation
-- 404-redirects since the athletics domain moved; corrected gold by one
-- digit to the new domain's own site_colors JSON, blue confirmed, white
-- dropped as unevidenced), principia-college (candidate's citation is a
-- 404 that resolves to 'School Logos - The Principia', i.e. Principia
-- SCHOOL, the K-12 division -- a wrong-institution trap inside the shared
-- principia.edu dual-campus domain; recovered Principia COLLEGE's actual
-- Dual-Campus Visual Identity Guide PDF whose 'PRIMARY COLOR PALETTE'
-- states exact blue+gold hex; corrected gold, confirmed blue, dropped
-- candidate's white as outside the stated primary palette).
--
-- Fell to low confidence after official search failed: mitchell-college
-- (candidate's citation has zero color content; mitchellathletics.com
-- quick-facts 404s; the college's own hub.mitchell.edu/style-guide page has
-- a Colors section with no configured swatches behind it; no brand PDF
-- found on any Mitchell domain -- fell back to a reputable secondary color
-- index for a single red hex, dropping its unevidenced white/black).
--
-- See data/brand-colors/batch-29-2026-08-24.jsonl for the full per-school
-- record. No rows were left null in this final batch -- every school had a
-- usable source once dead links, a wrong-institution citation, and a
-- relocated athletics domain were worked around; one row
-- (mitchell-college) landed at low confidence for lack of any official
-- on-domain hex.

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
      'pfeiffer-university',
      '199306',
      array['#FFC627', '#A4A9AD', '#000000']::text[],
      'https://www.pfeiffer.edu/wp-content/uploads/2021/10/Pfeiffer_identity_guide_6.2.14.pdf',
      'high',
      'Candidate PDF confirmed live and extracts cleanly. ''The University Colors'' section states Web RGB Yellow R:255 G:198 B:39 (= #FFC627, matches candidate exactly) and Gray R:164 G:169 B:173 (= #A4A9AD), with the wordmark otherwise reproduced ''only in the University colors shown at right, or in black or white'' -- the three swatches shown are Pantone 123 (yellow), Pantone 429 (gray), and Black. Corrected: candidate''s white was never one of the three University Colors on this page; replaced with the document''s actual stated gray, and kept black which the swatch row explicitly includes alongside the two Pantone colors.'
    ),
    (
      'lyon-college',
      '106342',
      array['#001632', '#851C1A']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/lyonscots.com/documents/2025/9/22/branding_guide_2025.pdf',
      'high',
      'Candidate''s 2017 Brand Logo Guide citation is dead (redirects to a cookie-consent shell). Found Lyon''s current, live September 2025 Branding Guide (linked from the same lyonscots.com documents system; had to resolve the actual S3-hosted file since the viewer page itself isn''t text-extractable). ''OFFICIAL BRAND COLOR PALETTE'': Navy PANTONE #289C WEB #001632, Crimson PANTONE #201C WEB #851C1A, Gold PANTONE #116C WEB #FFCF01, Light Blue PANTONE #298C WEB #3FB3E2 marked ''*ACCENT COLOR ONLY''; prose separately states ''Lyon Gold is not part of the Athletic Color Palette and should be used only as an accent color'' and instructs limiting Crimson/Light Blue usage while Navy carries the page. Corrected both hexes to the document''s exact current values (candidate''s navy and crimson were both close guesses, not exact); dropped candidate''s white (absent from the palette) and did not add Gold/Light Blue since the document itself frames both as accent-only, not primary.'
    ),
    (
      'thomas-college',
      '161563',
      array['#B52C1F', '#FFFFFF', '#151515']::text[],
      'https://www.thomas.edu/wp-content/uploads/2024/08/Visual-Identity-Toolkit-2023.pdf',
      'high',
      'Candidate''s /assets/ URL 404s; found the same document at its current live path on the school''s own domain. ''Primary Color Palette'': Terrier Pride Red #b52c1f (''the main color in the Thomas College Identity''), Graphite #333333, Charcoal #151515, White -- four colors listed together under one Primary Color Palette heading. Confirmed candidate''s exact 3-of-4 selection (red, white, charcoal); dropped the document''s fourth primary color (graphite) to stay within the 3-hex cap, consistent with red being explicitly called out as the main/hero color.'
    ),
    (
      'westminster-college-mo',
      '179946',
      array['#003767', '#79BDE8', '#FFFFFF']::text[],
      'https://www.wcmo.edu/marketing/brand-standards/files/athletic-brand-standards.pdf',
      'high',
      'Candidate PDF confirmed live and extracts cleanly. ''The athletic brand standard includes three color options: navy, light blue and white'' -- ''Official Colors'' table gives PANTONE 540 HEX #003767, PANTONE 292 HEX #79BDE8, and White HEX #FFFFFF, and separate prose instructs using ''all three official colors'' on uniforms. Corrected candidate''s approximate navy (#002F56) and light blue (#6EB1DF) to the document''s exact stated hex; kept white since it is explicitly one of only three named Official Colors here, satisfying the white-as-labeled-primary exception.'
    ),
    (
      'lagrange-college',
      '140234',
      array['#C4203C', '#0C0C0C']::text[],
      'https://www.lagrange.edu/faculty-and-staff/_images/LaGrange%20Brand%20Book%20V02.pdf',
      'high',
      'Candidate''s color-palette.html citation 404s on the live domain (confirmed via curl and browser); an Internet Archive snapshot from Jan 2026 of that exact URL shows it formerly stated ''Pantone Matching System: PMS 200 Red ... Hexadecimal value: #C4203C'' and ''PMS Black ... Hexadecimal value: #000000'' as the LaGrange College color-matching pair. The college''s current, live LaGrange College Brand Book supersedes it with a ''COLOR PALETTE'' of four co-equal swatches in two rows -- Red #C4203C / Near Black #0C0C0C (top row) and Light Grey #F2F2F2 / Yellow #FCAF17 (second row). Kept the top-row Red + Near Black pairing, consistent with the older page''s explicit two-color Red+Black framing (near-black replacing pure black as the shade refined in the newer document); dropped candidate''s white (never appears in either source) and the second-row grey/yellow to stay within the no-neutral-append spirit and the 2-color historical pairing.'
    ),
    (
      'wheeling-university',
      '238078',
      array['#E80532', '#FFFFFF']::text[],
      'https://wucardinals.com/sports/2011/11/26/GEN_1126115610.aspx',
      'medium',
      'Candidate''s homepage citation had no color content; found and read the site''s own ''Athletics Quick Facts'' page instead, which states ''Colors: Red & White'' (two named colors, no third). Red hex sourced from the same domain''s Sidearm site_colors JSON (primary_background #E80532); no white hex is ever stated (trivially #FFFFFF). Corrected candidate''s approximate red (#E31937, not found on-domain); dropped candidate''s near-black third color, not part of the page''s two-color statement (site_colors secondary_background is black but is not named in the prose as an official color).'
    ),
    (
      'spalding-university',
      '157757',
      array['#1B449C', '#FFD200']::text[],
      'https://spaldingathletics.com/sports/2026/7/14/brand-style-guide.aspx',
      'high',
      'Candidate''s citation URL 404-redirects to a generic Athletics Communication staff page whose own quick facts only say ''Colors: Blue and Gold'' with no hex. Found the site''s own live ''Brand & Style Guide'' page (linked from the same site''s nav) which states directly: ''Official Colors: Blue - #1B449C, Gold - #FFD200.'' Corrected candidate''s approximate hexes (#2B338C, #FFD103) to these exact stated values; dropped candidate''s white, absent from the two named Official Colors.'
    ),
    (
      'saint-elizabeth-university',
      '186618',
      array['#003366', '#FFFFFF']::text[],
      'https://seueagles.com/sports/2014/10/21/QuickFacts.aspx',
      'medium',
      'Stripped the stray ''ht'' prefix from the given URL; page confirmed live. Its own Quick Facts state ''Colors: Navy Blue, White and Gray'' -- three named colors including white explicitly as one of only three. Navy hex sourced from the same domain''s Sidearm site_colors JSON (primary_background #003366, matching ''Navy Blue''); no hex or RGB for ''Gray'' was found anywhere on seueagles.com or the university''s main steu.edu marketing/communications page after a targeted search (site_colors secondary_background is a second blue, not the named gray). Corrected candidate''s guessed navy (#1D2858) and dropped candidate''s blue-gray third color (#C5D0D6, not evidenced); kept white since it is explicitly one of the three named colors; dropped Gray for lack of any locatable hex despite being named in prose.'
    ),
    (
      'maranatha-baptist-university',
      '239071',
      array['#041E41', '#F5C400']::text[],
      'https://mbusabercats.com/sports/2023/9/11/information-quick-facts.aspx',
      'medium',
      'Candidate''s citation URL 404s; found the site''s current live Quick Facts page instead, which states ''Colors: Navy (primary), Gold, Crimson'' -- three named colors, no white at all. Navy and Gold hex sourced from the same domain''s Sidearm site_colors JSON (primary_background #041E41 exactly matching candidate''s navy; secondary_background #F5C400), consistent with Navy being labeled the primary color and Gold the paired secondary. Corrected candidate''s gold (#F0C415, close but not exact); dropped candidate''s white as fabricated -- not among the three named colors; dropped Crimson, named in prose but with no locatable hex anywhere on the domain.'
    ),
    (
      'sweet-briar-college',
      '233718',
      array['#002A4B', '#ED2B74']::text[],
      'https://vixenathletics.com/news/2020/1/14/general-sweet-briar-launches-new-suite-of-athletics-marks.aspx',
      'medium',
      'Candidate''s citation confirmed live. The article''s own prose frames the identity as ''the bold use of Sweet Briar''s pink and green ... complemented by strong strokes and accents of midnight blue'' -- i.e. pink+green as core, navy as accent. However, the only hex values actually configured anywhere on any official Sweet Briar domain (checked vixenathletics.com''s Sidearm site_colors JSON, sbc.edu''s branding and style-guide pages, and sbc.edu''s own CSS, none of which publish a green hex) are primary_background #002A4B (navy) and secondary_background #ED2B74 (pink, closely matching candidate''s pink). Two independent third-party team-color indexes disagreed with each other on a green hex (#72B543 vs #79BC43), so no green was usable per the never-guess rule. Corrected candidate''s pink by one digit and replaced candidate''s unfounded green with the only other on-domain configured color (navy); dropped candidate''s white, not evidenced anywhere.'
    ),
    (
      'salem-college',
      '199607',
      array['#004C97', '#FFD000']::text[],
      'https://salemcollegeathletics.com/',
      'medium',
      'Candidate''s SID_Downloads citation 404-redirects (the athletics domain itself moved to salemcollegeathletics.com); no dedicated quick-facts or brand-guide page with prose color names was found on the new domain after search, but the site''s own Sidearm site_colors JSON declares primary_background #004C97, secondary_background #FFD000, consistent with third-party listings of Salem''s colors as blue/royal and gold. Corrected candidate''s gold by one digit (#FFD100 -> #FFD000) to match the site''s actual configured value; blue confirmed exact; dropped candidate''s white, not evidenced in the site''s own configured colors.'
    ),
    (
      'mitchell-college',
      '129774',
      array['#D52331']::text[],
      'https://teamcolorcodes.com/mitchell-college-mariners-color-codes/',
      'low',
      'Candidate''s mitchell.edu/athletics/ citation is live but is a generic landing page with zero color content. Searched further: mitchellathletics.com''s quick-facts/information pages 404; hub.mitchell.edu/style-guide/ has a ''Colors: Primary / Secondary / Tertiary / Accent'' section but is an unconfigured template page with no rendered swatches or CSS values behind those labels; no official brand or visual-identity PDF was located on any Mitchell domain despite search. Fell back to a reputable secondary color index listing Mitchell Mariners red as #D52331 (with white/black also listed, but neither is corroborated by any official source, so not added). Low confidence: hex sourced entirely from a third-party index after official search failed; kept only the single chromatic value rather than guess at a pairing.'
    ),
    (
      'principia-college',
      '148016',
      array['#102B51', '#B58D50']::text[],
      'https://resources.finalsite.net/images/v1634764274/principiacollegeedu/ijdajasfyflj072ondwl/PrincipiaDualCampusVisualIdentityGuide.pdf',
      'high',
      'Candidate''s citation URL is a 404 on the live domain -- and when resolved via a nearby working URL turned out to be ''School Logos - The Principia,'' i.e. Principia SCHOOL (the K-12 division), not Principia COLLEGE (IPEDS 148016), a wrong-institution trap inside the shared principia.edu dual-campus site. Located Principia''s actual ''Dual-Campus Visual Identity Guide'' PDF (hosted on the college''s asset CDN, referenced from principiacollege.edu/marketing/resources) whose ''PRIMARY COLOR PALETTE'' states Principia Blue PMS 295C HEX #102b51 and Principia Gold PMS 872+Metallic HEX #b58d50 explicitly, framed as the primary palette distinct from neutral/secondary colors. Corrected candidate''s gold (#B5985A, not the document''s value); blue essentially confirmed (#102B52 vs. document''s #102B51); dropped candidate''s white, not part of the stated Primary Color Palette.'
    ),
    (
      'st-joseph-s-college-of-nursing',
      '195191',
      array['#03205B', '#FFFFFF', '#F9B826']::text[],
      'https://www.sjny.edu/files/images/sjny_standards_guide.pdf',
      'high',
      'Candidate PDF confirmed live and extracts cleanly. ''COLOR SPECIFICATIONS'' table states Colors: PMS 281 Hex #03205B, White Hex #FFFFFF, PMS 124 (coated paper) Hex #F9B826, PMS 7406 (uncoated paper) Hex #F1C418 -- the last two being the same yellow for different paper stocks. Confirmed candidate''s exact selection of navy, white, and the coated-paper yellow (#F9B826); the uncoated-paper alternate yellow was not added to stay within the 3-hex cap.'
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
