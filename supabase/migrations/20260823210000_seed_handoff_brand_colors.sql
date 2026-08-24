-- First-ship brand hexes from the riso school-inks design handoff
-- (ink-lab.html). Plates are still derived at render; this stores source
-- hexes only.
--
-- 19 of the 20 brief school palettes. Deep Springs College is not in
-- institution_directory (Scorecard does not list it), and its grey-only
-- palette would house-fallthrough anyway. The synthetic "Pale primary ·
-- test" row is not a school.

with seed (
  school_id,
  brand_colors,
  brand_colors_source,
  brand_colors_notes
) as (
  values
    (
      'umich',
      array['#00274C', '#FFCB05']::text[],
      'https://brand.umich.edu/design-resources/colors/',
      'First-ship palette from the riso school-inks design handoff. Michigan Blue + Maize.'
    ),
    (
      'stanford',
      array['#8C1515', '#E98300']::text[],
      'https://identity.stanford.edu/design-elements/color/',
      'First-ship palette from the riso school-inks design handoff. Cardinal + accent gold.'
    ),
    (
      'uc-berkeley',
      array['#003262', '#FDB515']::text[],
      'https://brand.berkeley.edu/visual-identity/color/',
      'First-ship palette from the riso school-inks design handoff. Berkeley Blue + California Gold.'
    ),
    (
      'howard-university',
      array['#003A63', '#E51937']::text[],
      'https://www2.howard.edu/brand',
      'First-ship palette from the riso school-inks design handoff. Navy + Howard red. B-on-A type stays cream.'
    ),
    (
      'ut-austin',
      array['#BF5700']::text[],
      'https://brand.utexas.edu/visual-identity/colors/',
      'First-ship palette from the riso school-inks design handoff. Burnt orange only; A falls back to charcoal.'
    ),
    (
      'mit',
      array['#750014', '#8A8B8C']::text[],
      'https://web.mit.edu/graphicidentity/colors.html',
      'First-ship palette from the riso school-inks design handoff. MIT Maroon; grey second colour is rejected.'
    ),
    (
      'wellesley-college',
      array['#0142A2', '#C9D9EE']::text[],
      'https://www.wellesley.edu/communications',
      'First-ship palette from the riso school-inks design handoff. Wellesley blue + pale second.'
    ),
    (
      'grinnell-college',
      array['#B01F24', '#F0B323']::text[],
      'https://www.grinnell.edu/about/offices-services/communications/brand',
      'First-ship palette from the riso school-inks design handoff.'
    ),
    (
      'spelman-college',
      array['#00457C', '#7A9A01']::text[],
      'https://www.spelman.edu/about-us',
      'First-ship palette from the riso school-inks design handoff.'
    ),
    (
      'reed-college',
      array['#A70E13', '#4F5858']::text[],
      'https://www.reed.edu/communications/visual-identity/',
      'First-ship palette from the riso school-inks design handoff. Reed red; grey second colour is rejected.'
    ),
    (
      'bethel-university',
      array['#10306B', '#F0B323']::text[],
      'https://www.bethel.edu/university-communications/brand',
      'First-ship palette from the riso school-inks design handoff. Bethel University (MN, UNITID 173160), not IN/TN namesakes.'
    ),
    (
      'oberlin',
      array['#C00000', '#FFC72C']::text[],
      'https://www.oberlin.edu/communications',
      'First-ship palette from the riso school-inks design handoff.'
    ),
    (
      'morehouse-college',
      array['#8A1C1C', '#B79A5B']::text[],
      'https://morehouse.edu/about/brand',
      'First-ship palette from the riso school-inks design handoff.'
    ),
    (
      'smith-college',
      array['#F5C400', '#002B45']::text[],
      'https://www.smith.edu/about-smith/college-relations',
      'First-ship palette from the riso school-inks design handoff. Gold + navy; order as published in the brief.'
    ),
    (
      'rice',
      array['#00205B', '#7C7E7F']::text[],
      'https://brand.rice.edu/',
      'First-ship palette from the riso school-inks design handoff. Rice Blue; grey second colour is rejected.'
    ),
    (
      'tulane-university-of-louisiana',
      array['#006747', '#418FDE']::text[],
      'https://brand.tulane.edu/',
      'First-ship palette from the riso school-inks design handoff. Olive + Tulane blue.'
    ),
    (
      'colorado-college',
      array['#FFC72C', '#1E1E1E']::text[],
      'https://www.coloradocollege.edu/offices/communications/',
      'First-ship palette from the riso school-inks design handoff. Gold + black.'
    ),
    (
      'amherst',
      array['#4F2683', '#B7A57A']::text[],
      'https://www.amherst.edu/news/communications',
      'First-ship palette from the riso school-inks design handoff. Purple + gold.'
    ),
    (
      'hampton-university',
      array['#00447C', '#005EB8']::text[],
      'https://www.hamptonu.edu/',
      'First-ship palette from the riso school-inks design handoff. Two close blues; B is pushed brighter to separate.'
    )
)
update public.institution_directory as d
set
  brand_colors = s.brand_colors,
  brand_colors_source = s.brand_colors_source,
  brand_colors_checked_at = date '2026-08-23',
  brand_colors_confidence = 'medium',
  brand_colors_notes = s.brand_colors_notes
from seed s
where d.school_id = s.school_id;
