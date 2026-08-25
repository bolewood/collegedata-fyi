-- Batch 25 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a dropped
-- mechanically-attached white/neutral: lake-superior-state-university
-- (Blue/Gold exact match, recovered via Wayback after the live PDF was
-- blocked by Cloudflare, white dropped), oklahoma-baptist-university
-- (Green/Gold exact match on the athletics art-sheet PDF, white dropped),
-- texas-lutheran-university (Black/Gold exact match -- "Our primary colors
-- are Black and TLU Gold" -- re-hosted PDF, white dropped), lakeland-
-- university (Navy/Gold exact match under "INSTITUTIONAL COLORS", white
-- dropped, athletic and supporting color groups on the same PDF left out),
-- queens-university-of-charlotte (Blue/Gold exact match under "PRIMARY"/
-- "SECONDARY", recovered via the underlying S3 PDF after the sidearm
-- viewer stub blocked curl, white dropped -- an apparel-only secondary),
-- juniata-college (Blue/Gold exact match -- "the two official primary
-- colors" -- recovered via Wayback after Akamai blocked the live page,
-- white dropped).
--
-- Corrected (candidate hex, color set, or source did not match the
-- school's own current official source): west-virginia-state-university
-- (gold corrected C99700->CFB023 against the athletics quick-facts page's
-- own stated hex, black kept -- one of exactly two named colors),
-- oglethorpe-university (re-sourced to the current Nov-2024 style guide
-- after the old PDF 404'd; single primary gold #FFDD00, black/white
-- dropped -- explicitly an "alternate palette," not a second primary),
-- gordon-college (candidate's citation was a literal Google search URL,
-- not a real source; re-sourced to Gordon's own Brand Resources page --
-- Gordon Blue #014983 and Scottie Cyan #00AEEF under "Primary Colors",
-- correcting candidate's guessed blue and its placeholder pure-cyan
-- #00FFFF), catawba-college (blue corrected -- candidate's #13294E is the
-- page's labeled Secondary "Dark Blue", not primary; real primary is
-- Catawba Blue #02216E + white, both explicitly the "official College
-- primary colors"; candidate's #989AA5 dropped as not present anywhere in
-- the guide), chatham-university (purple corrected 735990->625093 against
-- "PMS 268 is the primary color for Chatham University"; kept single-ink,
-- a second candidate purple in the doc is a tint of the same heritage hue
-- not a distinct named color; white/gray dropped), lasell-university (all
-- three of Lasell's actual "Primary Colors" are chromatic -- Navy
-- #13294B, Blue #69B3E7, Light Blue #5C88DA -- candidate's white swapped
-- out since the source lists it only under Neutral Colors, not Primary),
-- wittenberg-university (red corrected C51F35->990000 against the current
-- Branding Guidelines PDF's own "Wittenberg Red (For Web Use Only)"
-- hex; kept single-ink -- the doc's Primary Colors block also includes
-- black, a gray, a 50%-tint gray, and white, none individually more
-- load-bearing than another and collectively over the 3-slot budget),
-- thomas-more-university (blue/gray corrected against the current
-- Nov-2024 Visual Identity PDF -- rendered as an image to resolve a
-- self-contradictory printed hex on the gray swatch (#99CC99, clearly a
-- copy-paste error since it decodes to green, not the gray shown); a
-- second instance of the same PMS 421 gray elsewhere in the doc gives the
-- correct #848689, used instead; black kept -- all three are the
-- document's own named "official colors," not appended), simpson-college
-- (both hexes corrected via the athletics site's own --color-primary/
-- --color-secondary CSS custom properties after the candidate's issuu
-- document proved unextractable), north-carolina-wesleyan-university
-- (both hexes corrected via Sidearm site-config JSON on the redirected
-- current URL), suny-maritime-college (re-sourced from the Pantone-free-
-- text quick-facts page to the university's own theme-color meta tag,
-- corrected 62082C->780032, kept single-ink), johnson-c-smith-university
-- (re-sourced from a dead 2015 PDF to the current Brand Management page's
-- own theme CSS, navy corrected 062562->002D56, gold confirmed FFCF01),
-- russell-sage-college (green corrected 006F51->006747 via the page's own
-- theme-primary-color/theme-secondary-color meta tags; white kept -- one
-- of only two explicitly labeled theme colors), westmont-college
-- (athletics style guide proved Pantone/CMYK-only with no hex anywhere;
-- corrected via the main westmont.edu site's own CTA-button CSS color
-- 810031->9D2235, kept single-ink), washington-and-jefferson-college
-- (brand PDF dead with no Wayback capture; confirmed red A4343A via the
-- school's own homepage CSS, kept single-ink, black/white dropped),
-- virginia-union-university (style manual proved Pantone-only for
-- "Maroon & Steel"; corrected via the school's own homepage CSS
-- 8F012D->990033 matching the named Maroon, kept single-ink -- no
-- on-domain evidence for the named Steel gray), meredith-college
-- (candidate's athletics citation names no colors at all; corrected via
-- meredith.edu's own pervasive homepage CSS maroon 6D1A34->82003D, kept
-- single-ink), saint-vincent-college (re-sourced from a color-free
-- quick-facts page to the live Athletic Communications page's own
-- "Official Approved Colors" section, confirming Green #1C5633 and Gold
-- #D9AB28 with directly stated hex), east-texas-baptist-university
-- (candidate's citation redirects to a login page; sibling Typography-
-- and-Color page's own theme-color meta tag confirms navy #081F2C, kept
-- single-ink -- no on-domain hex found for the candidate's gold),
-- northern-state-university (original PDF dead with no Wayback capture,
-- current Brand Guide is a JS flipbook not text-extractable; both hexes
-- confirmed via the main site's own CSS -- a labeled ".gold-box" rule and
-- the site's maroon -- matching candidate exactly).
--
-- Left null (no usable on-domain hex/RGB found, only bare Pantone
-- numbers or bare color names with no number at all -- see brief's
-- Pantone-only-is-not-medium rule, or conflicting/unconfirmable signals):
-- kentucky-state-university (official Graphic Standards Manual states
-- only "Green: PMS 349, Gold: PMS 109", no hex anywhere on domain),
-- adams-state-university (official Graphic Standards page states only
-- "black and pantone green 341", no hex anywhere on domain -- a
-- third-party #00452A guess does not appear on adams.edu and was not
-- used), immaculata-university (athletics page names "Navy Blue,
-- Carolina Blue, and White" with no hex; the only distinctive homepage
-- CSS colors are stock Bootstrap/WordPress theme defaults, not
-- confirmable as intentional brand colors), william-jessup-university
-- (two rebrands in two years -- 2023 "royal blue, red, white", 2024
-- "navy primary, light-blue accent" -- neither ever published a hex; the
-- site's current CSS teal #0680a2 matches neither description and looks
-- like an unrelated theme default, so treated as a wrong-swatch risk and
-- not used).
--
-- See data/brand-colors/batch-25-2026-08-24.jsonl for the full per-school
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
      'east-texas-baptist-university',
      '224527',
      array['#081F2C']::text[],
      'https://www.etbu.edu/etbu-now/brand-standard/typography-and-color',
      'medium',
      'Candidate citation (website-design-standards) redirects to a login-gated page; the sibling ''Typography and Color'' page under the same Brand Standard section loads but its ''Brand Colors'' swatch content is JS-rendered and not present in the static HTML. The page''s own theme-color/msapplication-TileColor meta tags declare #081F2C, matching candidate''s navy exactly -- on-domain declared brand color, medium confidence. No hex found anywhere on-domain for the candidate''s gold (#ECBC00) or white; dropped both rather than guess.'
    ),
    (
      'oglethorpe-university',
      '140696',
      array['#FFDD00']::text[],
      'https://oglethorpe.edu/wp-content/uploads/2024/12/OU24-Style-Guide.pdf',
      'high',
      'Candidate''s uc.oglethorpe.edu PDF 404s; re-sourced to the current (Nov 2024) OU24-Style-Guide.pdf. ''The primary color is the Oglethorpe yellow.'' PMS 109, HEX #ffdd00 -- exact match to candidate. The doc separately states ''The alternate palette is black and white only'' for black-and-white-only pieces -- explicitly an alternate, not a second primary color, so black/white dropped rather than carried over from candidate. Two further unlabeled accent swatches (light blue #71b2c9, red #c8102e) appear on the same page with no ''primary'' designation and were not used.'
    ),
    (
      'lake-superior-state-university',
      '170639',
      array['#003F87', '#FFC61E']::text[],
      'https://www.lssu.edu/wp-content/uploads/2016/04/lssu-style-guide.pdf',
      'high',
      'Live URL now blocked by Cloudflare bot protection; recovered the identical PDF via Wayback (2025 capture). ''LSSU''''s primary color is web color #003F87. The secondary color is #FFC61E.'' Exact 2-of-2 match to candidate; dropped candidate''s white -- not named as a primary/secondary color in the text.'
    ),
    (
      'west-virginia-state-university',
      '237899',
      array['#CFB023', '#000000']::text[],
      'http://www.wvsuyellowjackets.com/sports/2016/7/11/2016-wvsu-quick-facts.aspx',
      'high',
      'Candidate''s live citation confirmed. Page states colors as ''Old Gold (Pantone 117 - #CFB023) and Black (#000000)'' -- corrected candidate''s guessed gold (#C99700) to the page''s actual stated hex #CFB023; black retained since it is explicitly named as one of exactly two official colors, not a mechanically-appended neutral.'
    ),
    (
      'immaculata-university',
      '213011',
      null::text[],
      null,
      null,
      'Candidate''s gomightymacs.com citation loads and states ''Colors: Navy Blue, Carolina Blue, and White'' but gives no hex/RGB/Pantone anywhere on the page. Checked immaculata.edu homepage CSS for a fallback on-domain hex: the only distinctive values present (#428bca, #1b365d, #69b3e7) are stock Bootstrap-3/WordPress default-theme swatches, not confirmable as intentionally chosen Immaculata brand colors, so not used. Left null rather than eyedrop or guess.'
    ),
    (
      'kentucky-state-university',
      '157058',
      null::text[],
      null,
      null,
      'Candidate''s kysu.edu PDF 404s; recovered the identical Graphic Standards Manual (rev. 3/19/18) via Wayback. ''Official Colors: Green: PMS 349, Gold: PMS 109'' -- Pantone numbers only, no hex/RGB/CMYK anywhere in the document. Checked kysu.edu''s live CSS for a fallback on-domain hex; found no green/gold theme color at all. Per the brief''s rule that Pantone-only is not medium confidence, left null.'
    ),
    (
      'oklahoma-baptist-university',
      '207403',
      array['#007934', '#F3CF45']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/okbu.sidearmsports.com/documents/2019/6/18/OBU_Art_Sheet_2019.pdf',
      'high',
      'Candidate''s citation confirmed (PDF downloads and extracts cleanly). Color tables for both the Primary Athletic Marks and University Marks state Green PMS 356 HEX #007934 and Gold PMS 129 HEX #F3CF45, exact match to candidate. Dropped candidate''s white -- not one of the named colors (the table lists Green, Gold, Vegas Gold #D2C295, and Black with no hex; only Green and Gold are common to both mark families).'
    ),
    (
      'texas-lutheran-university',
      '228981',
      array['#000000', '#EAAB00']::text[],
      'https://tlu-edu.files.svdcdn.com/production/files/general/TLU_Brand_Standards_v1_070912.pdf',
      'high',
      'Candidate''s tlu.edu-hosted PDF 404s; the identical document is now re-hosted on TLU''s CDN domain. ''Our primary colors are Black and TLU Gold.'' Table gives Hexadecimal for web: Black #000000, TLU Gold #EAAB00 -- exact match to candidate. Dropped candidate''s white, not named as a primary color.'
    ),
    (
      'westmont-college',
      '125727',
      array['#9D2235']::text[],
      'https://www.westmont.edu/',
      'medium',
      'Candidate''s athletics.westmont.edu Style Guide PDF (recovered via the underlying S3 URL after the sidearm document-viewer stub blocked curl) states colors only as Pantone/CMYK (''Westmont Crimson'' PMS 202 C, ''Westmont Gold'' PMS 874 C) -- no hex/RGB anywhere in the 26-page document, so not usable per the Pantone-only rule. Fell back to the main westmont.edu homepage, whose CSS uses #9D2235 as the primary CTA button color (31 occurrences) -- on-domain color, corrected from candidate''s guessed #810031. No comparably strong on-domain evidence for a gold companion, so kept as a single chromatic ink; dropped candidate''s white/black.'
    ),
    (
      'washington-and-jefferson-college',
      '216667',
      array['#A4343A']::text[],
      'https://www.washjeff.edu/',
      'medium',
      'Candidate''s washjeff.edu-hosted brand-guidelines PDF is dead (returns CloudFront 403/moved, no Wayback capture available). No replacement official brand PDF found via search. Fell back to washjeff.edu''s own homepage CSS, which uses #A4343A repeatedly as its accent/highlight color -- exact match to candidate''s stated red, on-domain evidence, medium confidence. Dropped candidate''s black/white -- no distinguishing on-domain evidence either was treated as an official second color rather than generic UI neutral.'
    ),
    (
      'william-jessup-university',
      '122728',
      null::text[],
      null,
      null,
      'Candidate''s citation (Jan 2023 rebrand article) states only ''royal blue, red, and white'' with no hex; a later Feb 2024 athletics rebrand reportedly made navy the primary color with a light-blue accent, again with no hex published. jessup.edu''s current CSS declares a WordPress theme-primary/theme-secondary of #0680a2 (teal), which matches neither the 2023 nor 2024 verbal descriptions and looks like an unrelated theme default rather than a deliberate brand color -- treated as a wrong-swatch risk per the brief''s guidance and not used. No hex found anywhere on jessup.edu or jessupathletics.com after two rebrands in two years; left null.'
    ),
    (
      'thomas-more-university',
      '157809',
      array['#000099', '#848689', '#000000']::text[],
      'https://www.thomasmore.edu/wp-content/uploads/24tmu_visualstandards.pdf',
      'high',
      'Candidate''s cited filename 404s; re-sourced to the current (Nov 2024) Visual Identity Standards PDF. ''The official colors for the Thomas More University visual identity are blue, gray and black'' -- page rendered as an image to check the printed swatch hexes: Blue (PMS 661) #000099, Gray (PMS 421) shown visually as a plain gray though the page prints a self-contradictory hex (#99CC99, clearly wrong -- decodes to green, not the gray swatch shown); a second instance of the same PMS 421 gray elsewhere in the document gives #848689, which matches the rendered swatch color and was used instead. Black #000000. All three are explicitly the school''s named ''official colors,'' not mechanically appended, so kept all three per the brief''s exception; corrected candidate''s blue (#00559F) and gray (#9FA1A3), dropped candidate''s white (not one of the three named colors).'
    ),
    (
      'suny-maritime-college',
      '196291',
      array['#780032']::text[],
      'https://www.sunymaritime.edu/',
      'medium',
      'Candidate''s maritimeathletics.com Quick Facts page loads and states colors as ''Cardinal, Navy, Off-Black, Grey, and White'' but gives no hex/RGB anywhere. sunymaritime.edu''s own theme-color/mask-icon meta tags declare #780032, consistent with the named ''Cardinal'' -- on-domain declared color, medium confidence, corrected from candidate''s guessed #62082C. No comparable on-domain evidence found for the named Navy, so kept as a single chromatic ink; dropped candidate''s white/navy.'
    ),
    (
      'gordon-college',
      '165936',
      array['#014983', '#00AEEF']::text[],
      'https://www.gordon.edu/offices-services/marketing/resources',
      'high',
      'Candidate''s citation was literally a Google search-results URL for ''pms 294'', not a real source -- searched fresh. Found Gordon''s own Brand Resources page: ''Color Palette Primary Colors ... Gordon Blue | 100-69-7-30 | #014983 | PMS 294C. Scottie Cyan | 100-0-0-0 | #00AEEF | Process Cyan.'' Both explicitly under ''Primary Colors.'' Corrected candidate''s guessed blue (#003882) and its literal pure-cyan guess (#00FFFF, clearly an eyedrop/placeholder) to the real stated hexes; dropped candidate''s white.'
    ),
    (
      'northern-state-university',
      '219259',
      array['#990033', '#FFCC66']::text[],
      'https://northern.edu/',
      'medium',
      'Candidate''s northern.edu-hosted graphicstandards.pdf is dead with no Wayback capture; the current official 2023 Brand Guide is a JS-rendered flipbook (apps.northern.edu) whose page content is not text-extractable via curl. Fell back to northern.edu''s own homepage CSS: a ''.gold-box { background-color: #ffcc66 /* Gold background */ }'' style rule matches candidate''s gold exactly, and #990033 (maroon, matching Northern''s well-known maroon-and-gold identity) is used repeatedly in site chrome. On-domain CSS evidence for both hexes exactly matching candidate, medium confidence.'
    ),
    (
      'saint-vincent-college',
      '215798',
      array['#1C5633', '#D9AB28']::text[],
      'https://athletics.stvincent.edu/sports/2022/2/9/athletic-communications.aspx',
      'high',
      'Candidate''s cited GEN_1010103003.aspx page only states ''Colors: Green & Gold'' with no hex. Found the live Athletic Communications page instead, which has an ''Official Approved Colors'' section: Green PMS 357, RGB 29-86-51, Hex# #1c5633; Gold PMS 110, RGB 217-171-40, Hex# #d9ab28. Both directly stated hex, high confidence.'
    ),
    (
      'adams-state-university',
      '126182',
      null::text[],
      null,
      null,
      'Candidate''s citation page 404s; recovered the current Graphic Standards page. ''The colors for the logo are black and pantone green 341'' -- Pantone number only, no hex/RGB anywhere on the page or elsewhere checked on adams.edu. A third-party search result surfaced #00452A as ''the'' green, but that hex does not appear anywhere on adams.edu and was not used. Left null.'
    ),
    (
      'johnson-c-smith-university',
      '198756',
      array['#002D56', '#FFCF01']::text[],
      'https://www.jcsu.edu/communications-and-marketing/brand-management',
      'medium',
      'Candidate''s jcsu.edu-hosted 2015 Brand Guidelines PDF 404s; the current Brand Management page has no downloadable PDF or color prose, but its own theme CSS uses #002D56 (navy, 22 occurrences) and #FFCF01 (gold, 8 occurrences, matching candidate exactly) as the site''s active accent colors -- on-domain CSS custom properties, medium confidence. Corrected candidate''s navy (#062562) to the site''s actual value; dropped candidate''s white.'
    ),
    (
      'russell-sage-college',
      '195128',
      array['#006747', '#FFFFFF']::text[],
      'https://www.sagegators.com/information/quickfacts/index',
      'medium',
      'Candidate''s citation loads. Page''s own meta tags explicitly declare theme-primary-color #006747 and theme-secondary-color #ffffff -- an explicit two-color labeled scheme on the official athletics domain, medium confidence (meta/site-config, not narrative prose). Corrected candidate''s green (#006F51) to the page''s actual configured value; white kept since it is one of only two explicitly labeled theme colors, not a mechanically-appended third value; dropped candidate''s gray (#231F20), not present in this config.'
    ),
    (
      'catawba-college',
      '198215',
      array['#02216E', '#FFFFFF']::text[],
      'https://catawba.edu/brandguide/',
      'high',
      'Candidate''s citation confirmed live. ''College Brand Colors Primary Colors: Catawba Blue and white are the official College primary colors.'' Catawba Blue Online: #02216E; White Online: #FFFFFF. Corrected candidate''s blue -- #13294E is actually the page''s labeled ''Secondary Colors: Dark Blue,'' not the primary. White kept since it is explicitly one of exactly two labeled primary colors. Dropped candidate''s #989AA5, which does not appear anywhere in the brand guide''s primary/secondary/tertiary tables.'
    ),
    (
      'chatham-university',
      '211556',
      array['#625093']::text[],
      'https://my.chatham.edu/documents/documentcenter/CU%20Brand%20Standards-0319.pdf',
      'high',
      'Candidate''s citation confirmed live and extracts cleanly. ''PMS 268 is the primary color for Chatham University, both academics and athletics.'' Hex: 625093 -- corrected from candidate''s guessed #735990. The doc also says ''Use both PMS 268 and PMS 2695 for backgrounds...on light backgrounds,'' but PMS 2695 (#4b366b) is a darker tint of the same heritage-purple hue family, not a second named primary color, so kept Chatham as a single ink rather than pair two tints of one hue. Dropped candidate''s white and gray -- neither appears in the Heritage Colors group.'
    ),
    (
      'simpson-college',
      '154350',
      array['#9F1A29', '#EAAB21']::text[],
      'https://www.simpsonathletics.com/',
      'medium',
      'Candidate''s issuu-hosted ID Guidelines document is not text-extractable via curl (JS viewer). simpsonathletics.com''s own site-config CSS declares ''--color-primary:#9F1A29; --color-secondary:#EAAB21;'' explicitly labeled primary/secondary -- on-domain CSS custom properties, medium confidence. Corrected candidate''s maroon (#931A29) and gold (#EFB402) to the site''s actual configured values; dropped candidate''s white.'
    ),
    (
      'lasell-university',
      '166391',
      array['#13294B', '#69B3E7', '#5C88DA']::text[],
      'https://www.lasell.edu/discover-lasell/news/office-of-communications/brand-and-identity-center.html',
      'high',
      'Candidate''s citation confirmed live. ''Primary Colors: Lasell Navy Blue'' HEX #13294b, ''Lasell Blue'' HEX #69b3e7, ''Light Blue'' HEX #5c88da -- all three explicitly under the page''s own ''Primary Colors'' heading, none of them a neutral, so kept all three per the max-3/prefer-chromatic guidance (no neutral-append issue at all here). Dropped candidate''s white, which the page lists only under ''Neutral Colors'' alongside black/grey, not as a primary.'
    ),
    (
      'wittenberg-university',
      '206525',
      array['#990000']::text[],
      'https://www.wittenberg.edu/sites/default/files/media/universitycommunications/WittenbergBrandingGuidelines-Rev2023.pdf',
      'high',
      'Candidate''s citation confirmed live and extracts cleanly. ''PRIMARY COLORS: Wittenberg Red (For Web Use Only) #990000, Wittenberg Red (For Print) PANTONE 200 #C2002F.'' Used the web-specific hex since this powers a website glyph. The same Primary Colors block also names Black, a gray (PMS 7527, #D7D1C4), a 50%-tint gray (#EAE8E2), and White as separate boxes -- four neutral/near-neutral entries alongside the one chromatic red, more than the 3-slot budget and none individually more load-bearing than another, so per the brief''s ''prefer 1-2 chromatic hexes when in doubt'' guidance kept Wittenberg Red alone. Corrected candidate''s guessed #C51F35.'
    ),
    (
      'north-carolina-wesleyan-university',
      '199209',
      array['#003C69', '#D7A900']::text[],
      'https://ncwsports.com/recruiting_central/quick_facts',
      'medium',
      'Candidate''s ncwcsports.com citation 301-redirects to ncwsports.com. The redirected sidearm page embeds site-config JSON: window.site_colors = {"primary_background":"#003c69","primary_text":"#fff","secondary_background":"#d7a900","secondary_text":"#000"} -- on-domain Sidearm site-config JSON, medium confidence. Corrected candidate''s navy (#0F4D76) and gold (#EEC626) to the site''s actual configured values; dropped candidate''s white (site config labels it ''primary_text,'' a foreground/contrast color, not a second brand ink).'
    ),
    (
      'lakeland-university',
      '238980',
      array['#0C233F', '#FFC62F']::text[],
      'https://lakeland.edu/perch/resources/admin/lakeland-brand-guidelines.pdf',
      'high',
      'Candidate''s citation confirmed live and extracts cleanly. ''INSTITUTIONAL COLORS: Lakeland Navy Blue WEB: #0C233F, Lakeland Gold WEB: #FFC62F'' -- exact match to candidate. The doc separately lists ''Athletic Colors'' (Muskies Blue #0070b9, Muskies Gray #97999B) and ''Supporting Colors'' (Black, 30% Gray, White) as distinct groups; kept only the Institutional pair, dropping candidate''s white.'
    ),
    (
      'queens-university-of-charlotte',
      '199412',
      array['#00205B', '#A89968']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/queensathletics.com/documents/2022/4/29/Athletic_Guidelines_Updated_4_29_22.pdf',
      'high',
      'Candidate''s citation URL is blocked by the sidearm document-viewer stub under curl; recovered the identical PDF via its underlying S3 URL. ''PRIMARY -- 70% / The primary blue...'' PMS 281, HTML 00205B; ''SECONDARY -- 15% / The secondary gold...'' PMS 7503, HTML A89968 -- exact 2-of-2 match to candidate. Dropped candidate''s white, listed only as an apparel ''Secondary color'' for uniforms, not part of the brand-identity primary/secondary pair.'
    ),
    (
      'virginia-union-university',
      '234164',
      array['#990033']::text[],
      'https://www.vuu.edu/',
      'medium',
      'Candidate''s citation PDF loads but states colors only as ''Maroon & Steel (Pantones PMS 194 (Maroon) and PMS 877 (Steel)) ... may be printed in the pantone colors or white and black ONLY'' -- Pantone-only, no hex/RGB anywhere in the document. Fell back to vuu.edu''s own homepage CSS, which uses #990033 as its dominant maroon (37 occurrences) -- on-domain color matching the named Maroon, medium confidence, corrected from candidate''s guessed #8F012D. No comparable on-domain hex found for the named Steel gray, so kept as a single chromatic ink; dropped candidate''s white/gray.'
    ),
    (
      'juniata-college',
      '213251',
      array['#1B365D', '#A89968']::text[],
      'https://www.juniata.edu/offices/marketing/standards-guide/colors.php',
      'high',
      'Live URL now returns Akamai ''Access Denied''; recovered the identical page via Wayback. ''Primary Colors: Blue and gold are the two official primary colors of Juniata College.'' PMS 534 Blue HEX #1b365d, PMS 7503 Gold HEX #a89968 -- exact 2-of-2 match to candidate. Dropped candidate''s white, not one of the ''two official primary colors.'''
    ),
    (
      'meredith-college',
      '198950',
      array['#82003D']::text[],
      'https://www.meredith.edu/',
      'medium',
      'Candidate''s goavengingangels.com citation loads but names no colors or hex on the page at all. Fell back to meredith.edu''s own homepage CSS, which uses #82003D pervasively (29 occurrences, including as CSS custom properties for its events-bar/calendar theme) as the site''s dominant maroon -- on-domain color, medium confidence, corrected from candidate''s guessed #6D1A34. No comparably strong on-domain evidence for a second color, so kept as a single chromatic ink; dropped candidate''s white/#222222.'
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
