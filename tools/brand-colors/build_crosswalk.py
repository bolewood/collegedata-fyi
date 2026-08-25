#!/usr/bin/env python3
"""
build_crosswalk.py — bootstrap a brand-color scouting queue for US colleges
by cross-referencing three public sources instead of searching each school
from scratch.

Part of collegedata.fyi (https://collegedata.fyi), an open-source archive of
US college Common Data Set documents. This tool exists because manually
searching ~2,900 schools one at a time for a stated brand-color hex is the
slow part of populating a "brand_colors" field — this collapses that search
into a single join, leaving only verification (open the cited URL, confirm
the hex is actually printed there) to a human or agent.

INPUTS (three independent public sources, joined on school identity):

  1. Wikipedia's `Module:College_color/data` — a Lua data module maintained
     by Wikipedia's college sports editors, mapping ~1,550 NCAA team
     nicknames ("Iowa Hawkeyes") to 1-3 brand hex colors plus a citation
     (usually the school's own athletics brand-guide PDF, sometimes a
     third-party team-color site). Fetch with:

       curl -sL "https://en.wikipedia.org/w/index.php?title=Module:College_color/data&action=raw" \
         -o college_color_data.lua

  2. Wikipedia's "List of NCAA Division I/II/III institutions" — three
     tables mapping team nickname -> official school name + state. Needed
     because the color module is keyed by nickname, not school name. Fetch
     with (repeat for Division_II, Division_III):

       curl -sL "https://en.wikipedia.org/w/index.php?title=List_of_NCAA_Division_I_institutions&action=raw" \
         -o ncaa_Division_I.wikitext

  3. Your own institution directory — a CSV export of school_id / ipeds_id /
     school_name / state / brand_colors (so the tool only surfaces schools
     that actually need colors, and can join by IPEDS UNITID rather than
     fragile name matching). In this project:

       psql "$DATABASE_URL" -c "
         select school_id, ipeds_id, school_name, state,
                undergraduate_enrollment, (brand_colors is null) as needs_colors,
                brand_colors_confidence
         from institution_directory where in_scope = true
       " --csv -A -F',' > institution_directory_scope.csv

OUTPUT: a JSONL candidate queue, one row per matched school, each with a
candidate hex list, the citation URL, and a citation-quality tier (`edu` =
cites a .edu domain directly, `other` = cites a non-.edu source that isn't a
known-unofficial index, `trucolor`/`none` = excluded). Two files are
written: the full match set and a `_usable` subset filtered to
`needs_colors=true` and a citable tier.

THIS IS A HINT LIST, NOT A SOURCE OF TRUTH. Every row still requires a
human or agent to open `wikipedia_cite_url` and confirm the hex is actually
stated there before it goes into a database migration — Wikipedia's
transcription can be stale, wrong, or (rarely) copy-pasted from an adjacent
row. What this tool buys you is skipping the slowest part of manual
scouting: finding out whether an official page with a stated hex exists at
all, and where.

KNOWN LIMITATIONS:
  - NCAA-athletics-only. Coverage skews to D1/D2/D3 schools; two-year and
    non-athletic colleges never appear in Wikipedia's color module and need
    from-scratch scouting.
  - Multi-campus university systems (e.g. a state school with several
    IPEDS-listed satellite campuses) are deliberately left UNMATCHED rather
    than guessed, unless exactly one candidate is IPEDS-designated
    "-Main Campus" — see match_official_to_directory()'s docstring.
  - `match_score` reflects matcher confidence (how cleanly the school name
    matched), not brand-color confidence. Ignore it once a row is verified.
  - The matcher was iteratively hardened against real false positives found
    while using it across ~800 schools (Cincinnati main-vs-branch campus,
    Arizona vs Arizona State, Central Michigan vs Michigan, Siena vs NYU,
    Columbia University vs Columbia-Greene Community College, Penn State
    main vs branch campuses — see match_official_to_directory() comments).
    It is not guaranteed bug-free for cases not yet seen; spot-check a
    sample of any new run before trusting it wholesale.

USAGE:

    python3 build_crosswalk.py \\
      --lua college_color_data.lua \\
      --d1 ncaa_Division_I.wikitext --d2 ncaa_Division_II.wikitext --d3 ncaa_Division_III.wikitext \\
      --directory institution_directory_scope.csv \\
      --out-dir .

All arguments default to the same filenames in the current directory (as
listed above), so if you've fetched the four inputs into one folder you can
just run `python3 build_crosswalk.py` from there.

LICENSE NOTE: Wikipedia content is CC BY-SA 4.0. This script only reads and
transforms that content locally to build a work queue; it doesn't
redistribute the source data. If you publish the *output* candidate queue
(not just use it internally), attribute Wikipedia per CC BY-SA.
"""
import argparse
import csv
import json
import re
from pathlib import Path

STATE_NAMES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "New York (state)": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
    "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY", "Puerto Rico": "PR",
}

# ---------- 1. parse the Lua color module ----------

def parse_lua_module(path):
    """Parse Module:College_color/data's Lua table by hand (not a real Lua
    parser) -- a regex-only approach undercounts entries because citation
    values contain nested {{cite web ...}} wikitext braces two levels deep."""
    text = path.read_text()
    entries = {}   # key -> {hexes, cite_raw}
    aliases = {}   # alias key -> canonical key

    key_re = re.compile(r'\["((?:[^"\\]|\\.)*)"\]\s*=\s*')
    pos = 0
    n = len(text)
    while True:
        m = key_re.search(text, pos)
        if not m:
            break
        key = m.group(1)
        i = m.end()
        pos = i + 1
        if i >= n:
            continue
        if text[i] == '{':
            # manually find the matching closing brace (handles nested {{ }})
            depth = 0
            j = i
            in_str = False
            while j < n:
                c = text[j]
                if in_str:
                    if c == '\\':
                        j += 1
                    elif c == '"':
                        in_str = False
                elif c == '"':
                    in_str = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            body = text[i + 1:j]
            hexes = re.findall(r'"([0-9A-Fa-f]{6})"', body)
            cite_m = re.search(r'cite\s*=\s*"((?:[^"\\]|\\.)*)"', body)
            cite = cite_m.group(1) if cite_m else None
            entries[key] = {"hexes": hexes, "cite_raw": cite}
            pos = j + 1
        elif text[i] == '"':
            sm = re.match(r'"((?:[^"\\]|\\.)*)"', text[i:])
            if sm:
                aliases.setdefault(key, sm.group(1))
                pos = i + sm.end()
    return entries, aliases


def extract_cite_url(cite_raw):
    """Classify a citation's URL into a trust tier. `.edu` domains and other
    non-trucolor sources are kept as scouting candidates; trucolor.net (an
    unofficial hobbyist color-archive site) and uncited entries are not."""
    if not cite_raw:
        return None, "none"
    m = re.search(r'\|\s*url\s*=\s*([^|}]+)', cite_raw)
    url = m.group(1).strip() if m else None
    if not url:
        return None, "none"
    if "trucolor.net" in url:
        return url, "trucolor"
    if re.search(r'\.edu(/|$|[/?#])', url):
        return url, "edu"
    return url, "other"


# ---------- 2. parse NCAA institution list wikitext ----------

def clean_wikilink_text(s):
    """Return the *display* text of the first [[..]] link in s, or s stripped."""
    s = s.strip()
    m = re.search(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', s)
    if m:
        return (m.group(2) or m.group(1)).strip()
    # strip {{sort|key|[[Real Name]]}} wrapper
    m = re.search(r'\{\{sort\|[^|]*\|\[\[([^\]|]+)(?:\|([^\]]+))?\]\]\}\}', s, re.I)
    if m:
        return (m.group(2) or m.group(1)).strip()
    return re.sub(r'\{\{[^}]*\}\}', '', s).strip()


def strip_disambiguator(s):
    """Drop a trailing Wikipedia disambiguator, e.g. 'Siena University (New York)'
    -> 'Siena University' -- the parenthetical is an article-title artifact,
    not part of the school's actual name, and pollutes token matching."""
    return re.sub(r'\s*\([^)]*\)\s*$', '', s).strip()


def clean_link_target(s):
    """Return the *article title* (link target) of the first [[..]] link in s."""
    s = s.strip()
    m = re.search(r'\{\{sort\|[^|]*\|\[\[([^\]|]+)(?:\|[^\]]+)?\]\]\}\}', s, re.I)
    if m:
        return strip_disambiguator(m.group(1).strip())
    m = re.search(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', s)
    if m:
        return strip_disambiguator(m.group(1).strip())
    return strip_disambiguator(re.sub(r'\{\{[^}]*\}\}', '', s).strip())


def strip_refs(s):
    s = re.sub(r'\{\{refn[^}]*(\{\{[^}]*\}\}[^}]*)*\}\}', '', s, flags=re.I | re.S)
    s = re.sub(r'\{\{Ref label[^}]*\}\}', '', s, flags=re.I)
    s = re.sub(r'\{\{Abbr\|(?:\[\[[^\]]+\]\]|[^|}]+)\|[^}]+\}\}', lambda m: clean_wikilink_text(m.group(0)), s)
    return s


def parse_d1(path):
    """Division I's table has 8 columns: School / Common name / Nickname /
    City / State / Type / Subdivision / Primary conference."""
    text = strip_refs(path.read_text())
    rows = []
    blocks = text.split('\n|-')
    for block in blocks:
        cells = re.findall(r'\n\|([^\n]+)', '\n' + block)
        cells = [c.strip() for c in cells if c.strip() and not c.strip().startswith('style=')]
        if len(cells) < 5:
            continue
        school_cell, common_cell, nick_cell, city_cell, state_cell = cells[0], cells[1], cells[2], cells[3], cells[4]
        if '[[' not in school_cell:
            continue
        official = clean_link_target(school_cell)
        common = common_cell.strip()
        nickname = clean_wikilink_text(nick_cell)
        nickname = re.sub(r'\s*\{\{[^}]*\}\}', '', nickname).strip()
        state_txt = clean_wikilink_text(state_cell)
        state = STATE_NAMES.get(state_txt, state_txt if len(state_txt) == 2 else None)
        if not state:
            m = re.search(r'\b([A-Z]{2})\b', state_cell)
            state = m.group(1) if m else None
        rows.append({"official": official, "common": common, "nickname": nickname, "state": state, "division": "I"})
    return rows


def parse_dii_diii(path, division):
    """Division II/III tables have no "Common name" column, unlike Division
    I -- they're single-line rows: `!scope=row| School` then
    `| Nickname || City || State || Enrollment || Conference` on the next
    line."""
    text = strip_refs(path.read_text())
    rows = []
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'!\s*scope="?row"?\s*\|\s*(.+)', line)
        if m:
            school_cell = m.group(1)
            official = clean_link_target(school_cell)
            common_display = clean_wikilink_text(school_cell)
            # next non-empty line should hold nickname/city/state/...
            j = i + 1
            data_line = None
            while j < len(lines) and j < i + 3:
                if lines[j].strip().startswith('|') and not lines[j].strip().startswith('|-') and not lines[j].strip().startswith('|+'):
                    data_line = lines[j]
                    break
                j += 1
            if data_line:
                data_line = data_line.lstrip('|')
                parts = [p.strip() for p in data_line.split('||')]
                if parts:
                    nickname = clean_wikilink_text(parts[0])
                    state = None
                    if len(parts) >= 3:
                        state_txt = clean_wikilink_text(parts[2])
                        state = STATE_NAMES.get(state_txt, state_txt if len(state_txt) == 2 else None)
                    rows.append({
                        "official": official, "common": common_display, "nickname": nickname,
                        "state": state, "division": division,
                    })
        i += 1
    return rows


# ---------- 3. normalize + match ----------

GENERIC_WORDS = {"university", "college", "of", "the", "at", "institute", "technology",
                  "technical", "and", "&", "a&m", "a-m", "main", "campus"}
# "state" is deliberately NOT generic -- it's the disambiguator, not filler
# (Arizona vs Arizona State, Tennessee vs Tennessee State, Michigan vs
# Michigan State). Treating it as generic caused real false-match collisions
# during development.


def normalize_name(name):
    name = name.lower()
    name = name.replace("&", "and")
    name = re.sub(r'[^a-z0-9\s]', ' ', name)  # hyphens -> spaces too, so
    name = re.sub(r'\s+', ' ', name).strip()  # "Cincinnati-Main" tokenizes as two words
    # ceremonial legal-name suffix (e.g. "Columbia University in the City of
    # New York") -- strip it so it doesn't out-jaccard a plain short name.
    name = re.sub(r'\bin the city of\b.*$', '', name).strip()
    return name


def name_tokens(name):
    return set(normalize_name(name).split()) - {"of", "the", "at"}


def load_directory(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def match_official_to_directory(official, state, directory_by_state, directory_all, common=None):
    """Strict, asymmetric-safe matcher: exact name match, or a candidate whose
    *distinctive* (non-generic) tokens are a superset of the official name's
    distinctive tokens with at most two unexplained extra tokens (a
    branch/campus qualifier like "Main Campus" or "Ann Arbor" is tolerated;
    two schools that only differ by "State" or by a real place name are NOT
    silently guessed) -- this is a hint list feeding a namesake-collision-
    sensitive pipeline, so an unmatched row is far cheaper than a wrong one.

    This function's shape was hardened against several real false positives
    found while running it across ~800 schools:
      - "state" must stay a distinctive token, or Arizona/Arizona State,
        Tennessee/Tennessee State, etc. collide.
      - hyphens must tokenize as word separators, or "Cincinnati-Main
        Campus" fails to match "Cincinnati" at all.
      - Wikipedia article-title disambiguators like "Siena University (New
        York)" must be stripped, or the parenthetical state name spuriously
        matches a same-named different school (e.g. "New York University").
      - ceremonial legal names ("Columbia University in the City of New
        York") must be trimmed, or they lose to a short, unrelated,
        coincidentally-token-heavy name (e.g. "Columbia-Greene Community
        College") under naive scoring.
      - branch-campus ties (e.g. three "University of Michigan-X" IPEDS
        rows) are refused rather than guessed, UNLESS exactly one tied
        candidate is IPEDS-designated "-Main Campus" -- a real, meaningful
        flagship marker, not a guess, since NCAA rosters represent the
        flagship campus almost universally.
    """
    candidates = directory_by_state.get(state, []) if state else []
    if not candidates:
        candidates = directory_all

    # official names can carry ceremonial cruft ("... in the City of New
    # York") that pushes extra-token count over the cap and hides the real
    # match; the D1 table's short "common name" column (e.g. "Columbia") is
    # often cleaner. Try both bases per candidate and keep whichever is
    # tighter.
    bases = [official]
    if common and normalize_name(common) != normalize_name(official):
        bases.append(common)
    for basis in bases:
        norm_basis = normalize_name(basis)
        for row in candidates:
            if normalize_name(row["school_name"]) == norm_basis:
                return row, 1.0

    passing = {}  # school_id -> (row, extra_token_count, jaccard)
    for basis in bases:
        off_tokens = name_tokens(basis)
        off_distinctive = off_tokens - GENERIC_WORDS
        if not off_tokens or not off_distinctive:
            continue
        for row in candidates:
            row_tokens = name_tokens(row["school_name"])
            if not row_tokens:
                continue
            row_distinctive = row_tokens - GENERIC_WORDS
            if not off_distinctive.issubset(row_distinctive):
                continue
            extra = row_distinctive - off_distinctive
            if len(extra) > 2:
                continue
            inter = off_tokens & row_tokens
            union = off_tokens | row_tokens
            jaccard = len(inter) / len(union) if union else 0.0
            key = row["school_id"]
            if key not in passing or len(extra) < passing[key][1]:
                passing[key] = (row, len(extra), jaccard)
    passing = list(passing.values())
    if not passing:
        return None, 0.0
    passing.sort(key=lambda t: (t[1], -t[2]))
    best_row, best_extra, best_jaccard = passing[0]
    if len(passing) > 1:
        tied = [p for p in passing if p[1] == best_extra and abs(p[2] - best_jaccard) < 1e-9]
        if len(tied) > 1:
            main_campus_tied = [p for p in tied if "main campus" in normalize_name(p[0]["school_name"])]
            if len(main_campus_tied) == 1:
                best_row, best_extra, best_jaccard = main_campus_tied[0]
            else:
                return None, 0.0
    score = 0.9 - 0.15 * best_extra
    return best_row, score


def find_lua_key(all_keys, lua_entries, lua_aliases, common, nickname, official):
    """Resolve an NCAA (common, nickname) pair to a Module:College_color/data
    key. Tries the obvious "<common> <nickname>" / "<official> <nickname>"
    guesses first (exact key hits, no scoring needed), then falls back to a
    suffix search over every module key ending in the nickname, disambiguated
    by distinctive-token overlap between the key's prefix and the school's
    official/common name. Refuses (returns None) on a genuine tie -- e.g. two
    different schools both nicknamed "Wildcats" -- rather than guessing."""
    def resolve(key):
        if key in lua_entries:
            return key, lua_entries[key]
        if key in lua_aliases and lua_aliases[key] in lua_entries:
            return lua_aliases[key], lua_entries[lua_aliases[key]]
        return None, None

    for guess in (f"{common} {nickname}", f"{official} {nickname}"):
        k, d = resolve(guess)
        if d:
            return k, d
    if not nickname:
        return None, None
    nick_lower = nickname.lower()
    suffix_matches = [
        k for k in all_keys
        if k.lower() == nick_lower or k.lower().endswith(" " + nick_lower)
    ]
    if not suffix_matches:
        return None, None
    off_distinctive = (name_tokens(official) | name_tokens(common)) - GENERIC_WORDS
    passing = []  # (key, extra_count)
    for k in suffix_matches:
        prefix = k[: len(k) - len(nickname)].strip()
        prefix_distinctive = name_tokens(prefix) - GENERIC_WORDS
        if not prefix_distinctive or not off_distinctive:
            continue
        if prefix_distinctive.issubset(off_distinctive):
            extra = off_distinctive - prefix_distinctive
        elif off_distinctive.issubset(prefix_distinctive):
            extra = prefix_distinctive - off_distinctive
        else:
            continue
        if len(extra) > 2:
            continue
        passing.append((k, len(extra)))
    if not passing:
        return None, None
    passing.sort(key=lambda t: t[1])
    if len(passing) > 1 and passing[0][1] == passing[1][1]:
        return None, None  # genuine ambiguity (e.g. two same-nickname schools) -- refuse
    return resolve(passing[0][0])


def main():
    parser = argparse.ArgumentParser(
        description="Build a brand-color scouting candidate queue from Wikipedia + your institution directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--lua", default="college_color_data.lua", type=Path)
    parser.add_argument("--d1", default="ncaa_Division_I.wikitext", type=Path)
    parser.add_argument("--d2", default="ncaa_Division_II.wikitext", type=Path)
    parser.add_argument("--d3", default="ncaa_Division_III.wikitext", type=Path)
    parser.add_argument("--directory", default="institution_directory_scope.csv", type=Path)
    parser.add_argument("--out-dir", default=".", type=Path)
    args = parser.parse_args()

    lua_entries, lua_aliases = parse_lua_module(args.lua)
    print(f"Lua module: {len(lua_entries)} entries, {len(lua_aliases)} aliases")

    ncaa_rows = []
    ncaa_rows += parse_d1(args.d1)
    ncaa_rows += parse_dii_diii(args.d2, "II")
    ncaa_rows += parse_dii_diii(args.d3, "III")
    print(f"NCAA institution rows parsed: {len(ncaa_rows)}")

    directory = load_directory(args.directory)
    directory_by_state = {}
    for row in directory:
        directory_by_state.setdefault(row["state"], []).append(row)

    all_keys = list(lua_entries.keys())
    for alias_key, target in lua_aliases.items():
        if target in lua_entries:
            all_keys.append(alias_key)

    results = []
    unmatched_lua = 0
    unmatched_dir = 0
    for row in ncaa_rows:
        lua_key, lua_data = find_lua_key(all_keys, lua_entries, lua_aliases, row["common"], row["nickname"], row["official"])
        if not lua_data:
            unmatched_lua += 1
            continue
        dir_row, score = match_official_to_directory(
            row["official"], row["state"], directory_by_state, directory, common=row["common"]
        )
        if not dir_row:
            unmatched_dir += 1
            continue
        cite_raw = lua_data["cite_raw"]
        url, tier = extract_cite_url(cite_raw)
        results.append({
            "school_id": dir_row["school_id"],
            "ipeds_id": dir_row["ipeds_id"],
            "school_name": dir_row["school_name"],
            "state": dir_row["state"],
            "needs_colors": dir_row.get("needs_colors") == "t",
            "current_confidence": dir_row.get("brand_colors_confidence") or None,
            "ncaa_division": row["division"],
            "wikipedia_nickname_key": lua_key,
            "wikipedia_hexes": ["#" + h.upper() for h in lua_data["hexes"][:3]],
            "wikipedia_cite_tier": tier,
            "wikipedia_cite_url": url,
            "wikipedia_cite_raw": cite_raw,
            "match_score": round(score, 2),
        })

    print(f"Matched (both lua + directory): {len(results)}")
    print(f"  NCAA rows with no lua color entry: {unmatched_lua}")
    print(f"  NCAA rows with no directory match: {unmatched_dir}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with open(args.out_dir / "candidate_queue.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    needs = [r for r in results if r["needs_colors"]]
    by_tier = {}
    for r in needs:
        by_tier.setdefault(r["wikipedia_cite_tier"], 0)
        by_tier[r["wikipedia_cite_tier"]] += 1
    print(f"\nOf {len(results)} matched schools, {len(needs)} currently have brand_colors = NULL.")
    print("Citation tier breakdown among those NULL rows:")
    for tier, count in sorted(by_tier.items(), key=lambda x: -x[1]):
        print(f"  {tier}: {count}")

    usable = [r for r in needs if r["wikipedia_cite_tier"] in ("edu", "other")]
    with open(args.out_dir / "candidate_queue_usable.jsonl", "w") as f:
        for r in usable:
            f.write(json.dumps(r) + "\n")
    print(f"\nUsable (edu or other-cited, excludes trucolor/none) + needs_colors: {len(usable)} -> candidate_queue_usable.jsonl")


if __name__ == "__main__":
    main()
