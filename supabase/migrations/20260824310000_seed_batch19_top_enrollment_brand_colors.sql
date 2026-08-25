-- Batch 19 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a dropped
-- mechanically-attached white/reorder (hex matched the official source
-- verbatim once a live copy was located): alcorn-state-university
-- (purple/gold, exact hex match on the official Graphic Standards Manual;
-- white dropped, not a stated hex), southwest-minnesota-state-university
-- (brown/gold, exact hex match on the official Brand Guide; white dropped),
-- utica-university (navy/orange, exact HTML-hex match on the official
-- Style Guide's "Official Colors" section; white dropped), emporia-state-
-- university (black/gold, exact hex match, "the official... colors are
-- Black + Gold"; white dropped), the-university-of-findlay (orange/black,
-- RGB-stated match on the official Athletic Style Guide; white dropped),
-- messiah-university (navy/white, exact hex match, both explicitly labeled
-- "PRIMARY" on the current color-palette page).
--
-- Wrong-swatch / wrong-tier / stale corrections (candidate hex did not
-- match the school's own current official source):
-- vassar-college (candidate's blue/orange were generic Sidearm template
-- boilerplate colors, not Vassar-specific; corrected to the official Brand
-- Guidelines' actual Lead pair, Vassar Burgundy #951829 + Vassar Dark
-- Burgundy #641A2B -- white dropped, absent from the palette entirely),
-- university-of-detroit-mercy (candidate's red/blue were pre-2024 values;
-- the current institution-wide Visual Identity Standards explicitly says
-- "As of 2024, all color codes have been redefined" -- corrected to UDM
-- Red #A70A43 / UDM Blue #002C77; white dropped, not in either palette
-- tier), norwich-university (candidate's old maroon/tan predate a 2023
-- rebrand; corrected to the current Brand Guidelines' Primary pair,
-- Norwich Red #8A2424 + White), georgia-southwestern-state-university
-- (candidate's blue/gold did not match; corrected to the official Style
-- Guide's stated "PRIMARY COLORS" Blue #00205B / Gold #C69214), colby
-- (candidate's blue was pulled from a "Dare Northward" capital-campaign
-- sub-palette, not the base identity; corrected to the base guide's
-- actual "Colby Blue is the primary color used for all branding" #002169
-- + White), furman-university (candidate's third value, an unsupported
-- gray, replaced -- official guide names exactly two Primary colors,
-- Furman Purple #582C83 + Furman White, with the gray and midnight-purple
-- shades being Secondary only), point-park-university (candidate's
-- black+gold pairing is not supported by any primary/official 2-3-color
-- statement; the guide treats only PMS 7496 green as the identity color,
-- with a 5-color "Supplemental" accent palette explicitly framed as
-- non-primary -- reduced to the single sourced green #6D8D23), dickinson-
-- college (candidate's stated hex did not match the document's own RGB;
-- corrected to the RGB-derived #D3232D, keeping white+black since the
-- guide names exactly those 3 colors as the complete permitted set),
-- shawnee-state-university (candidate's blue/gray did not match the
-- guide's own stated RGB for SSU blue 281 / gray 424; corrected to the
-- RGB-derived #003E7E / #7E8082), pennsylvania-state-university-penn-
-- state-altoona (candidate's navy/white pair was correct but incomplete;
-- expanded to include the third literally-named Primary color, Beaver
-- Blue #1E407C, from the university-wide Penn State Brand Book that
-- governs all campuses including Altoona), pacific-lutheran-university
-- (candidate's white dropped -- the brand page names exactly "black and
-- gold" as its first two colors; gold hex corroborated via the same
-- page's own CSS, medium confidence), stetson-university (candidate's
-- black dropped and green retained after resolving a real conflict:
-- third-party sources disputed whether #006747 belongs to Stetson or USF;
-- the official gohatters.com site's own color configuration explicitly
-- declares "primary_background":"#006747", resolving it in the
-- candidate's favor -- medium confidence, site-config evidence not a
-- printed statement), hawaii-pacific-university (candidate's white
-- dropped -- current hpu.edu/brand page's "Primary Brand Colors" names
-- exactly HPU Teal #007298 + HPU Lt Teal #71B1C8, both confirmed exact),
-- university-of-maryland-eastern-shore (reduced to the single
-- independently-confirmable hex, Maroon #651D32 via on-domain CSS;
-- candidate's grey #888B8D appears nowhere on-domain and the palette
-- graphic is image-only, so white/grey were not guessed -- medium
-- confidence).
--
-- Left null (no usable on-domain hex/RGB found after a documented search;
-- see data/brand-colors/batch-19-2026-08-24.jsonl for full per-school
-- detail): st-catherine-university (candidate PDF 404s, no public brand
-- page found), le-moyne-college (candidate PDF now a dead Sidearm
-- landing page, official "Official Colors" page is login-walled),
-- north-central-college (graphic standards are login-walled on
-- CardinalNet), university-of-mary (candidate PDF 404s, no public brand
-- page found), dallas-baptist-university (candidate PDF now a dead
-- Sidearm landing page, no public brand page found), flagler-college
-- (current branding portal is a pure client-side Canto DAM embed with no
-- extractable text), shepherd-university (current brand-standards page is
-- an image-only Issuu flipbook embed, cannot verify without eyedropping),
-- trine-university (candidate citation 404s, no public brand page found),
-- university-of-charleston (candidate PDF 404s, no public brand page
-- found; this is University of Charleston, WV, IPEDS 237312, confirmed
-- distinct from College of Charleston, SC).
--
-- Every populated row was run through the production deriveInks()/
-- glyphInks() (web/src/lib/derive-inks.ts) via a throwaway vitest case
-- before finishing (deleted, not committed). All 21 populated rows produce
-- their own derived plates (house=false) -- no school in this batch loses
-- its chromatic primary to the house forest/ochre fallback, including the
-- single-chromatic-hex rows (point-park-university, university-of-
-- maryland-eastern-shore) whose sole brand color anchors both plates via
-- the deriver's single-ink rule.
-- See data/brand-colors/batch-19-2026-08-24.jsonl for the full per-school
-- record, including the nine null entries.

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
      'east-central-university',
      '207041',
      array['#000000','#FFFFFF','#FF5200']::text[],
      'https://www.ecok.edu/sites/default/files/2025-05/Identity%20Standards%2024-25%2010.29.24.pdf',
      'high',
      'Candidate''s issuu.com citation 404s (doc removed); recovered the current (2024-25) official Identity Standards PDF directly from ecok.edu. Text states "ECU''s orange is specific: HEX: FF5200" and "The colors of black, white and orange (Pantone 1655)... are interchangeable." Confirms candidate''s three hexes exactly as given.'
    ),
    (
      'vassar-college',
      '197133',
      array['#951829','#641A2B']::text[],
      'https://www.vassar.edu/sites/default/files/2021-06/Vassar_StyleGuidelines.pdf',
      'high',
      'Candidate''s vanguardlions.com citation is a generic Sidearm quick-facts template page whose hexes are cross-school Sidearm boilerplate, not Vassar-specific -- a wrong-swatch pull. Official Vassar Brand Guidelines PDF: "The lead colors for the Vassar College brand are Vassar Burgundy and Vassar Dark Burgundy... foundation of all Vassar College communications." Vassar Burgundy HEX #951829 (matches candidate''s first value), Vassar Dark Burgundy HEX #641A2B. Candidate''s white and #63666A do not belong to this Lead pair -- white is absent from the palette entirely, and #63666A is the Secondary "Dark Gray." Corrected to the documented Lead pair.'
    ),
    (
      'university-of-detroit-mercy',
      '169716',
      array['#A70A43','#002C77']::text[],
      'https://www.udmercy.edu/faculty-staff/marcom/_files/Detroit_Mercy_Brand_Guide.pdf',
      'high',
      'Candidate''s detroittitans.com 2016 athletics PDF now serves a generic Sidearm landing page. Found the current institution-wide Visual Identity Standards guide on udmercy.edu instead, which explicitly flags: "As of 2024, all color codes have been redefined... Previous color mixes must be updated." PRIMARY COLORS: UDM Red HEX #A70A43 (RGB 167/10/67), UDM Blue HEX #002C77 (RGB 0/44/119). Candidate''s stale pre-2024 values (#A6093D/#002D72) are close but not exact matches to the current spec; corrected. White is not listed in the primary or secondary palette -- dropped.'
    ),
    (
      'norwich-university',
      '230995',
      array['#8A2424','#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/norwichathletics.com/documents/2024/10/9/NWU001_Norwich_Brand_Guidelines_2023_1122_Final.pdf',
      'high',
      'Candidate''s norwich.edu/logo citation 404s. Recovered the current (Nov 2023) Norwich Brand Guidelines, a rebrand that superseded the old maroon/tan identity the candidate''s hex reflected. Text: "1. PRIMARY -- NORWICH RED #8A2424, WHITE #FFFFFF... The primary color palette makes ample use of Norwich Red and White." Candidate''s #87212E/#907C4B (old maroon/tan) match nothing in the current 3-tier palette; substantially corrected to the current stated Primary pair.'
    ),
    (
      'georgia-southwestern-state-university',
      '139764',
      array['#00205B','#C69214']::text[],
      'https://www.gsw.edu/university-relations/files/gsw-style-guide.pdf',
      'high',
      'Candidate''s HurricanesLogoManual.pdf citation 404s; found the current GSW Style Guide linked from gsw.edu/university-relations/brand-resources. "PRIMARY COLORS": PMS 281C Blue HEX 00205B (RGB 0,32,91), PMS 1245C Gold HEX C69214 (RGB 198,146,20). Candidate''s #1C3F7B/#C69E29 match neither; corrected. A separate "GSW Athletics" blue/gold pair exists for athletics letterhead only -- the institutional Primary Colors pair was used as the more general statement.'
    ),
    (
      'colby',
      '161086',
      array['#002169','#FFFFFF']::text[],
      'https://www.colby.edu/wp-content/uploads/2024/10/Colby-Brand-Guide-2024.pdf',
      'high',
      'Candidate''s 2015-era colby.edu citation 403s; recovered the current Oct-2024 Colby Brand Guide from the same domain. Main identity section: "Colby Blue is the primary color used for all branding, including logos and athletics... always used on a white background" -- HEX #002169. Candidate''s #002878 is instead pulled from a separate "Dare Northward Colors" capital-campaign sub-palette (its own distinct "Colby Blue (Digital)" swatch) -- a wrong-section pull, not the institution''s actual primary blue. Corrected to the base-identity #002169 + White (white is explicitly paired with Colby Blue as the only 2 primaries in both the base identity and the campaign section). Colby Gray dropped, accent-only.'
    ),
    (
      'pacific-lutheran-university',
      '236230',
      array['#000000','#FBBA37']::text[],
      'https://www.plu.edu/brand/',
      'medium',
      'Citation resolved. Page states in running text: "Black and gold will always be the first two colors of our brand and these are the specific color codes we''ll use for our brand," but the actual codes are shown only as a swatch image (not eyedropped, per policy). The same page''s own CSS uses #FBBA37 literally as the gold styling color tied to this statement (on-domain, same page) -- matches candidate''s gold exactly. Black is trivially #000000. Medium confidence because the gold hex is corroborated via on-page CSS rather than printed as literal swatch text. White (candidate''s middle value) dropped -- the page names exactly "black and gold" as the first two colors, not three.'
    ),
    (
      'hawaii-pacific-university',
      '141644',
      array['#007298','#71B1C8']::text[],
      'https://www.hpu.edu/brand/visual-language.html',
      'high',
      'Candidate''s hpusharks.com PDF now serves a generic Sidearm landing page. Found the current hpu.edu/brand/visual-language.html page instead: "Primary Brand Colors" -- "HPU Teal: Pantone 7468, R:0 G:113 B:153, #007298" and "HPU Lt Teal: Pantone 7458, R:113 G:177 B:200, #71B1C8." Matches candidate''s first and third hexes exactly. White (candidate''s middle value) is not listed among the Primary Brand Colors -- dropped.'
    ),
    (
      'university-of-maryland-eastern-shore',
      '163338',
      array['#651D32']::text[],
      'https://www.umes.edu/about/brand-colors/',
      'medium',
      'Candidate''s wwwcp.umes.edu citation redirected to the live umes.edu Brand Guidelines nav; followed the linked Brand Colors subpage. Text: "Maroon, grey, white and black are the university''s primary colors." Maroon HEX #651D32 confirmed via the site''s own theme CSS (header/footer background), matching candidate exactly. The actual color swatches on the page are an image only -- no text/CSS hex for grey (candidate''s #888B8D appears nowhere on-domain) or a deliberate white. Rather than guess, reduced to the one hex independently confirmable on-domain: maroon.'
    ),
    (
      'furman-university',
      '218070',
      array['#582C83','#FFFFFF']::text[],
      'https://www.furman.edu/wp-content/uploads/2019/Brand-Standards-Guide.pdf',
      'high',
      'Candidate''s furman.edu/sites/.../graphic-design-guide.aspx citation 404s; found the current Brand Standards Guide PDF on the same domain. "COLOR PALETTE -- UNIVERSITY COLORS... ALL COMMUNICATIONS SHOULD USE FURMAN PURPLE AND FURMAN WHITE, WITH FURMAN MIDNIGHT PURPLE AND FURMAN GRAY AS SECONDARY COLORS." PRIMARY: Furman Purple HEX 582C83 (matches candidate exactly), Furman White. Candidate''s third value (#A7A8AA) does not match the documented Secondary gray (#54585A) and gray isn''t Primary anyway; corrected to the documented Primary pair only.'
    ),
    (
      'pennsylvania-state-university-penn-state-altoona',
      '214689',
      array['#001E44','#1E407C','#FFFFFF']::text[],
      'https://brand.psu.edu/design-toolkit/design-essentials',
      'high',
      'Citation resolved and text-extracted cleanly (university-wide Penn State Brand Book, which governs all campuses including Altoona; no separate Altoona-specific palette exists). "Design Essentials // Brand Palette -- Primary Nittany Navy HEX: #001E44; Beaver Blue HEX: #1e407c; White out HEX: #ffffff... Secondary Pugh Blue HEX: #96BEE6." Candidate''s 2-hex pair (Navy+White) matched exactly but omitted the third literally-named Primary color (Beaver Blue); expanded to all three stated Primary colors.'
    ),
    (
      'alcorn-state-university',
      '175342',
      array['#512D6D','#CC8A00']::text[],
      'https://www.alcorn.edu/wp-content/uploads/2023/02/ASU_Graphic_Standards_Manual_122020-1.pdf',
      'high',
      'Citation resolved and text-extracted cleanly. "HEXADECIMAL COLORS -- Gold: #CC8A00, Purple: #512D6D." Matches candidate''s purple and gold exactly (reordered purple-first per the doc''s own phrasing). Candidate''s white dropped -- black/white are only mentioned as acceptable backgrounds/reversals, not stated hex brand colors.'
    ),
    (
      'point-park-university',
      '215442',
      array['#6D8D23']::text[],
      'https://www.pointpark.edu/about/admindepts/media/news/ppu_styleguide2.1_12_4_09.pdf',
      'high',
      'Citation resolved and text-extracted cleanly. The identity section repeatedly states "the Point Park University logotype should always appear in Pantone 7496 (green) to maintain brand identity" with no second color ever named as co-primary. A later "Supplemental Color Palette" section explicitly frames 5 additional colors (gold #FDB813, blue #008FC5, red #C41230, orange #F4911E, plus green) as secondary/energizing accents, not primary/official. Candidate''s black+gold pairing is unsupported by any primary statement; reduced to the one color the guide treats as the identity color, green #6D8D23 (matches candidate''s first value).'
    ),
    (
      'southwest-minnesota-state-university',
      '175078',
      array['#3A1807','#BCAA71']::text[],
      'https://www.smsu.edu/resources/webspaces/administration/communicationsmarketing/brand/smsu_brandguide_may2020.pdf',
      'high',
      'Citation resolved and text-extracted cleanly. "SMSU BROWN HEX #3a1807... SMSU GOLD HEX #bcaa71... Brown and gold are SMSU''s primary colors." Matches candidate''s first and third hexes exactly. Candidate''s white dropped -- the guide states only brown (primary) and gold (secondary), no white.'
    ),
    (
      'stetson-university',
      '137546',
      array['#006747','#FFFFFF']::text[],
      'https://gohatters.com/',
      'medium',
      'Candidate''s gohatters.com/pdf1/134128.pdf citation 404s; no institution-wide style guide with hex found on stetson.edu. A Stetson-Law-specific PDF gives a distinctly different green (#339933) -- a different sub-brand, not used. Third-party sites disagree with each other and flag #006747 as possibly a USF color. However, the official gohatters.com domain''s own site configuration explicitly declares "primary_background":"#006747" in its site_colors JS object and uses it as the page''s theme-color meta -- on-domain corroboration resolving the conflict in the candidate''s favor. White kept as the paired primary_text color from that same config; candidate''s black dropped, not present anywhere in the site''s color config. Medium confidence: site-configuration evidence, not a printed "official colors are..." statement.'
    ),
    (
      'utica-university',
      '197045',
      array['#0C223F','#E75200']::text[],
      'https://www.utica.edu/instadvance/marketingcomm/Utica_StyleGuide_FINAL.pdf',
      'high',
      'Citation resolved and text-extracted cleanly. "Official Colors -- PANTONE 289... HTML 0c223F... PANTONE 166... HTML e75200." Matches candidate''s first and third hexes exactly. Candidate''s white dropped -- the "Official Colors" section names exactly these two, no white.'
    ),
    (
      'dickinson-college',
      '212009',
      array['#D3232D','#FFFFFF','#000000']::text[],
      'https://www.dickinson.edu/download/downloads/id/10641/graphic-identity_guidelines_pdf_082019.pdf',
      'high',
      'Citation resolved and text-extracted cleanly (Dickinson Athletics Branding section). "DICKINSON RED -- Spot Color: Pantone 186; Web RGB: Red - R:211 G:35 B:45" (=#D3232D). "The Dickinson athletics marks may only be used in solid white, PMS 186 (red) and black" -- repeated twice as the complete 3-color set. Candidate''s stated hex (#E31837) does not match the document''s own RGB; corrected to the RGB-derived #D3232D. White and black kept, explicitly 2 of exactly 3 named permitted colors.'
    ),
    (
      'messiah-university',
      '213996',
      array['#002856','#FFFFFF']::text[],
      'https://www.messiah.edu/visual-identity/color-palette/',
      'high',
      'Candidate''s messiah.edu/info/23525/color_palette citation 404s (URL restructured); found the current color-palette page at the same domain. Swatch captions read "PRIMARY: INSTITUTIONAL NAVY... #002856" and "PRIMARY: WHITE... #ffffff" -- exactly two Primary colors. Matches candidate exactly, confirmed as-is.'
    ),
    (
      'shawnee-state-university',
      '205443',
      array['#003E7E','#7E8082']::text[],
      'https://www.shawnee.edu/sites/default/files/2019-01/Brand-Guidelines-low.pdf',
      'high',
      'Citation resolved and text-extracted cleanly. "Color palette... SSU blue 281 -- Pantone 281 CVC, R: 0 G: 62 B: 126. SSU gray 424 -- Pantone 424, R: 126 G: 128 B: 130." No literal HEX text, but RGB is explicitly stated for both, which counts as directly sourced. Candidate''s #00205B/#707372 do not match these stated RGB values; corrected to the RGB-derived #003E7E / #7E8082.'
    ),
    (
      'emporia-state-university',
      '155025',
      array['#000000','#BB8D0A']::text[],
      'https://www.emporia.edu/documents/3359/BrandGuidelines_23.pdf',
      'high',
      'Candidate''s logos-templates-downloads citation page links to this current (Summer 2023) Brand Guidelines PDF. "The official Emporia State University colors are Black + Gold... Black HEX: 000000... Gold HEX: bb8d0a." Matches candidate''s first and third hexes exactly. Candidate''s white dropped -- the guide states the official colors are exactly Black + Gold.'
    ),
    (
      'the-university-of-findlay',
      '202763',
      array['#F47920','#000000']::text[],
      'http://static.psbin.com/q/1/j99jg3b06su65l/Athletic_Style_Guide.pdf',
      'high',
      'Citation resolved and text-extracted cleanly. "Color Palette -- Orange: PMS 158, RGB R244 G121 B32; Black: C63 M52 Y51 K100, R0 G0 B0." No literal hex text but RGB is explicitly stated for both, counting as directly sourced; RGB(244,121,32)=#F47920 matches candidate''s stated hex exactly. Only two colors given in this Color Palette -- candidate''s white dropped, not part of the stated 2-color palette.'
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
