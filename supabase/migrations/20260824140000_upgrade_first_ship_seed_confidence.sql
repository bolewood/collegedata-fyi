-- Batch 2 of brand-color scouting: confirm/upgrade pass over the remaining
-- 18 first-ship seed schools from 20260823210000_seed_handoff_brand_colors.sql
-- (umich, the 19th first-ship school, was already upgraded in batch 1 --
-- 20260824130000 -- and is not touched here).
--
-- Only rows where something actually changed are included: confidence
-- upgraded to high on re-confirmation, hexes corrected against the official
-- source, and/or the source URL swapped to a more specific/current page.
-- Seven of the eighteen scouted schools (bethel-university,
-- hampton-university, oberlin, smith-college, spelman-college,
-- tulane-university-of-louisiana, wellesley-college) could not be
-- independently confirmed this pass (bot-walled, 404/DNS-dead source pages,
-- or an intranet login wall) and are left untouched at medium confidence --
-- see data/brand-colors/batch-2-2026-08-24.jsonl for the full record,
-- including human-review flags on spelman-college, tulane-university-of-
-- louisiana, and wellesley-college where secondary sources suggest the
-- recorded hexes may be stale but could not be confirmed against an
-- official page this pass.
--
-- Plates are still derived at render (deriveInks() / glyphInks()); this
-- stores source hexes only.

with seed (
  school_id,
  brand_colors,
  brand_colors_source,
  brand_colors_confidence,
  brand_colors_notes
) as (
  values
    (
      'amherst',
      array['#3F1F69']::text[],
      'https://www.amherst.edu/news/communications/visual-identity-toolkit/colors',
      'high',
      'Official Visual Identity Toolkit page: "MAMMOTH PURPLE is the main color in the Amherst College Identity," primary palette HEX #3f1f69 (previously recorded #4F2683 does not appear on the official page). The page explicitly warns against secondary colors "suggest[ing] that the Amherst College school colors are anything other than purple and white" -- there is no official gold/tan; the previously recorded #B7A57A does not exist anywhere in the published palette and has been dropped rather than carried forward. Stored as a single chromatic ink.'
    ),
    (
      'colorado-college',
      array['#EAB337', '#000000']::text[],
      'https://www.coloradocollege.edu/offices/ocm/guides-and-best-practices/visual-style/colors.html',
      'high',
      'Found the dedicated Visual Style color page (offices/communications/ has reorganized to offices/ocm/). States Tiger Gold (Pantone 1235C) HEX #EAB337 and CC Black HEX #000000 as the two primary institutional colors -- both corrected from the previously recorded #FFC72C/#1E1E1E, which do not match the published swatch. Black kept per the no-neutral-append rule''s scope: it is one of the two explicitly published primary colors (Michigan Tech precedent), not an appended neutral.'
    ),
    (
      'grinnell-college',
      array['#DA291C', '#000000']::text[],
      'https://www.grinnell.edu/about/leadership/offices-services/communications/our-brand/visuals',
      'high',
      'Found the current Visual Language page (recorded source URL reorganized). States "Our primary colors are PMS 485 and black" -- Grinnell Red HEX #DA291C and Black HEX #000000. Gold does not appear in the primary tier; the previously recorded #F0B323 does not match any color on the published page (closest is a light accent tan #FFE1A0). Corrected to the officially labeled primary pair; black kept per the no-neutral-append rule''s scope (Michigan Tech precedent).'
    ),
    (
      'howard-university',
      array['#003A63', '#E51937']::text[],
      'https://ouc.howard.edu/our-services/creative-branding-multimedia/colors-typography',
      'high',
      'Upgraded medium -> high; recorded www2.howard.edu/brand source now redirects to a 404. The Office of Communications "Colors & Typography" page explicitly states Blue HEX #003A63 and Red HEX #E51937 -- exact match to the previously recorded hexes, now confirmed as hex text on an official dedicated page.'
    ),
    (
      'mit',
      array['#750014', '#8B959E']::text[],
      'https://brand.mit.edu/color',
      'high',
      'Upgraded medium -> high; web.mit.edu/graphicidentity/colors.html now redirects to brand.mit.edu/color. States MIT Red HEX #750014 (exact match) and Silver Gray HEX #8b959e (small correction from previously recorded #8A8B8C). Silver gray is rejected as a neutral by deriveInks() either way, so the render outcome is unchanged; data-accuracy fix only.'
    ),
    (
      'morehouse-college',
      array['#840028', '#C1A231']::text[],
      'https://morehouse.edu/hubfs/22200391/Files/PDFs/Brand-Guidelines-March-2021.pdf',
      'high',
      'Found the official Brand Guidelines PDF (hosted on morehouse.edu, linked from the recorded /about/brand page). Extracted text: "Our official visual identity colors are maroon (PMS 202) and white," PMS 202 C = HEX #840028; gold is secondary/accent tier (PMS 7753, used <=20%) at HEX #C1A231. Both previously recorded values (#8A1C1C, #B79A5B) were off from the published swatch; corrected to the exact stated hexes.'
    ),
    (
      'reed-college',
      array['#A70E16', '#000000']::text[],
      'https://www.reed.edu/strategic-communications-and-marketing/guidelines/graphic-standards/colors.html',
      'high',
      'Found the current Graphic Standards color page (recorded reed.edu/communications/visual-identity/ URL now 404s; office renamed Strategic Communications & Marketing). States "Reed''s primary color palette comprises Reed Red and Black Ink" -- Reed Red HEX #A70E16 (one-digit correction from previously recorded #A70E13) and Black Ink HEX #000000. Grey is not part of the current published palette at all; previously recorded #4F5858 does not match any swatch. Corrected to the officially labeled primary pair; black kept per the no-neutral-append rule''s scope (Michigan Tech precedent).'
    ),
    (
      'rice',
      array['#00205B', '#7C7E7F']::text[],
      'https://brand.rice.edu/colors',
      'high',
      'Upgraded medium -> high; source URL narrowed to the dedicated /colors page (brand.rice.edu/ is a landing page that links out without showing hex itself). States "Rice University Blue HEX #00205B" and "Rice University Gray HEX #7C7E7F" -- exact match to the previously recorded hexes, now confirmed as hex text on an official page.'
    ),
    (
      'stanford',
      array['#8C1515', '#E98300']::text[],
      'https://identity.stanford.edu/design-elements/color/primary-colors',
      'high',
      'Upgraded medium -> high; source URL narrowed to the primary-colors subpage. States "Our primary palette consists of Cardinal red, white, black and cool grey," Cardinal red HEX #8C1515 (exact match); the separate Accent Colors page states the gold/orange "Poppy" accent at HEX #E98300 (exact match). Both hexes confirmed as hex text on official identity.stanford.edu pages.'
    ),
    (
      'ut-austin',
      array['#BF5700']::text[],
      'https://umac.utexas.edu/brand-center/visual-identity/colors/',
      'high',
      'Upgraded medium -> high; brand.utexas.edu/visual-identity/colors/ now redirects to umac.utexas.edu/brand-center/, whose /visual-identity/colors/ subpage carries the swatch. States Burnt Orange, Pantone PMS 159, HEX #bf5700 -- exact match to the previously recorded single hex.'
    ),
    (
      'uc-berkeley',
      array['#002676', '#FDB515']::text[],
      'https://brand.berkeley.edu/visual-identity/color/',
      'high',
      'Same official source URL, re-fetched and confirmed twice independently. States "Our primary colors are Berkeley Blue and California Gold" -- Berkeley Blue HEX #002676 and California Gold HEX #FDB515. Gold is an exact match to the previously recorded value; blue is a correction from the previously recorded #003262, which is not the primary swatch on the current page (may reflect an older print-era value).'
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
