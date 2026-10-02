"""Classify Supabase gateway log groups for PRD 032 usage capture.

Pure functions only. The ingest job feeds grouped log dimensions in and gets
aggregate rows out. Nothing returned from here may contain an IP address, a
full user agent, or a query string.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import unquote_plus

INTERNAL = "internal_pipeline"
FRIENDLY = "friendly_api_upstream"
FIRST_PARTY = "first_party_site"
BROWSER = "browser_unattributed"
THIRD_PARTY = "third_party"
CLASSIFICATIONS = (INTERNAL, FRIENDLY, FIRST_PARTY, BROWSER, THIRD_PARTY)

# When the site started sending X-Client-Info: collegedata-web/<sha>
# (web/src/lib/client-info.ts). Hours that start before this use the
# pre-tagging inference rules and are flagged inferred. None means the
# tagged build has not shipped yet, so every hour is pre-tagging.
SITE_TAGGING_T0: datetime | None = datetime(2026, 10, 1, 19, 16, tzinfo=timezone.utc)

SITE_CLIENT_INFO_PREFIX = "collegedata-web"
FRIENDLY_CLIENT_INFO_PREFIX = "collegedata-friendly-api"
FIRST_PARTY_REFERER_HOSTS = ("collegedata.fyi", "www.collegedata.fyi")
INTERNAL_UA_MARKERS = ("collegedata-pipeline", "collegedata-fyi")
KNOWN_HOSTS = frozenset({"api.collegedata.fyi", "isduwmygvmdozhpvzaix.supabase.co"})
INTERNAL_FUNCTIONS = frozenset({
    "archive-enqueue",
    "archive-process",
    "archive-upload",
    "directory-enqueue",
    "discover",
    "refresh-coverage",
})
ARCHIVE_PREFIX = "/storage/v1/object/public/sources/"

# RE2- and Python-compatible; the SQL builder embeds NON_BROWSER_PATTERN so
# the database-side browser flag and the Python check agree.
_BOT_WORDS = "bot|crawler|spider|crawl|slurp|indexer|fetcher|scraper|archiver|externalagent|externalhit"
_AI_WORDS = "claude|anthropic|chatgpt|openai|perplexity|copilot"
# Matched against the lowercased user agent. A marker word must end a product
# token (followed by '/', ';', ')' or the end), so phone models such as
# "CUBOT X30" stay browsers while "GPTBot/1.2" and "(FendodoRubricBot)" match.
_TOKEN_END = "[a-z0-9_.-]*([/;)]|$)"
# Crawlers without a bot word, from COUNTER-Robots checked against real
# traffic (PRD 033 M0), and automation that looks like a browser.
_CRAWLER_TOKENS = (
    "googleother|google-inspectiontool|mediapartners-google|adsbot-google|"
    "feedfetcher-google|storebot-google|google-safety|skypeuripreview"
)
_AUTOMATION_TOKENS = "headlesschrome|google-apps-script|phantomjs"
BOT_PATTERN = f"({_BOT_WORDS}){_TOKEN_END}|{_CRAWLER_TOKENS}"
NON_BROWSER_PATTERN = f"({_BOT_WORDS}|{_AI_WORDS}){_TOKEN_END}|{_CRAWLER_TOKENS}|{_AUTOMATION_TOKENS}"
_BOT_RE = re.compile(BOT_PATTERN)
_NON_BROWSER_RE = re.compile(NON_BROWSER_PATTERN)
_URL_RE = re.compile(r"\+?https?://\S+|\+?[\w.-]+@[\w.-]+")
_COMPATIBLE_RE = re.compile(r"compatible;\s*([A-Za-z][\w.-]*)(?:/([\w.+-]+))?", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(
    rf"((?:[A-Za-z][\w.-]*?)?(?:{_BOT_WORDS}|{_CRAWLER_TOKENS})[\w.-]*)(?:/([\w.+-]+))?", re.IGNORECASE
)
_AI_TOKEN_RE = re.compile(rf"([\w.-]*(?:{_AI_WORDS})[\w.-]*)(?:/([\w.+-]+))?", re.IGNORECASE)
_PRODUCT_RE = re.compile(r"^\s*([A-Za-z0-9][\w.@+-]*)(?:/([\w.+-]+))?")
_ROUTE_NAME_RE = re.compile(r"[a-z0-9_][a-z0-9_-]{0,63}")
_SCHOOL_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,99}")
_TOKEN_CLEAN_RE = re.compile(r"[^a-zA-Z0-9._:/@+-]")
_ORG_CLEAN_RE = re.compile(r"[^\w .,&()'-]")

# AI clients split by intent (PRD 033). Agents fetch because a person asked;
# crawlers collect for indexing or training. Tokens are matched as
# lowercase substrings and take precedence over the vendor-word fallback.
AI_USER_TOKENS = (
    "chatgpt-user", "claude-user", "perplexity-user", "mistralai-user",
    "meta-externalfetcher", "duckassistbot",
)
AI_CRAWLER_TOKENS = (
    "gptbot", "oai-searchbot", "claudebot", "claude-searchbot", "anthropic-ai",
    "perplexitybot", "ccbot", "bytespider", "amazonbot", "applebot-extended",
    "meta-externalagent", "google-extended", "cohere-ai", "ai2bot", "youbot",
)
AI_FAMILIES = ("ai_user", "ai_crawler")

# Unique downloads (PRD 033): one client key (IP + user agent) x one archive
# file x one UTC day. Bump DOWNLOADS_METHOD_VERSION whenever a rule here or
# in queries.daily_downloads_sql changes the counts; the public page marks
# each version change on its charts.
DOWNLOADS_METHOD_VERSION = 1
# A browser key fetching more distinct files than this in a day counts as a
# machine. Real browser keys rarely pass 10 files a day (Sept 2026 logs).
HEAVY_CLIENT_FILES = 30
ACCESS_METHODS = ("browser", "machine", "bots_crawlers", "excluded")
BOT_FAMILIES = ("declared_bot", "ai_crawler")

GENERIC_PRODUCTS = frozenset({
    "mozilla", "curl", "wget", "python-requests", "python-urllib", "python-httpx",
    "httpx", "aiohttp", "node", "node-fetch", "undici", "axios", "got", "deno",
    "bun", "go-http-client", "okhttp", "java", "apache-httpclient", "libwww-perl",
    "ruby", "php", "guzzlehttp", "postmanruntime", "insomnia", "dart", "reqwest",
    "powershell", "pg_net",
})


@dataclass(frozen=True)
class Signals:
    """Classification inputs for one log group. No raw identifiers."""

    role: str = ""
    key_prefix: str = ""
    client_info: str = ""
    referer_host: str = ""
    ua_browser: bool = False
    ua_internal: bool = False
    aws: bool = False
    before_t0: bool = True
    surface: str = ""
    route_kind: str = ""


def t0_hour(t0: datetime | None) -> datetime | None:
    """Last hour that still uses pre-tagging inference (the hour containing T0)."""
    return t0.replace(minute=0, second=0, microsecond=0) if t0 else None


def is_before_t0(hour: datetime, t0: datetime | None) -> bool:
    cutoff = t0_hour(t0)
    return cutoff is None or hour <= cutoff


def ua_is_bot(ua: str) -> bool:
    return bool(_BOT_RE.search(ua.lower()))


def ua_is_browser(ua: str) -> bool:
    """Browser-shaped and not a self-declared bot or AI agent.

    Real browsers always carry a platform section, so a bare "Mozilla/5.0"
    (a common scraper default) is not a browser.
    """
    return ua.startswith("Mozilla/") and "(" in ua and not _NON_BROWSER_RE.search(ua.lower())


def ua_is_internal(ua: str) -> bool:
    low = ua.lower()
    return any(marker in low for marker in INTERNAL_UA_MARKERS)


def classify(s: Signals) -> tuple[str, bool]:
    """Return (classification, inferred). Order matters; see PRD 032."""
    if (
        s.role == "service_role"
        or s.key_prefix.startswith("sb_secret_")
        or s.ua_internal
        or (s.surface == "edge_function" and s.route_kind in INTERNAL_FUNCTIONS)
    ):
        return INTERNAL, False
    if s.client_info.startswith(FRIENDLY_CLIENT_INFO_PREFIX):
        return FRIENDLY, False
    if s.client_info.startswith(SITE_CLIENT_INFO_PREFIX) or s.referer_host in FIRST_PARTY_REFERER_HOSTS:
        return FIRST_PARTY, False
    if s.before_t0:
        if s.role == "anon" and s.client_info.startswith("supabase-js-node") and s.aws:
            return FIRST_PARTY, True
        if s.role == "anon" and s.client_info.startswith("supabase-js-web"):
            return FIRST_PARTY, True
        if s.surface == "storage" and s.ua_browser:
            return BROWSER, True
    if s.ua_browser:
        return BROWSER, False
    return THIRD_PARTY, False


def safe_route_name(value: str) -> str:
    value = value or ""
    return value if _ROUTE_NAME_RE.fullmatch(value) else "invalid"


def edge_route(svc: str, seg4: str, seg5: str, is_archive: bool, method: str) -> tuple[str, str]:
    """Map gateway path segments to (surface, route_kind).

    seg4 and seg5 are the 4th and 5th '/'-separated path parts
    (/rest/v1/<seg4>/<seg5>), matching ClickHouse splitByChar indexing.
    """
    if svc == "rest":
        surface = "postgrest"
        if seg4 == "":
            route = "root"
        elif seg4 == "rpc":
            route = f"rpc:{safe_route_name(seg5)}"
        else:
            route = safe_route_name(seg4)
    elif svc == "storage":
        surface = "storage"
        route = "archive_file" if is_archive else "storage_other"
    elif svc == "functions":
        surface = "edge_function"
        route = safe_route_name(seg4)
    elif svc == "auth":
        surface, route = "auth", "auth"
    else:
        surface, route = "other", "other"
    if method.upper() == "OPTIONS":
        route = "options_preflight"
    return surface, route


def function_route(pathname: str, method: str) -> tuple[str, str]:
    parts = [part for part in (pathname or "").split("/") if part]
    if parts[:2] == ["functions", "v1"]:
        parts = parts[2:]
    route = safe_route_name(parts[0]) if parts else "root"
    if method.upper() == "OPTIONS":
        route = "options_preflight"
    return "edge_function", route


def status_class(status: object) -> str:
    text = str(status or "")
    if len(text) == 3 and text.isdigit() and text[0] in "2345":
        return f"{text[0]}xx"
    return "other"


def normalize_host(host: str) -> str:
    host = (host or "").lower()
    return host if host in KNOWN_HOSTS else "other"


def school_id_from(raw: str) -> str | None:
    if not raw:
        return None
    value = unquote_plus(raw)
    return value if _SCHOOL_ID_RE.fullmatch(value) else None


def clean_token(value: str | None, max_length: int = 80) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"-+", "-", _TOKEN_CLEAN_RE.sub("-", value.strip()[:max_length]))
    return cleaned or None


def clean_org(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _ORG_CLEAN_RE.sub("", value)[:120].strip()
    return cleaned or None


def clean_country(value: str | None) -> str | None:
    value = (value or "").strip().upper()
    return value if re.fullmatch(r"[A-Z]{2}", value) else None


def user_agent_family(ua: str) -> str:
    """Port of userAgentFamily in web/src/lib/api-usage.ts, plus urllib/httpx."""
    low = (ua or "").lower()
    if not low:
        return "unknown"
    if "claude" in low or "anthropic" in low:
        return "ai_agent"
    if "chatgpt" in low or "openai" in low:
        return "ai_agent"
    if "perplexity" in low or "copilot" in low:
        return "ai_agent"
    if "curl/" in low:
        return "curl"
    if any(token in low for token in ("python-requests", "aiohttp", "python-urllib", "httpx")):
        return "python"
    if low == "node" or "node-fetch" in low or "undici" in low:
        return "node_fetch"
    if "mozilla/" in low:
        return "browser"
    return "script"


def product_token(ua: str) -> tuple[str | None, str | None]:
    match = _PRODUCT_RE.match(ua or "")
    if not match:
        return None, None
    return match.group(1), match.group(2)


def ai_family(ua: str) -> str | None:
    """ai_user, ai_crawler, or None when the user agent is not an AI client."""
    low = (ua or "").lower()
    if any(token in low for token in AI_USER_TOKENS):
        return "ai_user"
    if any(token in low for token in AI_CRAWLER_TOKENS):
        return "ai_crawler"
    if user_agent_family(ua) != "ai_agent":
        return None
    # Contact URLs such as "+https://openai.com/bot" must not make an agent
    # look like a crawler.
    return "ai_crawler" if ua_is_bot(_URL_RE.sub(" ", low)) else "ai_user"


def client_family(ua: str, client_info: str = "") -> str:
    family = user_agent_family(ua)
    ai = ai_family(ua)
    if ai:
        return ai
    if ua_is_bot(ua or ""):
        return "declared_bot"
    if family == "browser":
        return "browser" if ua_is_browser(ua) else "script"
    if client_info.startswith("supabase-"):
        return "integration"
    product, _ = product_token(ua)
    if product and product.lower() not in GENERIC_PRODUCTS:
        return "integration"
    if family in ("curl", "python", "node_fetch", "script"):
        return "script"
    return "unknown"


def client_name_version(ua: str, family: str, client_info: str = "") -> tuple[str | None, str | None]:
    """Self-declared product name and version. Never the full user agent."""
    name: str | None = None
    version: str | None = None
    if family in ("declared_bot", *AI_FAMILIES):
        text = _URL_RE.sub(" ", ua or "")
        token_res = (_BOT_TOKEN_RE,) if family == "declared_bot" else (_AI_TOKEN_RE, _BOT_TOKEN_RE)
        for regex in (_COMPATIBLE_RE, *token_res):
            match = regex.search(text)
            if match:
                name, version = match.group(1), match.group(2)
                break
        else:
            name, version = product_token(text)
        if name and name.lower() in GENERIC_PRODUCTS:
            name, version = None, None
    elif family == "integration":
        name, version = product_token(ua)
        if (not name or name.lower() in GENERIC_PRODUCTS) and client_info:
            name, version = product_token(client_info)
    return clean_token(name), clean_token(version, 20)


def access_method(ua: str, family: str, internal: bool, heavy: bool) -> str:
    """Access method for one unique download (PRD 033).

    internal means a service-role or secret key or the friendly API's
    client info; heavy means the client key passed HEAVY_CLIENT_FILES.
    """
    if internal or ua_is_internal(ua):
        return "excluded"
    if family in BOT_FAMILIES:
        return "bots_crawlers"
    if family == "browser" and not heavy:
        return "browser"
    return "machine"


def rollup_family(classification: str, ua: str, client_info: str) -> str:
    if classification in (INTERNAL, FRIENDLY, FIRST_PARTY):
        return "first_party"
    return client_family(ua, client_info)


def client_hash(salt_hex: str, ip: str, ua: str, ja4: str) -> str:
    key = bytes.fromhex(salt_hex)
    message = "\x1f".join((ip or "", ua or "", ja4 or "")).encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:16]


def hour_from_epoch(value: object) -> datetime:
    return datetime.fromtimestamp(int(value), tz=timezone.utc)
