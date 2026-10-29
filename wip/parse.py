"""Bulgaria: read the cache only and write corpus.json (SCHEMA.md in scripts/gitlaw_common).

The Constitution, as the National Assembly publishes it:
- today's text from the parliament.bg API (/api/v1/nav/bg/const);
- earlier texts from Internet Archive `id_` captures of the old server-rendered page parliament.bg/bg/const
  (2010 to 2021), pinned below by capture timestamp (WB_PICKS; fetch.py --history chose them).

Every source goes through the same code: its HTML is cut to lines (html_lines) and split into provisions
(split_units), so a site redesign that changes no words gives identical units. Changes between versions are
credited to an amending event only where the provision's own amendment note names that event's gazette issue.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
WB_CACHE = CACHE / "wb"
CONST_URL = "https://www.parliament.bg/api/v1/nav/bg/const"
PAGE_URL = "https://www.parliament.bg/bg/const"
RETRIEVED = "2026-10-29"   # .cache/requests.jsonl: the API response was fetched at 2026-10-29T00:01:43Z

# One complete Internet Archive capture per distinct text, oldest first: (capture timestamp, archived URL).
# fetch.py --history surveyed the captures and wrote wayback_survey.json (which captures were read, and the
# text hash each one parsed to). The survey read 46 of the 314 old-page captures: every one from 2010-12-22 to
# 2016-01-16 parses to the first text (the 2007 one), every one from 2016-01-25 to 2021-05-06 to the second (2015);
# the API captured on 2021-06-29 parses to that same second text, and the API captured on 2025-08-20 is
# byte-identical to today's response.
WB_PICKS: list[tuple[str, str]] = [
    ("20101222212318", "http://parliament.bg/bg/const/"),
    ("20160125101631", "http://www.parliament.bg/bg/const/"),
]

# The in-force day of each gazette event, where it is not the default (promulgation + 3 days, Constitution
# чл. 5, ал. 5 for laws and чл. 151, ал. 2 for Constitutional Court decisions), from the events' own clauses as the
# text prints them.
OWN_IN_FORCE = {
    "dv-1991-56": ("1991-07-13", "the header: \"в сила от 13.07.1991 г.\"; § 9 of the Constitution: in force from "
                                 "the day of its promulgation"),
}
# Parts of an event that took effect later than the event itself, by its own clause. A text that contains the event
# is dated no earlier than these days.
LATE_PARTS = {
    "dv-2003-85": ("2004-01-01", "§ 7 of the 2003 law: \"Параграф 1, т. 3 влиза в сила от 1 януари 2004 г.\" "
                                 "(the note on чл. 129: \"в сила от 01.01.2004 г.\")"),
    "dv-2005-18": ("2007-01-01", "§ 7 of the 2005 law: § 2 in force from the entry into force of the EU Accession "
                                 "Treaty (the note on чл. 22: \"в сила от 01.01.2007 г.\")"),
    "dv-2007-12": ("2008-01-01", "§ 13 of the 2007 law: \"Параграфи 1 и 2 влизат в сила от 1 януари 2008 г.\" "
                                 "(the notes on чл. 9 and чл. 59: \"в сила от 01.01.2008 г.\")"),
}
PLACEHOLDER = "[Източникът не дава текста, действащ на тази дата.]"

SHY_DASH = re.compile(r"[ \t]+[\x1f­][ \t]+")


WB_RETRIEVED = "2026-10-29"  # .cache/wb/requests.jsonl


def wb_requests() -> int:
    log = WB_CACHE / "requests.jsonl"
    return sum(1 for line in log.read_text(encoding="utf-8").splitlines() if line.strip()) if log.exists() else 0


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode("utf-8")).hexdigest()


def wb_url(ts: str, url: str) -> str:
    return f"https://web.archive.org/web/{ts}id_/{url}"


def wb_path(ts: str, url: str) -> Path:
    return WB_CACHE / hashlib.sha256(wb_url(ts, url).encode("utf-8")).hexdigest()


def norm(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace(" ", " ")
    # The source types a dash in amendment notes as a stray control character (U+001F in the API text) or a soft
    # hyphen (U+00AD in the old page): "(Изм. \x1f ДВ, ...", "предишна ал. 3 -\x1f ДВ". Standing alone it is the
    # dash; next to a dash it is dropped.
    s = SHY_DASH.sub(" - ", s).replace("\x1f", "").replace("­", "")
    s = s.replace("–", "-").replace("—", "-").replace("„", '"').replace("“", '"').replace("”", '"')
    s = re.sub(r"\s+", " ", s)
    return s.strip()


BLOCK = re.compile(r"<br\s*/?>|</?(?:p|div|hr|h[1-6]|li|ul|ol|table|tr|td|th|center)\b[^>]*>", re.I)


def html_lines(fragment: str) -> list[str]:
    """One line per paragraph or <br>-separated item, whatever the site's markup."""
    out = []
    for chunk in BLOCK.split(fragment):
        t = norm(chunk)
        if t and not re.fullmatch(r"[.\s]+", t):
            out.append(t)
    return out


def api_lines(raw: bytes) -> list[str]:
    return html_lines(json.loads(raw.decode("utf-8"))["C_ArL_body"])


def page_lines(raw: bytes) -> list[str]:
    """The old server-rendered page (2010-2021): the text is the `articlebody` block of the left column."""
    s = raw.decode("utf-8")
    i = s.index('class="articlebody"')
    i = s.index(">", i) + 1
    j = s.find("<!-- End left column", i)
    if j < 0:
        j = s.index('id="rightcontent"', i)
    return html_lines(s[i:j])


def split_units(lines: list[str]) -> tuple[str, dict]:
    """(header, units): the header is the list of gazette events at the top; units are the provisions."""
    k = next(i for i, t in enumerate(lines) if t.startswith("(Обн"))
    head = [lines[k]]
    while not head[-1].endswith(")"):
        k += 1
        head.append(lines[k])
    header = " ".join(head)
    units: dict[str, dict] = {}
    order: list[str] = []
    cur = None

    def start(key, label, kind, first):
        nonlocal cur
        n, c = key, 2
        while n in units:
            n = f"{key}-{c}"
            c += 1
        units[n] = {"label": label, "kind": kind, "lines": [first] if first else []}
        order.append(n)
        cur = n

    start("preambyl", "Преамбюл", "preamble", None)
    seen_const = False
    tail_n = 0
    for t in lines[k + 1:]:
        m = re.match(r"Чл\.\s*(\d+)\s*([а-я]?)\s*\.", t)
        if t == "КОНСТИТУЦИЯ" and not seen_const:
            seen_const = True
            units[cur]["lines"].append(t)
            continue
        if m and seen_const and tail_n == 0:
            num, suf = int(m.group(1)), m.group(2)
            key = f"art-{num:03d}" + (f"-{ord(suf) - ord('а') + 1:02d}" if suf else "")
            start(key, f"Чл. {num}{suf}", "art", f"# Чл. {num}{suf}")
            rest = t[m.end():].strip().lstrip(".").strip()
            if rest.startswith("("):
                rest = re.sub(r"^\(\s*", "(", rest)
            if rest:
                units[cur]["lines"].append(rest)
            continue
        if re.match(r"(Глава|ГЛАВА)\s", t) or re.match(r"Раздел\s", t):
            start("glava-" + str(len(order)).zfill(3), t, "heading", f"# {t}")
            continue
        if re.match(r"(ПРЕХОДНИ|ЗАКЛЮЧИТЕЛНИ|ДОПЪЛНИТЕЛНИ)", t) and tail_n == 0:
            tail_n = 1
            start("prehodni-01", t, "transitional", f"# {t}")
            continue
        if t.startswith("ЗАКОН ЗА ИЗМЕНЕНИЕ") or t.startswith("ЗАКОН ЗА ДОПЪЛНЕНИЕ"):
            tail_n += 1
            start(f"prehodni-{tail_n:02d}", t, "transitional", f"# {t}")
            continue
        units[cur]["lines"].append(t)
    out = {}
    for key in order:
        u = units[key]
        out[key] = {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"}
    # chapter headings: keyed after the article they precede, so they sort just before it
    final, pending = {}, []
    for key in order:
        if key.startswith("glava-"):
            pending.append(out[key])
            continue
        if pending and key.startswith("art-"):
            for i, h in enumerate(pending, 1):
                final[f"{key}-0-heading-{i}"] = h
            pending = []
        final[key] = out[key]
    for i, h in enumerate(pending, 1):
        final[f"zz-heading-{i}"] = h
    return header, final


def complete(units: dict) -> bool:
    """A complete copy has every article 1-169 and the original transitional provisions."""
    arts = {int(k[4:7]) for k in units if re.fullmatch(r"art-\d{3}(-\d\d)?", k)}
    return arts >= set(range(1, 170)) and "prehodni-01" in units and "§ 9." in units["prehodni-01"]["text"]


def text_hash(units: dict) -> str:
    return hashlib.sha256(json.dumps(units, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


MONTHS = ["януари", "февруари", "март", "април", "май", "юни", "юли", "август", "септември", "октомври",
          "ноември", "декември"]
HEADER_EVENT = re.compile(
    r"бр\.\s*(\d+)\s+от\s+(\d{1,2})\s*(?:\.\s*(\d{1,2})\s*\.|\s+([А-Яа-я]+)\s+)\s*(\d{4})\s*г"
    r"(?:\.,?\s*в сила от [\d.]+ г\.)?"
    r"(?:\.?\s*-\s*Решение № (\d+) на\s+Конституционния съд от (\d{4}) г\.)?")


def header_laws(header: str) -> dict[str, dict]:
    """The Държавен вестник issues the source's header names (promulgation, amending laws, Constitutional Court
    decisions), as law keys dv-YYYY-N in the header's order. Dates are the issue dates the header prints."""
    laws: dict[str, dict] = {}
    for i, m in enumerate(HEADER_EVENT.finditer(header)):
        num, day, month, month_name, year, dec, dec_year = m.groups()
        if month_name:  # the 2016-2021 page: "бр.100 от 18 Декември 2015г."
            month = MONTHS.index(month_name.lower()) + 1
        if dec:
            title, kind = f"Решение № {dec} на КС от {dec_year} г.", "court"
        elif i == 0:
            title, kind = "Конституция на Република България", "law"
        else:
            title, kind = "ЗИД на Конституцията", "law"
        laws[f"dv-{year}-{int(num)}"] = {
            "label": f"ДВ бр. {int(num)}/{year}", "title": title, "kind": kind, "enacted": None,
            "published": f"{year}-{int(month):02d}-{int(day):02d}", "url": None, "temporary_until": None,
            "restores": None, "note": None}
    assert len(laws) == header.count("бр."), "every ДВ issue in the header must parse"
    return laws


def in_force(key: str, law: dict) -> str:
    if key in OWN_IN_FORCE:
        return OWN_IN_FORCE[key][0]
    return (date.fromisoformat(law["published"]) + timedelta(days=3)).isoformat()


def fully_in_force(key: str, law: dict) -> str:
    return max(in_force(key, law), LATE_PARTS.get(key, ("",))[0])


def named_events(text: str, laws: dict) -> set[str]:
    """The events an amendment note in this text names: "бр. 100 от 2015" (any issue number list form) and,
    for court decisions, "РКС № 13 от 2024"."""
    found = set()
    for m in re.finditer(r"бр\.\s*(\d+)\s+от\s+(?:\d{1,2}\.\d{1,2}\.)?(\d{4})", text):
        k = f"dv-{m.group(2)}-{int(m.group(1))}"
        if k in laws:
            found.add(k)
    return found


def load_sources():
    """[(from-capture label, source_url, sha256, header, units)] oldest first, then today's API text."""
    out = []
    for ts, url in WB_PICKS:
        raw = wb_path(ts, url).read_bytes()
        header, units = split_units(page_lines(raw))
        assert complete(units), f"capture {ts} is not a complete copy"
        out.append((ts, wb_url(ts, url), hashlib.sha256(raw).hexdigest(), header, units))
    raw = cache_path(CONST_URL).read_bytes()
    header, units = split_units(api_lines(raw))
    assert complete(units)
    out.append(("api", CONST_URL, hashlib.sha256(raw).hexdigest(), header, units))
    return out


def main():
    srcs = load_sources()
    header = srcs[-1][3]
    laws = header_laws(header)
    days = {k: in_force(k, v) for k, v in laws.items()}
    full = {k: fully_in_force(k, v) for k, v in laws.items()}
    order = lambda k: (days[k], k)  # noqa: E731
    versions, decisions, corrected = [], [], []
    prev_units, prev_events = None, set()
    for label, url, sha, head, units in srcs:
        events = set(header_laws(head))
        assert events <= set(laws), (label, events - set(laws))
        seen = "today's text (parliament.bg API)" if label == "api" else \
            f"the page as captured by the Internet Archive on {label[:4]}-{label[4:6]}-{label[6:8]}"
        if prev_units is None:
            first_events = sorted(events, key=order)
            last = max(first_events, key=lambda k: (full[k], k))
            versions.append({"from": full[last], "source_url": url, "sha256": sha, "units": units, "credits": {},
                             "note": f"Oldest version available here: the National Assembly's consolidated text, "
                                     f"{seen}. It lists {len(events)} gazette events, the last {laws[last]['label']}; "
                                     f"dated {full[last]}, the day the last of them was fully in force."})
            prev_units, prev_events = units, events
            continue
        new = sorted(events - prev_events, key=order)
        assert new, f"{label}: the text changed with no new gazette event in its header"
        for d in sorted({days[k] for k in new}):
            now = {k for k in new if days[k] == d}
            later = {k for k in new if days[k] > d}
            assert all(full[k] == days[k] for k in now), "an event with late parts needs its own versions"
            v_units = {}
            for key, u in units.items():
                names = named_events(u["text"], laws)
                if not names & later:
                    v_units[key] = u
                    continue
                # Text before its law (coordinator rule, 2026-10-28): the source shows this provision as a later
                # event left it. Inserted by that event: absent here; otherwise the source gives no text for today.
                if key not in prev_units and not names & (set(new) - later):
                    corrected.append((d, key, "absent"))
                    continue
                first_line = u["text"].split("\n", 1)[0]
                body = (first_line + "\n" if first_line.startswith("# ") else "") + PLACEHOLDER + "\n"
                v_units[key] = {"label": u["label"], "kind": u["kind"], "text": body}
                corrected.append((d, key, "placeholder"))
            credits = {}
            for key in sorted(set(v_units) | set(prev_units)):
                a, b = prev_units.get(key), v_units.get(key)
                if a == b or (b and PLACEHOLDER in b["text"]):
                    continue
                c = sorted(named_events((b or a)["text"], laws) & now, key=order)
                if c:
                    credits[key] = c
            names = ", ".join(laws[k]["label"] for k in sorted(now, key=order))
            note = f"Text: {seen}, in force from {d} ({names}, promulgation + 3 days)."
            if later:
                note += (f" The source shows {len([1 for c in corrected if c[0] == d])} provisions as later "
                         f"events left them ({', '.join(laws[k]['label'] for k in sorted(later, key=order))}); "
                         f"here they read \"{PLACEHOLDER}\".")
            versions.append({"from": d, "source_url": url, "sha256": sha, "units": v_units, "credits": credits,
                             "note": note})
            prev_units = v_units
        prev_events = events
    for d, key, how in corrected:
        decisions.append(f"Text before its law: in the version of {d}, {key} {'is absent' if how == 'absent' else 'reads the placeholder'}"
                         f" (its note names a later event); its wording arrives with that event.")
    corpus = {
        "country": {
            "code": "BG", "name": "Bulgaria", "slug": "bulgaria", "lang": "bg", "tz": "Europe/Sofia",
            "future_branch": "badeshte",
            "publisher": {"name": "Народно събрание на Република България (parliament.bg)", "email": "ns@parliament.invalid"},
            "default_in_force_rule": {
                "text": "Конституция, чл. 5, ал. 5: нормативните актове влизат в сила три дни след обнародването им в "
                        "Държавен вестник, освен когато в тях е определен друг срок; чл. 151, ал. 2: решенията на "
                        "Конституционния съд влизат в сила три дни след обнародването им.",
                "source": CONST_URL},
            "licence_note": "Text of the Constitution from the National Assembly of the Republic of Bulgaria "
                            "(parliament.bg). Official legal texts are not subject to copyright (Закон за авторското "
                            "право и сродните му права, чл. 4, т. 1).",
        },
        "sources": [{"name": "Народно събрание: Конституция на Република България (consolidated text, API)",
                     "url": CONST_URL, "retrieved": RETRIEVED, "requests": 1,
                     "licence": "Official legal text; not subject to copyright (ЗАПСП чл. 4, т. 1)",
                     "notes": "Header of the text: " + header},
                    {"name": "Internet Archive (Wayback Machine): captures of parliament.bg/bg/const",
                     "url": "https://web.archive.org/web/*/parliament.bg/bg/const*", "retrieved": WB_RETRIEVED,
                     "requests": wb_requests(),
                     "licence": "The captured pages are the National Assembly's official text (not subject to "
                                "copyright, ЗАПСП чл. 4, т. 1); read through the Internet Archive's raw id_ captures",
                     "notes": "Pinned captures, one per distinct text: " + ", ".join(ts for ts, _ in WB_PICKS)
                              + ". fetch.py --history read a capture per quarter plus bisections (wayback_survey.json)."}],
        "laws": laws,
        "acts": [{
            "slug": "konstitutsiya",
            "short": "КРБ",
            "title": "Конституция на Република България",
            "url": PAGE_URL,
            "first_law": None,
            "earlier_laws": first_events,
            "versions": versions,
        }],
        "applies": [],
        "decisions": [
            "Constitution: built from the National Assembly's own consolidated text: today's from the parliament.bg API, earlier ones from Internet Archive captures of the old parliament.bg/bg/const page (2010 to May 2021), one capture per distinct text. lex.bg is a private service whose robots.txt disallows all but search engines, so it was not used.",
            "Every source goes through the same parse.py code (html_lines, split_units), so a site redesign that changes no words gives identical provisions.",
            f"No capture is older than {WB_PICKS[0][0][:4]}-{WB_PICKS[0][0][4:6]}-{WB_PICKS[0][0][6:8]}, so the 1991 text and the versions of 2003-2007 are not built: the oldest version is credited to the publisher as the oldest version available and names the earlier events." if WB_PICKS else "No capture was usable.",
            "In-force days: promulgation in the Държавен вестник + 3 days (Constitution чл. 5, ал. 5; for Constitutional Court decisions чл. 151, ал. 2), unless the event sets its own day: "
            + "; ".join(f"{k}: {v[0]} ({v[1]})" for k, v in {**OWN_IN_FORCE, **LATE_PARTS}.items()) + ".",
            "A version holding an event with later-starting parts is dated by the last of those days (the oldest version: 2008-01-01, ДВ бр. 12/2007 § 13).",
            "Credits: a changed provision is credited to a new event only where its own amendment note names that event's gazette issue (\"бр. N от YYYY\"); any other change is committed by the publisher as unexplained.",
            "The Internet Archive holds no copy of the text between the 2023 amendment (ДВ бр. 106/2023, in force 2023-12-25) and Constitutional Court Decision № 13/2024 (ДВ бр. 66/2024, in force 2024-08-09): the old page ends in May 2021 and the API was captured only on 2021-06-29 and 2025-08-20; Common Crawl's index was unreachable from this machine. The 2023-12-25 version is today's text with the coordinator's text-before-its-law rule applied to the provisions whose notes name the 2024 decision.",
            "Five provisions differ between the 2016-2021 text and today's in ways no note explains (чл. 9 and 59: \"в сила от 1 януари 2008 г.\" now \"01.01.2008 г.\"; чл. 85, т. 8: \".\" now \";\"; чл. 91а: the note joined to ал. 1; чл. 158, т. 5: \"гл.\" now \"глава\"). The publisher made them after 2021-06-29 (the API captured then still has the old wording) and by 2025-08-20; they are committed as unexplained in the version of 2023-12-25, the first version built from today's text.",
            "The source types the dash in some amendment notes as a stray control character (U+001F in the API text, U+00AD in the old page: чл. 22, 25, 150); parse.py reads it as \"-\".",
            "Inline amendment notes such as '(Нова - ДВ, бр. 18 от 2005 г.)' are kept in the text as the source prints them.",
            "Chapter and section headings are their own units, keyed just before the first article they precede.",
        ] + decisions,
        "ai_use": ["none: parse.py is deterministic code; no model output is used as text or data."],
    }
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else HERE / "corpus.json"
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, out)
    for v in versions:
        print(v["from"], len(v["units"]), len(v["credits"]), v["source_url"])


if __name__ == "__main__":
    main()
