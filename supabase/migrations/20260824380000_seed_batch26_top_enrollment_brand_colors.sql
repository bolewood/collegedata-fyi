-- Batch 26 of brand-color scouting: verify/confirm pass over 30 candidate
-- school+hex pairs sourced from Wikipedia's college-colors dataset, none of
-- which previously had any brand_colors row (all null before this pass).
--
-- Confirmed candidates exactly as given, or confirmed with only a dropped
-- mechanically-attached white/neutral: schreiner-university (Maroon/White
-- exact match against the page's own theme-color meta tag plus prose
-- naming both as school colors), knox-college (Purple/Gold/Yellow exact
-- 3-of-3 match, all three explicitly the document's "Primary colors"),
-- piedmont-university (Green/Gold exact match -- "Our primary colors are
-- Piedmont Green and Yonahian Gold" -- white dropped), westminster-college
-- (Navy/White exact match -- the document's only two "IDENTITY COLORS"),
-- mars-hill-university (Blue/Gold exact match against the institutional,
-- non-athletics Primary Color Palette -- "Blue and gold have been
-- designated as the official colors" -- white dropped), wilmington-college
-- (Green/Lime kept, white swapped for the document's actual third
-- "PRIMARY COLORS" swatch, Cincinnati Orange), american-international-
-- college (Black/White/Yellow kept -- "We have 3 colors and only 3" --
-- yellow hex corrected to the document's stated value), mount-st-joseph-
-- university (Navy/Gold exact match via pervasive on-domain CSS after the
-- cited PDF proved to be behind a student-portal login, white dropped).
--
-- Corrected (candidate hex, color set, or source did not match the
-- school's own current official source): mcmurry-university (kept only
-- the single chromatic Maroon; the cited page's "Primary Colors" group
-- actually lists 4 swatches -- Maroon + 3 neutrals -- with a separate
-- Accent Colors group below, so white/black dropped per the brief's
-- prefer-1-2-chromatic guidance), nichols-college (re-sourced from a
-- content-free Bootstrap swatch-demo page to the main site's own
-- --bs-primary/--bs-teal CSS custom property, corrected 007A5F->115740,
-- kept single-ink), roberts-wesleyan-university (red corrected
-- C10230->9E1B2B via the site's own site_colors JSON primary_background),
-- kalamazoo-college (orange corrected EC6820->EA6820, cross-confirmed by
-- both the athletics site_colors JSON and the main site's own
-- theme.json "--k-orange" preset), mount-saint-mary-college (blue
-- corrected 0067B1->0168B3 via site_colors JSON), university-of-baltimore
-- (single official color #007DB6 confirmed via Wayback -- "the official
-- ... color is ... UB Blue" -- candidate's yellow dropped as explicitly
-- one of a separate "Secondary Colors" accent group, not official),
-- united-states-coast-guard-academy (blue/orange corrected
-- 2554C7/F47F24->1A428A/E04403 via the athletics site's own site_colors
-- JSON, white dropped), mount-aloysius-college (navy corrected
-- 192C70->005599 via the athletics site's labeled primary_background,
-- gray dropped as not present anywhere), mary-baldwin-university (gold
-- corrected FFC525->FFC524, gray #53585B kept as the site_colors JSON's
-- explicit labeled secondary, white dropped), loras-college (white
-- swapped for the document's actual third "Primary Colors" swatch, Loras
-- Grey #8D9093 -- white is not in the primary list at all), saint-marys-
-- university-of-minnesota (kept only the single color the document calls
-- "the official ... color" -- red #C8102E -- dropping navy/white, both
-- described in the same document as an athletics/recruitment accent
-- addition, not the core official color), university-of-jamestown
-- (orange corrected F2622B->E86725 via site_colors JSON, black/white
-- dropped), new-england-college (navy corrected 000F30->001638 and
-- candidate's unconfirmed gray swapped for the site_colors JSON's actual
-- labeled secondary red B11422, white dropped), marian-university-wi
-- (blue corrected 003DA5->006CB7 via site_colors JSON, black kept as the
-- explicit labeled secondary, white dropped), quincy-university
-- (re-sourced from a Pantone-only Fast Facts PDF to the athletics site's
-- own site_colors JSON, brown corrected 581E00->591F00, gold FFD457
-- confirmed exact, white dropped), waynesburg-university (orange
-- corrected B95205->BD4F19 via site_colors JSON, black/white/gray
-- dropped), maryville-college (candidate's citation URL pointed at the
-- WRONG SCHOOL entirely -- Maryville University in St. Louis, MO, not
-- Maryville College, TN -- confirmed by downloading and reading it;
-- re-sourced from Maryville College TN's own mcscots.com athletics
-- site_colors JSON, which happens to match candidate's guessed maroon/
-- orange hexes exactly despite the wrong source, white dropped),
-- transylvania-university (re-sourced from a content-free Wayback capture
-- to transy.edu's own theme.json preset explicitly labeled "crimson",
-- corrected B20D35->9D2235, kept single-ink), lycoming-college (navy/gold
-- corrected 00305C/E6B012->092E58/E9AF10 via the athletics site's own
-- site_colors JSON for the Pantone-only-in-prose blue/gold, white and
-- the hex-less accent gray dropped).
--
-- Left null (no usable on-domain hex/RGB found, or the only accessible
-- color content was an unreadable image/eyedrop-only swatch): lesley-
-- university (cited Spirit Mark brand guide is Pantone-number-only
-- throughout; homepage CSS green gradient has no label confirming it as
-- an intentional brand color), dominican-university-of-california
-- (cited page's only color content is raster swatch images with no
-- surrounding text -- reading them would require eyedropping, which is
-- forbidden -- and no fallback on-domain hex was found), northwest-
-- nazarene-university (every accessible capture of the cited brand page
-- and its linked PDF was either a maintenance-mode stub or blocked/
-- unreachable; no fallback on-domain source found).
--
-- See data/brand-colors/batch-26-2026-08-24.jsonl for the full per-school
-- record, including all three null entries.

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
      'mcmurry-university',
      '226587',
      array['#6F1830']::text[],
      'https://mcm.edu/brand-resources/',
      'high',
      'Candidate citation anchor (#Athletics) confirmed live. The page''s ''Primary Colors'' group actually lists FOUR swatches -- McMurry Maroon #6F1830, Black #000000, Light Gray #F5F5F5, White #FFFFFF -- not the candidate''s 3. Since 3 of the 4 are neutrals and only Maroon is chromatic, and a separate ''Accent Colors'' group (Dark Maroon, Gold, Warm Gold, Teal) exists below it, kept only the single chromatic primary per the brief''s ''prefer 1-2 chromatic'' guidance rather than picking 2 of 3 neutrals to fill slots 2-3. Corrected candidate''s set (dropped white/black).'
    ),
    (
      'nichols-college',
      '167260',
      array['#115740']::text[],
      'https://www.nichols.edu/wp-content/themes/nichols/assets/dist/main.css',
      'medium',
      'Candidate''s alumni.nichols.edu style-guide page 404s live; recovered via Wayback but it proved to be a generic Bootstrap swatch demo page (literal class names ''brand-primary'', ''brand-secondary'' with no color values at all) -- not a real source, not used. Nichols'' own main-site theme CSS declares --bs-primary/--bs-teal: #115740, used pervasively as the site''s link/button/nav-active color and matching Wikipedia''s infobox description of Nichols as Black-and-Green. On-domain CSS custom property, medium confidence. Corrected candidate''s guessed #007A5F (not found anywhere on nichols.edu) and dropped candidate''s black/white -- no on-domain evidence either is a named second brand color beyond default Bootstrap neutrals.'
    ),
    (
      'roberts-wesleyan-university',
      '194958',
      array['#9E1B2B']::text[],
      'https://robertsredhawks.com/',
      'medium',
      'Candidate''s citation confirmed live. The page''s own Sidearm site_colors JSON declares primary_background #9e1b2b and secondary_background #313131 (a dark gray, not chromatic). Corrected candidate''s guessed red (#C10230) to the site''s actual configured value; dropped candidate''s white and the non-chromatic gray.'
    ),
    (
      'kalamazoo-college',
      '170532',
      array['#EA6820']::text[],
      'https://hornets.kzoo.edu/landing/index',
      'medium',
      'Candidate''s citation confirmed live; its own Sidearm site_colors JSON declares primary_background #EA6820, cross-confirmed by kzoo.edu''s own WordPress theme.json preset palette naming the identical value ''--k-orange: #ea6820'' alongside a full k-red/k-yellow/k-lime/k-green/k-aqua/k-purple rainbow with no single color marked primary in prose. Two independent on-domain sources agreeing on the same hex, medium confidence. Corrected candidate''s off-by-one-digit guess (#EC6820) and dropped white/near-black (#222020, not found anywhere).'
    ),
    (
      'mount-saint-mary-college',
      '193353',
      array['#0168B3']::text[],
      'https://msmcknights.com/',
      'medium',
      'Candidate''s citation confirmed live. Page''s own Sidearm site_colors JSON declares primary_background #0168b3 and secondary_background #c2c2c2 (gray, not chromatic). Corrected candidate''s guessed blue (#0067B1) to the site''s actual configured value; dropped candidate''s white and the non-chromatic gray.'
    ),
    (
      'university-of-baltimore',
      '161873',
      array['#007DB6']::text[],
      'http://www.ubalt.edu/about-ub/offices-and-services/marketing-and-creative-services/resources/style-guide/graphic-identity-guide/color-usage.cfm',
      'high',
      'Live URL now 404s; recovered the identical page via Wayback (2017 capture). ''The University''''s official color is PMS 7960C (UB Blue) ... Official University Color ... HEX: #007DB6'' -- exact match to candidate. Text explicitly frames green/orange/dark-blue/black/light-blue/yellow(#FFB81C)/gray/white as a separate ''Secondary Colors'' accent palette, not the official color, so dropped candidate''s yellow and white.'
    ),
    (
      'mount-st-joseph-university',
      '204200',
      array['#003366', '#FFCC00']::text[],
      'https://www.msj.edu/_global/_css/style.css',
      'medium',
      'Candidate''s mymount.msj.edu PDF is behind the Jenzabar student portal login (returns the login shell as fake-200 HTML, confirmed by both direct fetch and Wayback capture) and is not readable. msj.edu''s own pervasive site stylesheet hardcodes #003366 (navy, 48 occurrences) and #FFCC00 (gold, 35 occurrences) throughout headings/links/buttons -- exact match to candidate''s navy and gold. On-domain CSS, no explicit ''primary colors'' prose found, medium confidence. Dropped candidate''s white.'
    ),
    (
      'knox-college',
      '146427',
      array['#5B2B82', '#F7A800', '#FCE200']::text[],
      'https://www.case.org/system/files/media/file/Knox%20_AwdNomineeDocs_KnoxCollege.PrairieFireVisualIdentitySystem.pdf',
      'high',
      'Candidate''s citation confirmed live and extracts cleanly. ''Knox College''''s Primary colors are listed in the chart below'': Purple #5B2B82, Gold #F7A800, Yellow #FCE200 -- exact 3-of-3 match to candidate, all three explicitly named primary colors and all chromatic (no neutral-append issue). Black/Grey/White are shown separately as B&W print-reproduction swatches, not carried over.'
    ),
    (
      'lesley-university',
      '166452',
      null::text[],
      null,
      null,
      'Candidate''s cited PDF was truncated by Wayback''s default proxy; recovered a full untruncated capture via the ''if_'' raw-content endpoint. The document (''Spirit Mark Brandguide'', re: the Lynx logo) proved to be background-approval guidance stating only Pantone numbers throughout (PMS 367, PMS 340, PMS 3302, Cool Gray 5/11) plus ''White'' and ''Black'' by name -- no hex or RGB anywhere in 11 pages, so unusable per the Pantone-only rule. Checked lesley.edu''s own homepage CSS as a fallback: it uses a green gradient family (#00A766/#65BD60/#3ADC79/#003A35) pervasively, but with no CSS custom-property label or prose naming it a ''brand color'' (looks like a decorative hero gradient), insufficient to call even medium confidence. Left null rather than guess.'
    ),
    (
      'piedmont-university',
      '140818',
      array['#144734', '#B5A268']::text[],
      'https://www.piedmont.edu/wp-content/uploads/2021/04/PiedmontUniversity_Brand-Guide_April8_2021.pdf',
      'high',
      'Live URL 404s; recovered the identical PDF via Wayback (using the raw ''if_'' endpoint since the wrapped version truncated a 46MB file). ''Our primary colors are Piedmont Green and Yonahian Gold.'' Piedmont Green WEB HEX #144734, Yonahian Gold WEB HEX #B5A268 -- exact 2-of-2 match to candidate. ''Peat Black'' (#382F2D) is explicitly listed under a separate ''Secondary'' heading immediately after, so candidate''s white was dropped and black was not added either.'
    ),
    (
      'dominican-university-of-california',
      '113698',
      null::text[],
      null,
      null,
      'Candidate''s citation 404s live; recovered via Wayback (2017 capture), but the page presents its color palette purely as three embedded raster images (''color palletes.jpg'' etc.) with zero surrounding text/hex/Pantone -- reading the actual color values would require eyedropping an image, which the brief explicitly forbids. Checked dominican.edu''s current homepage CSS (thin: only #0779bf/#ffffff) and attempted the athletics domain (dupenguins.com, connection failed/timed out on repeated tries) for a fallback; found no usable on-domain hex or named-color prose anywhere. Left null.'
    ),
    (
      'united-states-coast-guard-academy',
      '130624',
      array['#1A428A', '#E04403']::text[],
      'https://www.uscgasports.com/',
      'medium',
      'Candidate''s 2012-13 news-article citation 404s; the current uscgasports.com Sidearm site loads instead. Its own site_colors JSON declares primary_background #1a428a (blue) and secondary_background #e04403 (orange), explicitly labeled primary/secondary. Corrected candidate''s guessed navy/orange (#2554C7/#F47F24, neither found anywhere on-domain) to the site''s actual configured values; dropped candidate''s white.'
    ),
    (
      'mount-aloysius-college',
      '214166',
      array['#005599']::text[],
      'https://mountieathletics.com/',
      'medium',
      'Candidate''s citation confirmed live. Its own site_colors JSON declares primary_background #005599 (blue), with secondary_background #F2F2F3 (near-white, not chromatic). The main mtaloy.edu site independently uses a related but different blue (#095498) pervasively in its own CSS with no explicit label, corroborating blue as the school''s real color family. Used the explicitly-labeled athletics primary_background value; corrected candidate''s guessed navy (#192C70, not found anywhere on either domain) and dropped candidate''s gray (#909091, not present in either site_colors config).'
    ),
    (
      'mary-baldwin-university',
      '232672',
      array['#FFC524', '#53585B']::text[],
      'https://www.marybaldwinathletics.com/',
      'medium',
      'Candidate''s /Baldwin citation 404s; confirmed on the live marybaldwinathletics.com homepage instead. Its own site_colors JSON declares primary_background #ffc524 (gold) and secondary_background #53585b (gray), explicitly labeled primary/secondary -- both kept since the gray is an explicit labeled secondary, not a mechanically-appended neutral. Corrected candidate''s off-by-one-digit gold guess (#FFC525); dropped candidate''s white.'
    ),
    (
      'loras-college',
      '153825',
      array['#442D7D', '#D1B888', '#8D9093']::text[],
      'https://myweb.loras.edu/Loras/IdentityStandardsManual.pdf',
      'high',
      'Live URL times out; recovered the identical 2022 Brand Guide via Wayback. ''Color Palette / Primary Colors'': Loras Purple HEX #442D7D, Loras Gold HEX #D1B888, Loras Grey HEX #8D9093 -- all three explicitly grouped under ''Primary Colors'' (distinct from a separate ''Presidential Colors'' pair, red/blue, used only with the Presidential Seal). Corrected candidate''s white to the document''s actual third primary color, Loras Grey -- white does not appear in this list at all.'
    ),
    (
      'saint-marys-university-of-minnesota',
      '174817',
      array['#C8102E']::text[],
      'https://www.smumn.edu/Brand_Resources/Saint_Mary_s_Brand_Visual_Identity_Guide.pdf',
      'high',
      'Live URL 404s; recovered the identical Graphic Identity Guidelines PDF via Wayback. ''The official Saint Mary''''s University color is Pantone 186C red ... hex #C8102E'' (singular, explicit). Navy (#002855) and Yellow (#FFCD00) are described in the same paragraph as Athletic Department colors ''added as accent colors ... for recruitment,'' not the core official color, and a further note clarifies white is a brand color used only as empty background (no hex given). Kept the single stated official color; dropped candidate''s navy and white.'
    ),
    (
      'schreiner-university',
      '228042',
      array['#581515', '#FFFFFF']::text[],
      'https://schreiner.edu/about/traditions-heritage/',
      'medium',
      'Candidate''s citation confirmed live. Page''s own <meta name="theme-color"> declares #581515, matching candidate''s maroon exactly, and its tartan-heritage prose names ''maroon ... white one of our school colors, and black an official accent color'' -- confirming Maroon and White (not black) as the two school colors. Confirmed candidate''s exact pair as-is; medium confidence since evidence is a meta tag plus prose rather than a dedicated color-swatch table.'
    ),
    (
      'mars-hill-university',
      '198899',
      array['#002D72', '#90754D']::text[],
      'https://www.mhu.edu/wp-content/uploads/2018/03/MHU-Graphic-Standards-2014-rev-web.pdf',
      'high',
      'Live URL 404s; recovered the identical PDF via Wayback. ''Blue and gold have been designated as the official colors of the institution ... Primary Color Palette'': Mars Hill University Blue Web #002D72, Metallic Gold Web #90754d -- exact match to candidate''s blue and gold. The same Primary Color Palette block also lists Black and White swatches, but the prose explicitly names only ''Blue and gold'' as the official colors, so dropped candidate''s white. (A separate Athletics Color Palette on p.24 uses a brighter Yellow #FFDD00 instead of Metallic Gold for spirit-wear use only; not used here since this is the non-athletics/institutional palette.)'
    ),
    (
      'university-of-jamestown',
      '200156',
      array['#E86725']::text[],
      'https://www.jimmiepride.com/',
      'medium',
      'Candidate''s citation confirmed live. Its own site_colors JSON declares primary_background #E86725 (orange) and secondary_background #E8E8E8 (light gray, not chromatic). Corrected candidate''s guessed orange (#F2622B); dropped candidate''s near-black (#080808) and the non-chromatic secondary gray.'
    ),
    (
      'westminster-college',
      '216807',
      array['#0C2340', '#FFFFFF']::text[],
      'https://s3.us-east-2.amazonaws.com/sidearm.nextgen.sites/westminstercollegepa.sidearmsports.com/documents/2022/6/24/WestminsterCollege_BrandGuide_June2022_1_.pdf',
      'high',
      'Candidate''s sidearm document-viewer URL is a JS stub under curl; recovered the identical PDF via its underlying S3 URL (confirmed this is Westminster College, PA -- ''Home of the Titans'', IPEDS 216807). ''IDENTITY COLORS: Navy Blue #0C2340, White #FFFFFF'' -- exact 2-of-2 match to candidate, these are the only two identity colors listed.'
    ),
    (
      'northwest-nazarene-university',
      '142461',
      null::text[],
      null,
      null,
      'Candidate''s marketing.nnu.edu page times out live; Wayback''s most recent capture shows the site was ''Down for Maintenance'' at crawl time, and the only earlier capture with real content (2017) links to a Visual Standards Manual PDF whose own Wayback capture is also a maintenance-page stub, not the PDF. Checked nnucrusaders.com (connection failed on repeated attempts) and www.nnu.edu (403 blocked) for a fallback -- no accessible on-domain source found anywhere. Left null rather than guess at candidate''s unconfirmed red.'
    ),
    (
      'new-england-college',
      '182980',
      array['#001638', '#B11422']::text[],
      'https://athletics.nec.edu/',
      'medium',
      'Candidate''s 2019 logo-unveiling news article 404s; the current athletics.nec.edu Sidearm site loads instead. Its own site_colors JSON declares primary_background #001638 (navy) and secondary_background #B11422 (red), explicitly primary/secondary. Corrected candidate''s navy (#000F30) and replaced candidate''s guessed gray (#A0A5A8, not found anywhere on-domain) with the site''s actual labeled secondary red; dropped candidate''s white.'
    ),
    (
      'american-international-college',
      '164447',
      array['#000000', '#FFFFFF', '#FFCC33']::text[],
      'http://www.aic.edu/aic3/downloads/athletics/AIC_YellowJacket_BSM.pdf',
      'high',
      'Live URL 404s (only the 2014 Wayback capture is a real PDF; all later captures are 404/redirect stubs). Recovered the 2014 capture: ''Our Colors ... We have 3 colors and only 3'': Pantone 1235 Hex FFCC33, Black Hex 000000, White Hex FFFFFF -- exact 3-of-3 match to candidate except the yellow value, corrected from candidate''s guessed #FFB60F to the document''s actual stated #FFCC33. All three explicitly ''the'' 3 colors, kept per the no-neutral-append exception.'
    ),
    (
      'marian-university-wi',
      '239080',
      array['#006CB7', '#000000']::text[],
      'https://www.sabreathletics.com/',
      'medium',
      'Candidate''s /quick_facts citation 404s; confirmed on the live sabreathletics.com homepage instead. Its own site_colors JSON declares primary_background #006cb7 (blue) and secondary_background #000 (black), explicitly primary/secondary -- kept black since it is an explicit labeled secondary, not an appended neutral. Corrected candidate''s guessed blue (#003DA5, not found anywhere on-domain); dropped candidate''s white.'
    ),
    (
      'quincy-university',
      '148131',
      array['#591F00', '#FFD457']::text[],
      'https://hawks.quincy.edu/',
      'medium',
      'Candidate''s Fast Facts PDF (recovered via the underlying S3 URL after the sidearm viewer stub blocked curl) states colors only as ''Brown (Pantone 497), White, & Yellow (129)'' -- Pantone-only, no hex, unusable per that rule. Fell back to the live hawks.quincy.edu homepage''s own site_colors JSON: primary_background #591f00 (brown), secondary_background #ffd457 (yellow) -- the yellow matches candidate''s guess exactly; corrected the brown from candidate''s off-by-one-digit guess (#581E00). Dropped candidate''s white.'
    ),
    (
      'waynesburg-university',
      '216694',
      array['#BD4F19']::text[],
      'https://waynesburgsports.com/',
      'medium',
      'Candidate''s 2014 logo-unveiling article citation confirmed live, but its prose does not itself state a hex; the page''s own site_colors JSON declares primary_background #bd4f19 (orange-brown) and secondary_background #d7d7db (light gray, not chromatic). Corrected candidate''s guessed orange (#B95205); dropped candidate''s white/black and the non-chromatic secondary gray.'
    ),
    (
      'wilmington-college',
      '206507',
      array['#024E43', '#7AB800', '#E8AE41']::text[],
      'http://www.wilmington.edu/wp-content/uploads/2015/03/WC-BGM-V3-February-1-2017-WEB.pdf',
      'high',
      'Live URL is caught in an infinite Vercel/WP-Engine redirect loop; recovered the identical PDF via Wayback. ''PRIMARY COLORS ... Dark Green Web=024E43, Lime Green Web=7AB800, Cincinnati Orange Web=E8AE41'' -- three swatches explicitly grouped under a ''PRIMARY'' heading on the Color Palette page, distinct from a following ''SECONDARY PALETTE'' (Brights + Neutrals). Corrected candidate''s white to the document''s actual third primary color, Cincinnati Orange -- white does not appear in the primary or secondary palettes at all (a later ''Black and White Conversion'' section is only a grayscale-printing guide, not a color listing, per the brief''s guidance).'
    ),
    (
      'maryville-college',
      '220710',
      array['#640A28', '#FF6600']::text[],
      'https://mcscots.com/',
      'medium',
      'IMPORTANT: candidate''s citation URL (maryville.edu/marketing/.../Brand-Guidelines-Fall-2018-FIN.pdf) is the WRONG SCHOOL -- confirmed by downloading and reading it: it is Maryville University''s guide, in St. Louis, MO (IPEDS 179566), not Maryville College, TN (IPEDS 220710, this record). Not used. Re-sourced from Maryville College TN''s own athletics domain, mcscots.com, whose site_colors JSON declares primary_background #640A28 (maroon) and secondary_background #FF6600 (orange) -- both matching candidate''s guessed hexes exactly despite the wrong source, corroborated by maryvillecollege.edu''s own homepage CSS using #640a28 as an active-tab accent color. Dropped candidate''s white.'
    ),
    (
      'transylvania-university',
      '157818',
      array['#9D2235']::text[],
      'https://www.transy.edu/offices/marketing-and-communications/',
      'medium',
      'Candidate''s www2.transy.edu/news/media/logos.htm citation is unreachable live; recovered via Wayback but the page''s captured content is only global nav template, with no color/logo prose at all -- not usable as the actual source. transy.edu''s current site (marketing-and-communications page, itself 404 but still serving the site theme) embeds a WordPress theme.json palette with an explicitly labeled ''--wp--preset--color--crimson: #9D2235''. On-domain, explicitly named ''crimson'' (matching Transylvania''s well-known Crimson-and-White identity), medium confidence. Corrected candidate''s guessed #B20D35 (a Wikipedia-editor value not found anywhere on transy.edu) and dropped candidate''s white/near-black.'
    ),
    (
      'lycoming-college',
      '213668',
      array['#092E58', '#E9AF10']::text[],
      'https://lycomingathletics.com/news/2013/8/13/GEN_0813134604.aspx',
      'medium',
      'Candidate''s citation confirmed live. The 2013 article''s own prose states ''blue (PMS color 540) and gold (PMS color 130) as its official colors, while utilizing gray (PMS color 129) as an accent color'' -- Pantone-only in the prose itself, but the same page''s Sidearm site_colors JSON gives on-domain hex for the named blue/gold: primary_background #092e58, secondary_background #e9af10. Corrected candidate''s guessed navy/gold (#00305C/#E6B012, neither found anywhere on-domain); dropped candidate''s white and the (hex-less) accent gray.'
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
