"""Tests for IR-hub link detection and Brave name-collision guards."""

from __future__ import annotations

import unittest

from tools.finder.ir_hubs import (
    collect_ir_hub_candidates,
    distinctive_name_tokens,
    enrollment_to_instsize,
    extract_about_links,
    extract_ir_hub_links,
    host_belongs_to_domain,
    result_matches_school,
    well_known_ir_hub_urls,
)


TCC_HOME = "https://www.tulsacc.edu/"
TCC_IR = "https://www.tulsacc.edu/about-tcc/institutional-research"


class ExtractIrHubLinksTests(unittest.TestCase):
    def test_homepage_ir_text_and_about_tcc_path(self) -> None:
        html = """
        <html><body>
          <a href="/admissions">Apply now</a>
          <a href="/about-tcc">About TCC</a>
          <a href="/about-tcc/institutional-research">Institutional Research</a>
          <a href="https://other.edu/institutional-research">Someone else IR</a>
        </body></html>
        """
        self.assertEqual(extract_ir_hub_links(html, TCC_HOME), [TCC_IR])

    def test_fact_book_and_ie_path_variants(self) -> None:
        html = """
        <a href="/ie/">Office of Institutional Effectiveness</a>
        <a href="/about/fact-book">Fact Book</a>
        <a href="/news/institutional-research-hires-analyst">News</a>
        """
        links = extract_ir_hub_links(html, "https://example.edu/")
        self.assertEqual(
            links,
            [
                "https://example.edu/ie/",
                "https://example.edu/about/fact-book",
            ],
        )

    def test_ira_subdomain_counts_as_same_institution(self) -> None:
        html = '<a href="https://ira.example.edu/">IRA</a>'
        self.assertEqual(
            extract_ir_hub_links(html, "https://www.example.edu/"),
            ["https://ira.example.edu/"],
        )

    def test_short_ir_path_does_not_match_first_or_directory(self) -> None:
        html = """
        <a href="/first-year">First year</a>
        <a href="/directory">Directory</a>
        <a href="/ir/">IR office</a>
        """
        self.assertEqual(
            extract_ir_hub_links(html, "https://example.edu/"),
            ["https://example.edu/ir/"],
        )

    def test_about_page_then_ir_link_is_how_tulsa_is_reached(self) -> None:
        homepage = """
        <a href="/about-tcc">About TCC</a>
        <a href="/admissions">Admissions</a>
        """
        about = """
        <a href="/about-tcc/leadership">Leadership</a>
        <a href="/about-tcc/institutional-research">Institutional Research</a>
        """
        self.assertEqual(extract_ir_hub_links(homepage, TCC_HOME), [])
        self.assertEqual(
            extract_about_links(homepage, TCC_HOME),
            ["https://www.tulsacc.edu/about-tcc"],
        )
        hubs = collect_ir_hub_candidates(
            homepage,
            TCC_HOME,
            about_pages=[("https://www.tulsacc.edu/about-tcc", about)],
            include_well_known=False,
        )
        self.assertEqual(hubs[0], TCC_IR)

    def test_collect_caps_extra_guesses_and_prefers_real_links(self) -> None:
        html = '<a href="/institutional-research">Institutional Research</a>'
        hubs = collect_ir_hub_candidates(
            html,
            "https://www.example.edu/",
            include_well_known=True,
            include_subdomains=True,
            domain="example.edu",
            limit=6,
        )
        self.assertEqual(hubs[0], "https://www.example.edu/institutional-research")
        self.assertLessEqual(len(hubs), 6)
        self.assertIn("https://www.example.edu/ir", hubs)

    def test_well_known_paths_stay_on_the_landing_origin(self) -> None:
        urls = well_known_ir_hub_urls("https://www.tulsacc.edu/index.html")
        self.assertTrue(
            all(u.startswith("https://www.tulsacc.edu/") for u in urls)
        )
        self.assertIn("https://www.tulsacc.edu/institutional-research", urls)


class NameCollisionGuardTests(unittest.TestCase):
    def test_nvcc_does_not_take_george_mason_cds(self) -> None:
        self.assertFalse(
            result_matches_school(
                "https://oiep.gmu.edu/resources/student-consumer-information/common-data-set/",
                "Common Data Set 2023-2024",
                "George Mason University Common Data Set",
                school_name="Northern Virginia Community College",
                school_domain="nvcc.edu",
                other_names=["George Mason University"],
                other_domains=["gmu.edu"],
            )
        )

    def test_apus_does_not_take_azusa_pacific_cds(self) -> None:
        self.assertFalse(
            result_matches_school(
                "https://www.apu.edu/oir/commondata/",
                "Common Data Set | Azusa Pacific University",
                "Office of Institutional Research",
                school_name="American Public University System",
                school_domain="apus.edu",
                other_names=["Azusa Pacific University"],
                other_domains=["apu.edu"],
            )
        )

    def test_byu_idaho_does_not_take_byu_provo_cds(self) -> None:
        self.assertFalse(
            result_matches_school(
                "https://data.byu.edu/common-data-set",
                "Common Data Set | Brigham Young University",
                "Official CDS for Brigham Young University in Provo",
                school_name="Brigham Young University-Idaho",
                school_domain="byui.edu",
                other_names=["Brigham Young University"],
                other_domains=["byu.edu"],
            )
        )

    def test_on_domain_hit_counts_even_without_the_full_name_in_the_snippet(self) -> None:
        self.assertTrue(
            result_matches_school(
                "https://www.tulsacc.edu/about-tcc/institutional-research",
                "Institutional Research",
                "Common Data Set files",
                school_name="Tulsa Community College",
                school_domain="tulsacc.edu",
            )
        )
        self.assertTrue(
            host_belongs_to_domain(
                "https://ira.tulsacc.edu/cds",
                "tulsacc.edu",
            )
        )

    def test_off_domain_hit_counts_when_the_document_names_this_school(self) -> None:
        self.assertTrue(
            result_matches_school(
                "https://okhighered.org/reports/tulsa-community-college-cds.pdf",
                "Tulsa Community College Common Data Set 2024-25",
                "Published for Tulsa Community College",
                school_name="Tulsa Community College",
                school_domain="tulsacc.edu",
                other_names=["University of Tulsa"],
                other_domains=["utulsa.edu"],
            )
        )

    def test_idaho_tokens_are_what_separate_the_byu_campuses(self) -> None:
        self.assertIn("idaho", distinctive_name_tokens("Brigham Young University-Idaho"))
        self.assertNotIn("idaho", distinctive_name_tokens("Brigham Young University"))

    def test_enrollment_buckets_match_ipeds_instsize(self) -> None:
        self.assertEqual(enrollment_to_instsize(800), 1)
        self.assertEqual(enrollment_to_instsize(4500), 2)
        self.assertEqual(enrollment_to_instsize(8000), 3)
        self.assertEqual(enrollment_to_instsize(15000), 4)
        self.assertEqual(enrollment_to_instsize(25000), 5)
        self.assertIsNone(enrollment_to_instsize(None))


if __name__ == "__main__":
    unittest.main()
