#!/usr/bin/env python3
"""IR-hub discovery and Brave name-collision guards.

Homepage crawls often miss a Common Data Set that lives on an Institutional
Research / Institutional Effectiveness / fact-book page. This module:

- finds those hub URLs from homepage (and one About page) HTML, plus a
  short list of conventional paths and IR subdomains
- decides whether a search hit actually belongs to the queried school so
  a name search cannot steal George Mason's CDS for Northern Virginia CC,
  Azusa Pacific's for APUS, or BYU Provo's for BYU-Idaho

Network I/O stays in the caller. Keep extra fetches small: at most
MAX_IR_HUB_URLS hub pages and MAX_ABOUT_PAGES about pages per school.
"""
from __future__ import annotations

import html.parser
import re
import urllib.parse
from typing import Iterable

MAX_IR_HUB_URLS = 6
MAX_ABOUT_PAGES = 1

# Hub pages, not CDS-specific landings. Callers fetch these only after the
# homepage/landing crawl found no CDS, and stop at MAX_IR_HUB_URLS.
WELL_KNOWN_IR_HUB_PATHS: tuple[str, ...] = (
    "/institutional-research",
    "/institutional-research/",
    "/ir",
    "/ir/",
    "/institutional-effectiveness",
    "/institutional-effectiveness/",
    "/about/institutional-research",
    "/about/institutional-research/",
    "/oir",
    "/ie",
)

IR_SUBDOMAIN_LABELS: tuple[str, ...] = ("ir", "oir", "oira", "ira", "ie")

IR_TEXT_RE = re.compile(
    r"institutional\s+(?:research|effectiveness|analysis|assessment|planning)"
    r"|office of institutional"
    r"|fact[\s-]?books?"
    r"|\b(?:OIR|OIRA|IRA|IEA)\b"
    r"|(?<![A-Za-z])IR(?![A-Za-z])",
    re.I,
)
IR_PATH_RE = re.compile(
    r"/(?:institutional[-_ ]?(?:research|effectiveness|analysis|assessment)"
    r"|office-of-institutional-[^/]+"
    r"|fact[-_]?books?|factbook"
    r"|oir|oira|ira|iea)(?:/|$)",
    re.I,
)
IR_SHORT_PATH_RE = re.compile(r"(?:^|/)ir(?:/|$)", re.I)

ABOUT_TEXT_RE = re.compile(
    r"^about(?:\s|$)|about (?:us|the (?:college|university|school)\b)",
    re.I,
)
ABOUT_PATH_RE = re.compile(r"/about(?:-[a-z0-9]+)?(?:/|$)", re.I)

SKIP_PATH_RE = re.compile(
    r"/(?:admissions?|apply|financial-aid|news|athletics|library|bookstore"
    r"|careers?|jobs?|alumni|give|donate|login|my[-_]?tcc)(?:/|$)",
    re.I,
)

_NAME_STOPWORDS = {
    "the",
    "of",
    "at",
    "and",
    "for",
    "in",
    "a",
    "an",
    "college",
    "university",
    "community",
    "campus",
    "district",
    "system",
    "state",
    "county",
    "inc",
}


class _AnchorParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = ""
        for key, value in attrs:
            if key.lower() == "href":
                href = value or ""
                break
        self._href = href
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = " ".join(self._text)
            self.anchors.append((self._href, text))
            self._href = None
            self._text = []


def parse_anchors(html: str) -> list[tuple[str, str]]:
    """Return (href, link_text) pairs from HTML. Never executes markup."""
    parser = _AnchorParser()
    try:
        parser.feed(html or "")
    except (AssertionError, ValueError):
        return []
    return parser.anchors


def _absolute_http_url(href: str, base_url: str) -> str | None:
    if not href or re.match(r"^(#|mailto:|tel:|javascript:)", href, re.I):
        return None
    try:
        absolute = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(absolute)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return urllib.parse.urldefrag(absolute)[0]


def normalize_host(host: str | None) -> str:
    host = (host or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def host_belongs_to_domain(url: str, domain: str) -> bool:
    """True when the URL is on the school's own host, not a random search hit."""
    host = normalize_host(urllib.parse.urlparse(url).hostname)
    domain = normalize_host(domain)
    if not host or not domain:
        return False
    return host == domain or host.endswith("." + domain)


def _registrable_domain(host: str) -> str:
    host = normalize_host(host)
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _is_ir_subdomain(host: str, school_domain: str) -> bool:
    host = normalize_host(host)
    school_domain = normalize_host(school_domain)
    if not host or not school_domain:
        return False
    labels = host.split(".")
    if not labels:
        return False
    return labels[0] in IR_SUBDOMAIN_LABELS and (
        host == school_domain
        or host.endswith("." + school_domain)
        or _registrable_domain(host) == _registrable_domain(school_domain)
    )


def same_institution_host(url: str, page_url: str) -> bool:
    """Allow the landing host, its subdomains, and IR office subdomains."""
    try:
        page_host = urllib.parse.urlparse(page_url).hostname
        url_host = urllib.parse.urlparse(url).hostname
    except ValueError:
        return False
    page_host = normalize_host(page_host)
    url_host = normalize_host(url_host)
    if not page_host or not url_host:
        return False
    if url_host == page_host or url_host.endswith("." + page_host) or page_host.endswith(
        "." + url_host
    ):
        return True
    return _is_ir_subdomain(url_host, page_host)


def _path_looks_like_ir(path: str) -> bool:
    path = urllib.parse.unquote(path or "").lower()
    if IR_PATH_RE.search(path):
        return True
    return bool(IR_SHORT_PATH_RE.search(path))


def extract_ir_hub_links(html: str, base_url: str, *, limit: int = MAX_IR_HUB_URLS) -> list[str]:
    """IR / IE / fact-book hubs linked from a homepage or about page."""
    seen: set[str] = set()
    out: list[str] = []
    for href, text in parse_anchors(html):
        absolute = _absolute_http_url(href, base_url)
        if not absolute or absolute in seen:
            continue
        if not same_institution_host(absolute, base_url):
            continue
        path = urllib.parse.urlparse(absolute).path or ""
        if SKIP_PATH_RE.search(path):
            continue
        label = re.sub(r"\s+", " ", text or "").strip()
        if not (IR_TEXT_RE.search(label) or _path_looks_like_ir(path)):
            continue
        seen.add(absolute)
        out.append(absolute)
        if len(out) >= limit:
            break
    return out


def extract_about_links(html: str, base_url: str, *, limit: int = MAX_ABOUT_PAGES) -> list[str]:
    """About-page URLs used as a single extra hop toward an IR office."""
    seen: set[str] = set()
    out: list[str] = []
    for href, text in parse_anchors(html):
        absolute = _absolute_http_url(href, base_url)
        if not absolute or absolute in seen:
            continue
        if not same_institution_host(absolute, base_url):
            continue
        path = urllib.parse.urlparse(absolute).path or ""
        if SKIP_PATH_RE.search(path):
            continue
        label = re.sub(r"\s+", " ", text or "").strip()
        if not (ABOUT_TEXT_RE.search(label) or ABOUT_PATH_RE.search(path)):
            continue
        # Skip the current page.
        if urllib.parse.urldefrag(absolute)[0] == urllib.parse.urldefrag(base_url)[0]:
            continue
        seen.add(absolute)
        out.append(absolute)
        if len(out) >= limit:
            break
    return out


def well_known_ir_hub_urls(page_url: str, *, limit: int = MAX_IR_HUB_URLS) -> list[str]:
    """Conventional IR hub paths on the landing page's origin."""
    try:
        parsed = urllib.parse.urlparse(page_url)
    except ValueError:
        return []
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return []
    origin = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        origin = f"{origin}:{parsed.port}"
    urls: list[str] = []
    seen: set[str] = set()
    for path in WELL_KNOWN_IR_HUB_PATHS:
        url = origin + path
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def ir_subdomain_homepages(domain: str) -> list[str]:
    """ira.school.edu-style office homepages. Caller DNS-short-circuits."""
    domain = normalize_host(domain)
    if not domain:
        return []
    return [f"https://{label}.{domain}/" for label in IR_SUBDOMAIN_LABELS]


def collect_ir_hub_candidates(
    html: str,
    page_url: str,
    *,
    about_pages: Iterable[tuple[str, str]] = (),
    domain: str = "",
    include_well_known: bool = True,
    include_subdomains: bool = False,
    limit: int = MAX_IR_HUB_URLS,
) -> list[str]:
    """Merge homepage links, about-page links, well-known paths, optional IR hosts.

    Order is load-bearing: follow a real IR link (Tulsa's
    /about-tcc/institutional-research) before guessing /ir.
    """
    seen: set[str] = set()
    out: list[str] = []

    def _add(url: str) -> None:
        if not url or url in seen or len(out) >= limit:
            return
        seen.add(url)
        out.append(url)

    for url in extract_ir_hub_links(html, page_url, limit=limit):
        _add(url)
    for about_url, about_html in about_pages:
        if len(out) >= limit:
            break
        for url in extract_ir_hub_links(about_html, about_url, limit=limit):
            _add(url)
    if include_well_known:
        for url in well_known_ir_hub_urls(page_url, limit=limit):
            _add(url)
    if include_subdomains and domain:
        for url in ir_subdomain_homepages(domain):
            _add(url)
    return out[:limit]


def distinctive_name_tokens(name: str) -> tuple[str, ...]:
    """Tokens that identify a school after dropping generic higher-ed words."""
    raw = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
    tokens = [tok for tok in raw.split() if tok and tok not in _NAME_STOPWORDS]
    return tuple(tokens)


def _haystack(url: str, title: str, description: str) -> str:
    return " ".join(
        re.sub(r"[^a-z0-9]+", " ", part.lower())
        for part in (url, title, description)
        if part
    )


def name_tokens_match_document(school_name: str, haystack: str) -> bool:
    tokens = distinctive_name_tokens(school_name)
    if not tokens:
        return False
    blob = f" {haystack} "
    return all(f" {tok} " in blob for tok in tokens)


def other_school_owns_host(
    url: str,
    school_domain: str,
    other_domains: Iterable[str],
) -> bool:
    """True when the hit lives on a different school's known host."""
    if host_belongs_to_domain(url, school_domain):
        return False
    for domain in other_domains:
        if domain and normalize_host(domain) != normalize_host(school_domain):
            if host_belongs_to_domain(url, domain):
                return True
    return False


def better_name_match_exists(
    school_name: str,
    haystack: str,
    other_names: Iterable[str],
) -> bool:
    """Reject when another institution's name fits the document more tightly.

    BYU-Idaho's tokens are a superset of BYU Provo's. A Provo page that only
    says "Brigham Young University" must not count for Idaho; an Idaho page
    that also says "Idaho" must not count for Provo.
    """
    query_tokens = set(distinctive_name_tokens(school_name))
    query_hits = sum(1 for tok in query_tokens if f" {tok} " in f" {haystack} ")
    for other in other_names:
        if not other or other.lower() == (school_name or "").lower():
            continue
        other_tokens = set(distinctive_name_tokens(other))
        if not other_tokens:
            continue
        other_hits = sum(1 for tok in other_tokens if f" {tok} " in f" {haystack} ")
        if other_hits == len(other_tokens) and other_hits > query_hits:
            return True
        # Sibling campuses: other has extra place tokens the query lacks.
        extra = other_tokens - query_tokens
        if extra and all(f" {tok} " in f" {haystack} " for tok in extra):
            if other_hits >= query_hits:
                return True
    return False


def result_matches_school(
    url: str,
    title: str,
    description: str,
    *,
    school_name: str,
    school_domain: str,
    other_names: Iterable[str] = (),
    other_domains: Iterable[str] = (),
) -> bool:
    """A Brave hit counts only when the host or the institution name matches.

    Off-domain hits are allowed only when the document names this school and
    does not name a different known school more specifically.
    """
    if not url:
        return False
    if host_belongs_to_domain(url, school_domain):
        return True
    if other_school_owns_host(url, school_domain, other_domains):
        return False
    haystack = _haystack(url, title, description)
    if not name_tokens_match_document(school_name, haystack):
        return False
    if better_name_match_exists(school_name, haystack, other_names):
        return False
    return True


def enrollment_to_instsize(enrollment: int | str | None) -> int | None:
    """Map undergraduate enrollment onto IPEDS INSTSIZE buckets 1-5."""
    try:
        n = int(enrollment)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    if n < 1000:
        return 1
    if n < 5000:
        return 2
    if n < 10000:
        return 3
    if n < 20000:
        return 4
    return 5
