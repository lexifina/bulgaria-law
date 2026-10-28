"""Bulgaria: read the cache only and write corpus.json (SCHEMA.md in scripts/gitlaw_common).

Phase 1 so far: the Constitution, as the National Assembly's own consolidated text (parliament.bg API
/api/v1/nav/bg/const), committed as one "oldest version available" version. No earlier version is built yet:
archive.org was offline when this ran and dv.parliament.bg refuses connections from this machine.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
CONST_URL = "https://www.parliament.bg/api/v1/nav/bg/const"
RETRIEVED = "2026-10-28"


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode("utf-8")).hexdigest()


def norm(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace(" ", " ")
    s = s.replace("–", "-").replace("—", "-").replace("„", '"').replace("“", '"').replace("”", '"')
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def paragraphs(body: str) -> list[str]:
    out = []
    for p in re.findall(r"<p[^>]*>(.*?)</p>", body, flags=re.S):
        for line in re.split(r"<br\s*/?>", p):
            t = norm(line)
            if t and not re.fullmatch(r"\.+", t):
                out.append(t)
    return out


def parse_constitution():
    raw = cache_path(CONST_URL).read_bytes()
    data = json.loads(raw.decode("utf-8"))
    lines = paragraphs(data["C_ArL_body"])
    units: dict[str, dict] = {}
    order = []
    cur = None

    def start(key, label, kind, first):
        nonlocal cur
        n, k = key, 2
        while n in units:
            n = f"{key}-{k}"
            k += 1
        units[n] = {"label": label, "kind": kind, "lines": [first] if first else []}
        order.append(n)
        cur = n

    header = lines[0]
    start("preambyl", "Преамбюл", "preamble", None)
    seen_const = False
    tail_n = 0
    for t in lines[1:]:
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
    # chapter headings: keep as units so the structure is visible; key them after the article they precede
    out = {}
    for k in order:
        u = units[k]
        out[k] = {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"}
    # rename heading keys so they sort before the next article
    final, pending = {}, []
    for k in order:
        if k.startswith("glava-"):
            pending.append(out[k])
            continue
        if pending and k.startswith("art-"):
            for i, h in enumerate(pending, 1):
                final[f"{k}-0-heading-{i}"] = h
            pending = []
        final[k] = out[k]
    for i, h in enumerate(pending, 1):
        final[f"zz-heading-{i}"] = h
    return header, final, hashlib.sha256(raw).hexdigest()


def main():
    header, units, sha = parse_constitution()
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
                     "notes": "Header of the text: " + header}],
        "laws": {},
        "acts": [{
            "slug": "konstitutsiya",
            "short": "КРБ",
            "title": "Конституция на Република България",
            "url": "https://www.parliament.bg/bg/const",
            "first_law": None,
            "earlier_laws": ["ДВ бр. 56/1991 (обнародване)", "ДВ бр. 85/2003", "ДВ бр. 18/2005", "ДВ бр. 27/2006",
                             "ДВ бр. 78/2006 (Решение № 7 на КС)", "ДВ бр. 12/2007", "ДВ бр. 100/2015",
                             "ДВ бр. 106/2023", "ДВ бр. 66/2024 (Решение № 13 на КС)"],
            "versions": [{
                "from": "2024-08-09",
                "source_url": CONST_URL,
                "sha256": sha,
                "units": units,
                "credits": {},
                "note": "Oldest version available here: the National Assembly's current consolidated text. Its last "
                        "listed change is Constitutional Court Decision No. 13 of 2024 (ДВ бр. 66 от 06.08.2024), in "
                        "force three days after publication (чл. 151, ал. 2), so this version is dated 2024-08-09. "
                        "Earlier versions are not built yet.",
            }],
        }],
        "applies": [],
        "decisions": [
            "Constitution: built from the National Assembly's consolidated text (parliament.bg API), the only free official consolidation found; lex.bg is a private service whose robots.txt disallows all but search engines, so it was not fetched.",
            "Constitution: one version only, credited to the publisher as the oldest version available; dated 2024-08-09, the in-force day of its last listed change (КС Решение № 13/2024, ДВ бр. 66 от 06.08.2024, + 3 days under чл. 151, ал. 2).",
            "Earlier versions (1991, 2003, 2005, 2006, 2007, 2015, 2023) are not built: archive.org was offline at fetch time and dv.parliament.bg refused connections from this machine.",
            "Inline amendment notes such as '(Нова - ДВ, бр. 18 от 2005 г.)' are kept in the text as the source prints them.",
            "Chapter and section headings are their own units, keyed just before the first article they precede.",
        ],
        "ai_use": ["none: parse.py is deterministic code; no model output is used as text or data."],
    }
    tmp = HERE / "corpus.json.tmp"
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, HERE / "corpus.json")
    print(len(units), "units")


if __name__ == "__main__":
    main()
