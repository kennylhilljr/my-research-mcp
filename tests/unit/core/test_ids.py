"""Offline acceptance tests for identifier normalization."""

import unittest
from dataclasses import FrozenInstanceError

from hypothesis import given
from hypothesis import strategies as st

from research_mcp.core import ids


class IdentifierTests(unittest.TestCase):
    def test_doi(self):
        """AT-SRCH-10: Prefixes, resolvers, case and punctuation normalize."""
        for value in [
            "10.1145/ABC",
            " DOI:10.1145/ABC. ",
            "https://doi.org/10.1145/ABC",
            "http://dx.doi.org/10.1145/ABC,;",
            "doi:10.1145/ABC!?",
            '10.1145/ABC]."',
            "10.1145/ABC})",
        ]:
            with self.subTest(value=value):
                self.assertEqual(ids.normalize_doi(value), "10.1145/abc")
        self.assertEqual(ids.normalize_doi("10.1234/a(b)"), "10.1234/a(b)")
        self.assertEqual(ids.normalize_doi("10.1234/a[b]"), "10.1234/a[b]")
        self.assertEqual(ids.normalize_doi("10.1234/a{b}"), "10.1234/a{b}")
        self.assertEqual(ids.normalize_doi("10.1234/abc)."), "10.1234/abc")
        for value in ["10.1234/abc/", "https://doi.org/10.1234/abc/", "doi:10.1234/ABC/"]:
            with self.subTest(value=value):
                self.assertEqual(ids.normalize_doi(value), "10.1234/abc/")
        for value in [
            "",
            "10.123/x",
            "10.1234567890/x",
            "10.1234/",
            "10.1234/a b",
            "10.1234/alpha" + chr(0xA0) + "beta",
            "10.1234/alpha" + chr(0x2003) + "beta",
            "https://doi.org/10.1234/alpha" + chr(0xA0) + "beta",
            "https://example.org/10.1234/a",
        ]:
            with self.assertRaises(ids.IdentifierError):
                ids.normalize_doi(value)

    def test_arxiv(self):
        """AT-SRCH-11: Versions remain separate for modern and old arXiv IDs."""
        for value in [
            "2410.18291v1",
            "arXiv:2410.18291v1",
            "https://arxiv.org/abs/2410.18291v1",
            "https://arxiv.org/pdf/2410.18291v1.pdf",
        ]:
            self.assertEqual(ids.normalize_arxiv(value), ("2410.18291", 1))
        self.assertEqual(ids.normalize_arxiv("2410.18291"), ("2410.18291", None))
        self.assertEqual(ids.normalize_arxiv("HEP-TH/9901001v2"), ("hep-th/9901001", 2))
        self.assertEqual(ids.normalize_arxiv("math.ag/0301234"), ("math.AG/0301234", None))
        for value in ["2410.123", "2410.123456", "2410.18291v0", "hep-th/123", "x"]:
            with self.assertRaises(ids.IdentifierError):
                ids.normalize_arxiv(value)

    def test_canonical_forms(self):
        """AT-SRCH-12: All remaining scholarly identifier forms are canonical."""
        cases = [
            (ids.normalize_pmid, "pmid:12345", "12345"),
            (ids.normalize_pmcid, "pmcid:pmc12345", "PMC12345"),
            (ids.normalize_openalex, "https://api.openalex.org/works/w123", "W123"),
            (ids.normalize_openalex, "https://openalex.org/W123", "W123"),
            (ids.normalize_s2, "s2:" + "AB" * 20, "ab" * 20),
            (ids.normalize_core, "core:123", "123"),
            (ids.normalize_nct, "nct:01234567", "NCT01234567"),
            (ids.normalize_rfc, "RFC 0822", "822"),
            (ids.normalize_handle, "https://hdl.handle.net/123.45/AbC", "123.45/AbC"),
            (
                ids.normalize_dspace_uuid,
                "UUID:ABCDEF01-2345-6789-ABCD-0123456789AB",
                "abcdef01-2345-6789-abcd-0123456789ab",
            ),
        ]
        for normalizer, value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(normalizer(value), expected)
                with self.assertRaises(ids.IdentifierError):
                    normalizer("invalid value")

    def test_url(self):
        """AT-SRCH-13: URL cleanup preserves path case and meaningful query data."""
        self.assertEqual(
            ids.normalize_url(
                " HTTPS://Example.COM:443/Case/Path?utm_source=x&a=1&a=2&fbclid=x&empty=#frag "
            ),
            "https://example.com/Case/Path?a=1&a=2&empty=",
        )
        self.assertEqual(ids.normalize_url("HTTP://Example.COM:80"), "http://example.com/")
        self.assertEqual(
            ids.normalize_url("https://example.com:8443/A/"),
            "https://example.com:8443/A/",
        )
        self.assertEqual(ids.normalize_url("http://[::1]:80/A"), "http://[::1]/A")
        self.assertEqual(
            ids.normalize_url("https://example.org/Case?x=%FF"),
            "https://example.org/Case?x=%FF",
        )
        self.assertNotEqual(
            ids.normalize_url("https://example.org/Case?x=%FF"),
            ids.normalize_url("https://example.org/Case?x=%FE"),
        )
        self.assertEqual(
            ids.normalize_url("https://example.org/A?UTM_Medium=x&q=a+b&gclid=y"),
            "https://example.org/A?q=a+b",
        )
        for value in [
            "file:///tmp/x",
            "https://",
            "https://example.com:bad",
            "https://x/a b",
            "https://user:password@example.com/",
            "https://exam\x00ple.com/",
            "https://example.com/Pa\nper",
            "https://example.com/Pa\tper",
            "https://example.com/\x7f",
        ]:
            with self.assertRaises(ids.IdentifierError):
                ids.normalize_url(value)

    def test_detection(self):
        """AT-SRCH-14: Detect prefixes, hosts and shapes while rejecting filenames."""
        cases = [
            ("doi:10.1234/ABC", "doi", "10.1234/abc"),
            ("10.1234/ABC", "doi", "10.1234/abc"),
            ("2410.18291v1", "arxiv", "2410.18291"),
            ("https://arxiv.org/pdf/2410.18291.pdf", "arxiv", "2410.18291"),
            ("12345", "pmid", "12345"),
            ("PMC123", "pmcid", "PMC123"),
            ("W123", "openalex", "W123"),
            ("ab" * 20, "s2", "ab" * 20),
            ("core:123", "core", "123"),
            ("NCT01234567", "nct", "NCT01234567"),
            ("RFC822", "rfc", "822"),
            ("123.45/AbC", "handle", "123.45/AbC"),
            ("1234.56789/AbC", "handle", "1234.56789/AbC"),
            ("github:Owner/Repo", "github", "owner/repo"),
            ("https://github.com/Owner/Repo.git", "github", "owner/repo"),
            ("https://pubmed.ncbi.nlm.nih.gov/123/", "pmid", "123"),
            ("https://pmc.ncbi.nlm.nih.gov/articles/PMC123/", "pmcid", "PMC123"),
            ("https://api.openalex.org/works/W123", "openalex", "W123"),
            (
                "https://www.semanticscholar.org/paper/title/" + "ab" * 20,
                "s2",
                "ab" * 20,
            ),
            ("https://core.ac.uk/outputs/123", "core", "123"),
            ("https://clinicaltrials.gov/study/NCT01234567", "nct", "NCT01234567"),
            ("https://www.rfc-editor.org/rfc/rfc822.txt", "rfc", "822"),
            (
                "abcdef01-2345-6789-abcd-0123456789ab",
                "dspace_uuid",
                "abcdef01-2345-6789-abcd-0123456789ab",
            ),
            ("https://example.org/Paper.pdf", "url", "https://example.org/Paper.pdf"),
        ]
        for value, scheme, expected in cases:
            with self.subTest(value=value):
                ident = ids.parse_any(value)
                self.assertEqual((ident.scheme, ident.value), (scheme, expected))
        self.assertEqual(ids.parse_any("arxiv:2410.18291v1").version, 1)
        with self.assertRaises(FrozenInstanceError):
            ids.parse_any("W123").value = "W456"
        for value in [
            "unknown",
            "doi_10.1145_3649835",
            "core_123",
            "paper.pdf",
            "2410.18291.pdf",
            "arxiv:2410.18291.pdf",
            "doi:bad",
            "https://doi.org/10.1234/ab\ncd",
            "https://github.com/Own\ter/Repo",
        ]:
            with self.assertRaises(ids.IdentifierError):
                ids.parse_any(value)

    @given(
        number=st.integers(10000, 99999),
        digest=st.integers(0, 2**160 - 1),
        version_number=st.integers(1, 1000),
    )
    def test_properties(self, number, digest, version_number):
        """AT-SRCH-15: Generated inputs are idempotent and whitespace/case stable."""
        n = str(number)
        cases = [
            (ids.normalize_doi, "10.1234/a" + n, True),
            (ids.normalize_pmid, n, True),
            (ids.normalize_pmcid, "PMC" + n, True),
            (ids.normalize_openalex, "W" + n, True),
            (ids.normalize_s2, f"{digest:040x}", True),
            (ids.normalize_core, n, True),
            (ids.normalize_nct, "NCT000" + n, True),
            (ids.normalize_rfc, n, True),
            (ids.normalize_handle, "123/Ab" + n, False),
            (
                ids.normalize_dspace_uuid,
                "abcdef01-2345-6789-abcd-0123456789ab",
                True,
            ),
            (ids.normalize_github, "Owner/Repo" + n, True),
            (ids.normalize_url, "https://example.org/Case?x=" + n, False),
        ]
        for normalizer, value, case_insensitive in cases:
            expected = normalizer(value)
            self.assertEqual(normalizer(expected), expected)
            self.assertEqual(normalizer(" \t" + value + "\n"), expected)
            if case_insensitive:
                self.assertEqual(normalizer(value.swapcase()), expected)
        for base in ["2410." + n, "hep-th/99" + n, "math.AG/03" + n]:
            raw = f"ARXIV:{base}v{version_number}"
            canonical, version = ids.normalize_arxiv(raw)
            self.assertEqual(version, version_number)
            self.assertEqual(ids.normalize_arxiv(canonical), (canonical, None))
            self.assertEqual(ids.normalize_arxiv(f"{canonical}v{version}"), (canonical, version))
            self.assertEqual(ids.normalize_arxiv(" " + raw.swapcase() + " "), (canonical, version))
        self.assertEqual(
            ids.normalize_url("HTTPS://EXAMPLE.ORG/Case?x=" + n),
            "https://example.org/Case?x=" + n,
        )

    def test_title_key(self):
        """AT-SRCH-16: Titles use NFKC, casefold, punctuation and fixed stop words."""
        self.assertEqual(ids.title_key("The Ａrt of STRAẞE: A Study!"), "art strasse study")
        self.assertEqual(
            ids.title_key("  Models,\tand methods\nfor science."),
            "models methods science",
        )
        self.assertEqual(ids.title_key("Cafe\u0301"), ids.title_key("Café"))
        self.assertEqual(ids.title_key("the and of"), "")
        self.assertEqual(ids.title_key(""), "")
        self.assertEqual(ids.title_key("Graph-based learning"), "graph based learning")
