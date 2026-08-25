-- Batch 1 of brand-color scouting: the "mich…" collision set (Michigan
-- State, Western/Central/Northern Michigan, Michigan Tech, and a umich
-- confidence upgrade). These are the rows users hit first when searching
-- "Michigan" -- until now they all rendered identical unknown-grey glyphs.
-- Source hexes only; deriveInks() / glyphInks() still derive plates at
-- render. See data/brand-colors/batch-2026-08-24.jsonl for full scouting
-- notes and source citations per school.

with seed (
  school_id,
  brand_colors,
  brand_colors_source,
  brand_colors_confidence,
  brand_colors_notes
) as (
  values
    (
      'michigan-state-university',
      array['#18453B']::text[],
      'https://brand.msu.edu/visual/color-palette',
      'high',
      'Official MSU Brand Studio page: Spartan Green (#18453B) and white are the core brand colors, black an accessibility fallback. White/black excluded per the no-neutral-append rule; single chromatic hex stored.'
    ),
    (
      'western-michigan-university',
      array['#F1C500', '#532E1F']::text[],
      'https://wmich.edu/brand/visualidentity/color',
      'high',
      'Official WMU Brand site: primary colors gold (#F1C500, Pantone 7406, swatched first, "dominant role") and brown (#532E1F, Pantone 4625). White also listed as primary but excluded per the no-neutral-append rule.'
    ),
    (
      'central-michigan-university',
      array['#6A0032', '#FFC82E']::text[],
      'https://www.cmich.edu/offices-departments/university-communications/brand-guidelines/visual-language/color-palette',
      'high',
      'Official CMU University Communications brand guidelines page: Primary colors Maroon (#6A0032) and Gold (#FFC82E), in that order.'
    ),
    (
      'northern-michigan-university',
      array['#095339', '#FFC425']::text[],
      'https://nmu.edu/mc/sites/mc/files/2020-08/NMU%20Institutional%20Brand%20Standards.pdf',
      'high',
      'Official Institutional Brand Standards Guide PDF, page 2 ("The Official Colors of Northern Michigan University"): NMU Green #095339 and NMU Gold #FFC425, primary palette in that order. The nmu.edu/mc/branding HTML landing page names these colors but does not print hex; the PDF does.'
    ),
    (
      'michigan-technological-university',
      array['#000000', '#FFCD00']::text[],
      'https://www.mtu.edu/umc/resources/brand/visual-identity/',
      'high',
      'Official UMC visual-identity page: official colors stated as black (#000000) and gold (#FFCD00) as the primary pair. Stored as published -- the no-neutral-append rule bars tacking a neutral onto an already-complete two-chromatic pair, it does not bar a published black+gold pair itself. deriveInks() rejects #000000 at the chroma gate and falls back to charcoal for the A plate; that is the intended black-and-gold render treatment (see derive-inks.test.ts "rejects black as a plate and keeps the gold"), not a scouting gap.'
    ),
    (
      'umich',
      array['#00274C', '#FFCB05']::text[],
      'https://brand.umich.edu/design-resources/colors/',
      'high',
      'Upgraded medium -> high. brand.umich.edu blocks automated fetches with a Cloudflare bot challenge, so it could not be re-fetched directly, but intranet.tcaup.umich.edu/knowledge-base/colors/ (Taubman College, umich.edu subdomain) independently restates the identical hexes -- Michigan Blue #00274C and Maize #FFCB05 -- and cites brand.umich.edu/design-resources/colors/ as its source. Same source URL retained; hexes unchanged.'
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
where d.school_id = s.school_id;
