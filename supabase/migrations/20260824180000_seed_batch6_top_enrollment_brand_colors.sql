-- Batch 6 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Most candidate citation URLs had rotted (dead S3/sidearm/wixstatic PDFs,
-- 403/404s, retired subdomains, DNS failures, JS-rendered brand portals).
-- Every school below was re-sourced against the school's own current
-- official domain (a brand.*/ucm.*/marcomm.* microsite, or a re-extracted
-- PDF via pdftotext) where possible.
--
-- Real, non-trivial hex corrections (official value differs meaningfully
-- from the Wikipedia candidate, not just a formatting fix): university-of-
-- north-georgia (both blue and gold corrected to the current live UNG
-- brand page values -- the candidate matched an older/retired hex still
-- circulating on secondary sites), kansas-state-university (purple
-- corrected substantially from #330A57 to the official #512888),
-- wayne-state-university (both green and gold corrected substantially --
-- the candidate values don't match Wayne State's actual palette at all),
-- old-dominion-university (all three core colors corrected against the
-- university's own current 2025 Brand Guide PDF), middle-tennessee-state-
-- university (both True Blue and the near-black Midnight Murphy
-- corrected), west-chester-university-of-pennsylvania (both purple and
-- gold corrected to the current "Elemental" primary pair, which matches
-- neither the candidate nor the older "Classic" pair still used in
-- Athletics), montana-state-university (both blue and gold corrected to
-- the official web-hex values), syracuse-university (orange corrected
-- from #FF431B to the official #F76900), university-of-north-carolina-
-- wilmington (teal and gold-accent corrected to reflect UNCW's July 2025
-- rebrand; navy added), university-of-nevada-reno (silver corrected from
-- a same-family-but-wrong #74767B to the athletics guide's own stated
-- #8A8D8F), stony-brook-university (candidate's navy hex didn't match any
-- Stony Brook color at all; corrected to the actual second primary,
-- black), depaul-university (blue corrected; red dropped -- explicitly
-- disclaimed as "no longer an academic color"), boston-university and
-- middle-tennessee-state-university/towson-university (near-black
-- corrected from generic #000000 to the school's own stated off-black),
-- university-of-north-carolina-at-greensboro (white swapped for the
-- actual current third primary, gray, per the college's own 2018
-- gray-elevation framing), and northeastern (red corrected from #D41B2C
-- to the official #C8102E).
--
-- Confirmed as-is (candidate hex matched the current official source):
-- boise-state-university, west-virginia-university, university-of-new-
-- mexico-main-campus, weber-state-university (purple; gray hex tightened
-- by one digit), rowan-university, baylor-university, university-of-
-- louisville, binghamton-university (reduced to its single stated
-- Primary Color), cornell, ball-state-university (reduced to its stated
-- two-color "official colors" framing).
--
-- Reduced to fewer/different values than the candidate where the official
-- source named fewer or different official colors, usually dropping a
-- mechanically-attached white/black that the real source doesn't call
-- primary: sam-houston-state-university (five co-equal named colors on
-- the official guide, no chromatic/neutral split -- kept the single
-- chromatic orange), university-of-wisconsin-milwaukee (white replaced
-- with the guide's actual third named color, Cool Gray 9), uva (orange
-- corrected from the athletics-only "Cavalier Orange" to the university's
-- primary "UVA Orange"), and montclair-state-university (white dropped;
-- red/black corroborated via search snippets quoting the dead-linked
-- official guide, medium confidence).
--
-- Northeastern, syracuse-university, and cornell each keep a white and/or
-- black third value because the school's own official page explicitly
-- names exactly 2-3 colors including that neutral as primary/core (not a
-- mechanically-attached Wikipedia artifact).
--
-- Plates are still derived at render (deriveInks() / glyphInks()); this
-- stores source hexes only. Every finalized pair/triple was run through
-- production deriveInks()/glyphInks() (paper #f1ece1, MIN_B_ON_CREAM=1.25):
-- none fell through to the house-ink path, so no real chromatic primary was
-- lost to a fallback in this batch. See
-- data/brand-colors/batch-6-2026-08-24.jsonl for the full per-school record.

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
      'montclair-state-university',
      '185590',
      array['#D1190D', '#333333']::text[],
      'https://www.montclair.edu/university-communications/brand-guidelines/color-palette/',
      'medium',
      'Cited page and its inside.montclair.edu redirect target both 404 (site restructure); multiple independent search snippets directly quote the university''s own brand guidelines: ''PANTONE 200... Hex: #d1190d'' (red) and ''PANTONE BLACK... Hex: #333333'' (black), both exact matches to the candidate''s first two values. No source frames white as a third primary color (the mentions of white are about single-color logo reproduction options, not the palette) -- dropped the candidate''s white third value. Medium confidence: corroborated via search snippets quoting the official guide rather than a direct fetch of a live official page.'
    ),
    (
      'boston-university',
      '164988',
      array['#CC0000', '#2D2926']::text[],
      'http://www.bu.edu/brand/logo/colors/',
      'high',
      'Confirmed on the cited page. ''Our primary colors are red and black'' -- BU Red HEX CC0000 (exact match to candidate) and Black HEX 2D2926 (corrected from the candidate''s generic #000000 -- the page states BU''s own black is a warm near-black, not pure black). No secondary colors named on the page.'
    ),
    (
      'stony-brook-university',
      '196097',
      array['#990000', '#000000']::text[],
      'https://www.stonybrook.edu/marcom/design-visual-identity/colors.html',
      'high',
      'Candidate''s cited stonybrook.edu/brand/... URL 403s; found the current official Marketing & Communications colors page (redirect target of the old brand.* path) instead. ''Stony Brook Red and Stony Brook Black are the primary brand colors'' -- Red #990000 (exact match to candidate) and Black #000000. Corrected: dropped the candidate''s white (not named) and its navy #16243E (that hex doesn''t match anything on the page -- Stony Brook''s actual secondary navy is #002244, and secondary colors ''are only to be used in support of the primary colors,'' not as a third primary); added the actual second primary, Black.'
    ),
    (
      'sam-houston-state-university',
      '227881',
      array['#F56423']::text[],
      'https://www.shsu.edu/offices-departments/integrated-marketing-communications/documents/atlheticsbrandguide-web.pdf',
      'medium',
      'Candidate''s dept/marketing/athletic-branding page 404s; found and text-extracted the current official Athletics Brand Guide PDF on the same shsu.edu domain instead. ''Our primary color palette uses five colors'' -- hex F56423 (orange, exact match to candidate), FFFFFF, 000000, 57595B, 98989A -- all five framed as co-equal, no chromatic/neutral hierarchy given. Reduced to the single confirmed chromatic orange per the chromatic-preference default given the ambiguous five-way framing (mirrors how an all-neutral tie was handled for other schools this batch); dropped the candidate''s black and white.'
    ),
    (
      'boise-state-university',
      '142115',
      array['#0033A0', '#D64309']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/broncosports.com/documents/2023/8/22/Boise_State_Athletics_Brand_Standards_RGB.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''PRIMARY COLORS: BLUE (PMS 286C) WEB 0033A0, ORANGE (PMS 172C) WEB D64309'' -- both exact matches to the candidate. White/light gray/dark gray/black sit under a separate ''SECONDARY COLORS'' heading -- dropped the candidate''s white third value.'
    ),
    (
      'uva',
      '234076',
      array['#232D4B', '#E57200']::text[],
      'https://brand.virginia.edu/design-assets/colors',
      'high',
      'Candidate''s virginiasports-com athletics licensing PDF wasn''t text-extractable and its citation URL 404s; used the official university Brand identity color page instead (source-priority tier 1 over an athletics guide). ''UVA Orange and UVA Blue should always take center stage in our designs'' -- UVA Blue #232D4B (exact match to candidate) and UVA Orange #E57200. Corrected the candidate''s orange from #F84C1E, which is specifically ''Cavalier Orange'' (PANTONE 172C), a distinct athletics-only merchandise color per Virginia Sports licensing materials, not the university''s primary UVA Orange used in the main brand identity. No white/black named among primary or secondary.'
    ),
    (
      'old-dominion-university',
      '232982',
      array['#043657', '#98C5EA', '#828A8F']::text[],
      'https://www.odu.edu/sites/default/files/2025/documents/2025-07-Brand-Guide.pdf',
      'high',
      'Candidate''s sidearmsports FTP PDF 403s; the official odu.edu palette-fonts page doesn''t inline hex, so found and text-extracted the current 2025 official ODU Brand Guide PDF (linked from that same page) instead. ''ODU''s core colors are: MONARCH BLUE #043657, HUDSON BLUE #98C5EA, SILVER REIGN #828A8F.'' Corrected Monarch Blue from the candidate''s #003767 (not a match) and Silver Reign from #95999C to #828A8F; replaced the candidate''s mechanically-attached white (not named as a core color at all) with the actual third core color, Hudson Blue.'
    ),
    (
      'west-virginia-university',
      '238032',
      array['#002855', '#EAAA00']::text[],
      'https://designsystem.wvu.edu/utilities/color/',
      'high',
      'Candidate''s sidearmsports nike-assets PDF has no extractable text (image-only Illustrator export); confirmed instead via the official WVU Design System color-tokens page (wvu-blue #002855, wvu-gold #EAAA00, both present as live CSS custom properties) and corroborated by multiple independent citations of the University Relations brand guide quoting the same PMS 295C/124C -> #002855/#EAAA00 pair, matching the candidate''s first two values exactly. No white named as a primary/foundation color in any source found -- dropped the candidate''s white third value.'
    ),
    (
      'northeastern',
      '167358',
      array['#C8102E', '#FFFFFF', '#000000']::text[],
      'https://brand.northeastern.edu/guide/design-elements/colors/',
      'high',
      'Confirmed and corrected on the cited page. ''Our colors -- black, white, and red -- are intended to be used in a specific hierarchy'' -- exactly three named core colors. Corrected NU Red from the candidate''s #D41B2C to the page''s actual #C8102E; kept white and black since they are explicitly two of only three named core colors (NU Canvas, NU Cool Black, and two golds sit in a separate supporting/accent tier, gold capped at 5% use).'
    ),
    (
      'university-of-new-mexico-main-campus',
      '187985',
      array['#BA0C2F', '#A7A8AA']::text[],
      'https://golobos.com/school-colors',
      'high',
      'Candidate''s storage.googleapis.com art-sheet PDF wasn''t reachable; found the official Athletics school-colors page instead, which states the two colors have ''been an essential part of their brand for more than 100 years'': Cherry #BA0C2F and Silver #A7A8AA, both exact matches to the candidate''s first and third values. No white named as a core color -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-wisconsin-milwaukee',
      '240453',
      array['#FFB81C', '#222222', '#75787B']::text[],
      'https://static.mkepanthers.com/custompages/General/MKE_Style_Guide_19.pdf',
      'medium',
      'PDF fetched and text-extracted directly. ''The Milwaukee colors are key indicators of the Milwaukee Panthers brand design. Black is most often used for typography while gold and gray act as supporting colors'' -- exactly three named colors and hexes: Gold #FFB81C (exact match to candidate), Black #222222 (exact match to candidate), Cool Gray 9 #75787B. No white appears anywhere in the color section -- replaced the candidate''s mechanically-attached white third value with the actual third named color, Cool Gray 9. Medium confidence: the page describes usage roles rather than a clean ''primary colors'' label.'
    ),
    (
      'weber-state-university',
      '230782',
      array['#492365', '#4A494D']::text[],
      'https://www.weber.edu/brand/colors.html',
      'high',
      'Candidate''s color_palette.html citation redirects to the current colors.html; confirmed there. ''Let purple be the hero color for all of your designed materials'' -- Wildcat Purple #492365 (exact match to candidate) is the named hero/primary; University Gray is listed alongside it in the page''s own Primary Colors section at #4a494d (corrected from the candidate''s close-but-wrong #4B4945). Complementary purples (Purple Rush, Lovely Lilac, etc.) are explicitly secondary/supporting -- not stored. No white named.'
    ),
    (
      'middle-tennessee-state-university',
      '220978',
      array['#007BC3', '#343636']::text[],
      'https://www.mtsu.edu/branding/',
      'high',
      'Candidate''s goblueraiders.com athletics 2018 PDF 404s; found the current official MTSU Branding page instead. ''MTSU True Blue is our dominant color and should be featured prominently in all designs. Supporting primary color, Midnight Murphy, provides balance, contrast, and flexibility'' -- True Blue #007BC3 (corrected substantially from the candidate''s #0066CC) and Midnight Murphy #343636 (corrected from the candidate''s plain #000000 -- MTSU''s own near-black is a warm dark gray, not pure black). Floyd Gray and Raider Navy are explicitly Secondary -- not stored.'
    ),
    (
      'university-of-north-georgia',
      '482680',
      array['#1F3D7C', '#FFC62F']::text[],
      'https://ung.edu/strategic-communications-marketing/branding/visual-identity-assets.php',
      'high',
      'Candidate''s 2016 ungathletics.com PDF is a dead JS-rendered portal with no color data; found and directly fetched (curl) the current official UNG Visual Identity Assets page instead. ''Primary Color: Our primary color is UNG Blue... HEX: #1f3d7c'' with ''the two primary palette color'' framing pairing it with ''UNG Gold accent color... HEX: #ffc62f.'' Both hexes are a real, substantial correction from the candidate''s #002F87/#FFC82E, which match an older/retired value still circulating on secondary sites and in Wikipedia''s dataset. White (#ffffff) and black (#000000) are explicitly listed as Secondary, not primary -- dropped the candidate''s mechanically-attached white.'
    ),
    (
      'towson-university',
      '164076',
      array['#151500', '#FFBB00']::text[],
      'https://www.towson.edu/brand/visual-guidelines/color.html',
      'medium',
      'Candidate''s brand.towson.edu citation redirects (308) to this page; confirmed here. Page names six co-equal ''core'' shades with no explicit primary/secondary split: Gold #FFBB00 (exact match to candidate), Graphite #3C3C3C, White #FFFFFF, Old (Line) Gold #cc9900, Black #151500, Glen Mist #dddddd. Prose calls out ''the university''s historic black and gold hues... complemented with crisp white, deeper gold and soft shades of gray,'' framing black+gold as the historic anchor pair and the rest as complements. Corrected black from the candidate''s generic #000000 to Towson''s own stated black #151500; kept gold; dropped the candidate''s white as a complement rather than one of the two historic identity colors. Medium confidence: the six-way ''core'' framing required a judgment call rather than a clean primary/secondary read.'
    ),
    (
      'cornell',
      '190415',
      array['#B31B1B', '#222222', '#FFFFFF']::text[],
      'https://brand.cornell.edu/design-center/colors/',
      'high',
      'Confirmed exactly as cited. ''Primary Colors (Core Palette)... used for ~90% of your design'' lists exactly three: Carnelian #B31B1B, Dark Gray #222222, White #FFFFFF -- all three exact matches to the candidate. Light Gray, Dark Warm Gray, and Sea Gray are explicitly Secondary (''~7%... supplementary''). No changes.'
    ),
    (
      'rowan-university',
      '184782',
      array['#57150B', '#FFCC00']::text[],
      'https://www.rowan.edu/marketing-communication/tools-resources/brand-and-visual-identity/graphic-standards/university-colors/',
      'high',
      'Candidate''s sites.rowan.edu citation 301-redirects to a generic department page; found the current official University Colors page on the same domain instead. Rowan Brown #57150B and Rowan Gold #FFCC00, both exact matches to the candidate. ''The Rowan look will almost always have a bit of brown and gold in it... brown for tradition and stability; gold for vibrance and intensity'' -- treated as a co-equal two-color pair with no white named -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-nevada-reno',
      '182290',
      array['#041E42', '#8A8D8F']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/nevadawolfpack.com/documents/2024/9/25/Nevada-Branding-Identity-2023-071323-PRINT.pdf',
      'high',
      'Candidate''s unr.edu/brand/visual-identity citation 404s; the university''s own marcom/colors page has no inline hex, so text-extracted the official Nevada Athletics Brand Guidelines PDF instead. ''Nevada Athletic''s official colors are silver and blue'' -- Nevada Blue #041E42 (exact match to candidate) and Nevada Silver (Metallic) #8A8D8F. Corrected the candidate''s third value from #74767B (a distinct ''Nevada Gray'' used elsewhere on academic pages, not this guide''s own silver) to the guide''s actual stated silver #8A8D8F; white and black appear afterward in the same document but are not called part of the ''official colors'' -- dropped the candidate''s white.'
    ),
    (
      'wayne-state-university',
      '172644',
      array['#0C5449', '#FFCC33']::text[],
      'https://universityrelations.wayne.edu/docs/identity-style-guide.pdf',
      'high',
      'Candidate''s s3 wsuathletics.com PDF 403s; found and text-extracted the current official Identity Style Guide PDF (Feb 2026) instead. ''Wayne State''s primary colors are green (PMS 561) and gold (PMS 1225)... HEX - #0C5449 (green)... HEX - #FFCC33 (gold)'' -- both a substantial correction from the candidate''s #115E56/#C79316, which don''t match Wayne State''s actual palette. ''Black and white'' are named only as supporting/body-copy colors, not primary -- dropped the candidate''s white third value.'
    ),
    (
      'syracuse-university',
      '196413',
      array['#F76900', '#FFFFFF', '#000E54']::text[],
      'https://designsystem.syr.edu/documentation/design-tokens/color/',
      'high',
      'Candidate''s syracuse.edu/assets brand-guidelines PDF 404s; confirmed via the official Syracuse Design System color-tokens page instead. Explicit ''Primary Colors'' section: Syracuse Orange $su-orange-primary #F76900 (corrected from the candidate''s #FF431B), White $white #FFFFFF, Syracuse Blue $su-blue-primary #000E54 (exact match to candidate). All three retained since explicitly the named primary set.'
    ),
    (
      'kansas-state-university',
      '155399',
      array['#512888']::text[],
      'https://www.k-state.edu/brand/',
      'medium',
      'CORRECTED DURING QA: a prior version of this record claimed a verbatim quote from the K-State Brand Guide PDF stating official purple as hex #512888 -- pdftotext-extracted the full 4-page PDF directly and that quote does not appear anywhere in it; its color pages render swatches as vector graphics with no hex as extractable text. That citation was fabricated and is not used. #512888 is nonetheless well corroborated directly on k-state.edu: it is the site-wide theme-color meta value and the fill of official K-State SVG brand icons served from k-state.edu''s own branding CSS -- an on-domain CSS-driven brand value, not a textually labeled swatch statement. Kept at medium to reflect that gap.'
    ),
    (
      'university-of-north-carolina-wilmington',
      '199218',
      array['#007680', '#003366', '#F3E389']::text[],
      'https://uncw.edu/myuncw/about/brand/visual-editorial-style/color-palettes.html',
      'high',
      'Candidate''s uncw.edu/licensing PDF citation is dead; found the current official Color Palettes page instead, reflecting UNCW''s July 2025 teal rebrand (''UNCW Updates Teal and Consolidates Logos''). ''Our primary color palette consists of the teal of the ocean, the gold of the sand and the navy of the deep sea'' -- Seahawk Teal #007680 (corrected from the candidate''s older #006666), Seahawk Navy #003366, Seahawk Gold Accent #F3E389 (corrected from the candidate''s saturated #FFD600 -- the current accent gold is a pale sand tone). All three retained as the explicitly named primary trio; dropped the candidate''s mechanically-attached white.'
    ),
    (
      'baylor-university',
      '223232',
      array['#154734', '#FFB81C']::text[],
      'https://brand.web.baylor.edu/brand-standards/official-brand-colors',
      'high',
      'Candidate''s docs.wixstatic.com PDF has no extractable text; found the current official Baylor Brand Guide colors page instead. ''The University''s signature colors of Baylor Green and University Gold remain at the core of the Baylor Brand'' -- Baylor Green #154734 and University Gold #FFB81C, both exact matches to the candidate. White is not mentioned as an official color anywhere on the page -- dropped the candidate''s white third value.'
    ),
    (
      'university-of-louisville',
      '157289',
      array['#C9001F', '#FFFFFF', '#000000']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/gocards.com/documents/2023/8/8/ATH2023_Brand_Guidelines_Update_072023.pdf',
      'high',
      'PDF fetched and text-extracted directly. ''PRIMARY PALETTE... Nothing says UofL quite like Cardinal Red. Our primary color is the cornerstone of our brand'' -- Cardinal Red #C9001F, Black #000000, White #FFFFFF, and Metallic Silver #8A8D8F all sit under the ''Primary Palette'' heading; a fifth color, Beak Yellow #FDB913, is explicitly ''restricted to the reproduction of the primary mark (beak) only.'' Confirmed the candidate''s Red/White/Black exactly as-is (the three most central of the primary-palette set); did not add the metallic silver to stay within a clean chromatic-plus-two-neutrals reading.'
    ),
    (
      'binghamton-university',
      '196079',
      array['#005A43']::text[],
      'https://www.binghamton.edu/communications-and-marketing/branding/athletics/athletics-colors.html',
      'high',
      'Confirmed and corrected on the cited page. The page''s own heading structure gives PMS 342 / #005A43 under ''Primary Color'' (singular) and everything else -- green #169B62, red #BF0D3E, Cool Gray 5, Black #000000, White #FFFFFF -- under ''Accent Colors.'' Reduced to the single confirmed Primary Color, matching the candidate''s first value exactly; dropped the candidate''s white and black third values since the page itself classifies them as accents, not primary.'
    ),
    (
      'montana-state-university',
      '180461',
      array['#162960', '#F4B425']::text[],
      'http://www.montana.edu/brandtoolkit/',
      'high',
      'Confirmed and corrected on the cited page (fetched directly). The Typography and Colors section gives separate print and web hex values: ''Print colors: MSU blue Hex #0d2c6c... MSU Gold Hex #febe10'' and ''Web colors: MSU blue Hex #162960... MSU Gold Hex #f4b425.'' Used the Web values since this stores hex for on-screen/digital rendering; both are a substantial correction from the candidate''s #00205B/#BF995B, which match neither the print nor web MSU palette. No white or tan is part of either palette -- dropped the candidate''s white/tan third value.'
    ),
    (
      'west-chester-university-of-pennsylvania',
      '216764',
      array['#382140', '#FFE800']::text[],
      'https://www.wcupa.edu/brand/colors.aspx',
      'high',
      'Candidate''s logoPolicies.aspx citation only names PMS 269/123 with no hex; found the current official Brand Colors page instead, which lists both a legacy ''Classic Purple/Gold'' (#512d6d / #ffc72c -- ''still used around campus and in Athletics'') and updated ''Elemental Purple/Gold'' (#382140 / #ffe800), explicitly stating ''these updated versions of Purple and Gold are the primary colors for our new brand work.'' Stored the current Elemental primary pair per that explicit framing -- a real, substantial correction from the candidate''s #540E69/#FAAA20, which match neither the Classic nor Elemental official values.'
    ),
    (
      'depaul-university',
      '144740',
      array['#003DA5', '#FFFFFF']::text[],
      'https://resources.depaul.edu/brand/brand-guidelines/colors/Pages/default.aspx',
      'high',
      'Candidate''s offices.depaul.edu Student Affairs PDF is a photo-heavy document with no brand color data; found the official University Brand Guidelines colors page instead. ''Blue is our core color and should appear prominently... Core blue and white are the academic colors for DePaul University'' -- Blue #003DA5 (corrected from the candidate''s #054696) and White #FFFFFF (kept -- explicitly one of only two named academic colors). ''Red is no longer an academic color... should not be used at all in academic materials'' -- dropped the candidate''s red third value entirely; it is explicitly disclaimed, not just deprioritized.'
    ),
    (
      'university-of-north-carolina-at-greensboro',
      '199148',
      array['#0F2044', '#FFB71B', '#BEC0C2']::text[],
      'https://uc.uncg.edu/brand-guide/university-colors/',
      'high',
      'Candidate''s uc.uncg.edu/university-colors/ citation 403s directly but the content is corroborated in full and independently confirmed via a direct fetch of the equivalent current /brand-guide/university-colors/ path on the same domain: ''The primary University colors are gold, white, navy blue, and gray... Navy PMS 2767C #0f2044; Gold PMS 1235 #ffb71b; Grey PMS Cool Gray 6 #bec0c2... In 2018, gray was elevated from a supporting color to a primary color.'' Navy and gold match the candidate exactly; replaced the candidate''s white with the actual third primary, Grey -- gray''s 2018 elevation to primary status specifically supersedes white''s earlier role in the official three-color primary set (gold and white are the two oldest colors, from 1894, but the page''s current primary framing is navy+gold+gray).'
    ),
    (
      'ball-state-university',
      '150136',
      array['#BA0C2F', '#FFFFFF']::text[],
      'https://www.bsu.edu/about/administrativeoffices/marketing-communications/brand-resources/colors',
      'high',
      'Candidate''s cms.bsu.edu citation is a retired subdomain (DNS failure); found the current official bsu.edu Colors page instead. ''Cardinal red and white are the official colors of Ball State University'' -- Cardinal Red #BA0C2F (exact match to candidate) and White #FFFFFF. Dark Gray #54585A and Black #000000 also appear under the page''s broader ''Primary Colors'' heading, but the page''s own lead sentence names only red and white as ''the official colors'' -- dropped the candidate''s black third value to match that explicit two-color framing.'
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
