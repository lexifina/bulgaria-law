"""Bulgaria: every law the National Assembly adopted and the State Gazette published, as published.

Reads only a local copy of the National Assembly's act records (parliament.bg /api/v1/act/<id>) and of State Gazette
material pages (dv.parliament.bg showMaterialDV, through Internet Archive captures), and writes corpus.d parts
(SCHEMA.md in scripts/gitlaw_common). Deterministic: the same inputs give the same bytes.

    python -X utf8 parse_acts.py --src <folder with acts.jsonl, raw/, dvmat.jsonl> [--report holds.jsonl]

What becomes an act here:
- a law (record type 1) with its adopted final text and a State Gazette issue;
- the text is the law as adopted and promulgated: the President's decree above it and the adoption formula and
  signature below it are not part of the law and are cut;
- its one version takes effect on the day its own final clause names ("от деня на обнародването" = the Gazette day,
  a calendar date), or else three days after the Gazette day (Constitution чл. 5, ал. 5);
- the Gazette day of an issue comes from the Gazette's own material pages ("брой: N, от дата D").

An act is held back, not published, when any of these is true (the reason is written to the report):
- the Constitutional Court's list of contested acts names it (by title): a ruling may have struck words from it;
- a later text cites its Gazette issue ("ДВ, бр. N от YYYY г."), or a later law's title names it as amended or
  repealed: its text today may differ from the text as published, and no version is guessed;
- its Gazette day is not known, or its final clause names a day this parser can't read;
- its provisions don't split cleanly (no provisions, or a provision number twice).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARTS = HERE / "corpus.d"
SOURCE_URL = "https://www.parliament.bg/bg/laws/ID/{id}"
API_URL = "https://www.parliament.bg/api/v1/act/{id}"

MONTHS = {m: i for i, m in enumerate(["януари", "февруари", "март", "април", "май", "юни", "юли", "август",
                                       "септември", "октомври", "ноември", "декември"], 1)}
BLOCK = re.compile(r"<br\s*/?>|</?(?:p|div|hr|h[1-6]|li|ul|ol|table|tr|td|th|center|blockquote)\b[^>]*>", re.I)
SHY_DASH = re.compile(r"[ \t]+[\x1f­][ \t]+")
OPEN_Q, CLOSE_Q = "„", "“”"

HEADINGS = re.compile(
    r"^(?:(?:Глава|ГЛАВА|Раздел|РАЗДЕЛ|Част|ЧАСТ|Дял|ДЯЛ)\s+\S+.*|"
    r"(?:Преходн[аи]|Заключителн[аи]|Допълнителн[аи]|Преходни и заключителни|Заключителни и преходни|"
    r"Допълнителна и заключителна|Допълнителни и заключителни)\s+разпоредб[аи].*|"
    r"(?:ПРЕХОДН[АИ]|ЗАКЛЮЧИТЕЛН[АИ]|ДОПЪЛНИТЕЛН[АИ]|ПРЕХОДНИ И ЗАКЛЮЧИТЕЛНИ|ДОПЪЛНИТЕЛНИ И ЗАКЛЮЧИТЕЛНИ)\s+РАЗПОРЕДБ[АИ].*)$")
ART = re.compile(r"^Чл\.\s*(\d+)\s*([а-я]?)\s*\.\s*")
PAR = re.compile(r"^§\s*(\d+)\s*([а-я]?)\s*\.\s*")
SOLE_ART = re.compile(r"^Член единствен\s*\.?\s*", re.I)
SOLE_PAR = re.compile(r"^Параграф единствен\s*\.?\s*", re.I)
ADOPTED = re.compile(r"^(?:Законът|Кодексът|Изборният кодекс|Този закон)\s+е\s+приет\s+от\b")
ANNEX = re.compile(r"^(?:Приложение|ПРИЛОЖЕНИЕ)\b")
# A citation of an act by name and original Gazette issue: 'Закона за горите (обн., ДВ, бр. 19 от 2011 г.; ...'.
NAMED_CITE = re.compile(r"\b(?:[Зз]акона?|[Кк]одекса?|[Пп]равилника?|[Уу]става?)\s+((?:за|на|относно)\s+[^()]{2,300}?)"
                        r"\s*\(\s*(?:обн\.\s*,?\s*)?(?:ДВ|\"Държавен вестник\")\s*,?\s*бр\.\s*(\d+)\s+от\s+"
                        r"(?:\d{1,2}[\s.]+(?:\S+\s+)?)?(\d{4})")
IN_FORCE = re.compile(r"(?:Законът|Кодексът|Този закон)\s+влиза\s+в\s+сила\s+([^.]*(?:\d\.\d[^.]*)*)\.")


def norm(s: str) -> str:
    s = html.unescape(s).replace(" ", " ")
    s = SHY_DASH.sub(" - ", s).replace("\x1f", "").replace("­", "")
    s = s.replace("–", "-").replace("—", "-").replace("„", '"').replace("“", '"').replace("”", '"')
    s = re.sub(r"[ \t\r\n]+", " ", s)
    return s.strip()


def raw_lines(fragment: str) -> list[tuple[str, int]]:
    """(normalised line, quote depth at its start), one per paragraph or <br> item. Word's conditional comments and
    style blocks are dropped first."""
    fragment = re.sub(r"<!--.*?-->", "", fragment, flags=re.S)
    fragment = re.sub(r"<(style|script|xml)\b.*?</\1>", "", fragment, flags=re.S | re.I)
    out, depth = [], 0
    for chunk in BLOCK.split(fragment):
        t = html.unescape(re.sub(r"<[^>]+>", "", chunk))
        n = norm(t)
        if n and not re.fullmatch(r"[.\s]+", n):
            out.append((n, depth))
        depth = max(0, depth + t.count(OPEN_Q) - sum(t.count(c) for c in CLOSE_Q))
    return out


def unit_key(prefix: str, num: int, suf: str) -> str:
    return f"{prefix}-{num:03d}" + (f"-{ord(suf) - ord('а') + 1:02d}" if suf else "")


class Hold(Exception):
    pass


def split(lines: list[tuple[str, int]], title: str) -> dict:
    # The law begins at its title (after the President's decree), and ends at its adoption formula.
    start = None
    for i, (t, _) in enumerate(lines):
        u = t.upper()
        if (u.startswith(("ЗАКОН", "КОДЕКС", "ИЗБОРЕН КОДЕКС", "ГРАЖДАНСКИ ПРОЦЕСУАЛЕН", "НАКАЗАТЕЛ", "СЕМЕЕН КОДЕКС",
                          "ДАНЪЧНО-ОСИГУРИТЕЛЕН", "АДМИНИСТРАТИВНОПРОЦЕСУАЛЕН", "КОДЕКС"))
                and t == u and not u.startswith("ЗАКОНЪТ")):
            start = i
            break
    if start is None:
        raise Hold("no_title_line")
    end = next((i for i in range(start, len(lines)) if ADOPTED.match(lines[i][0])), None)
    if end is None:
        raise Hold("no_adoption_formula")
    tail = lines[end + 1:]
    annex_at = next((i for i, (t, _) in enumerate(tail) if ANNEX.match(t)), None)
    # Title lines: the upper-case title, which may run over several lines.
    k = start + 1
    while k < end and lines[k][0] == lines[k][0].upper() and re.search(r"[А-Я]", lines[k][0]) \
            and not ART.match(lines[k][0]) and not PAR.match(lines[k][0]) and not HEADINGS.match(lines[k][0]):
        k += 1
    body = lines[k:end]
    first = next((t for t, d in body if d == 0 and (ART.match(t) or PAR.match(t) or SOLE_ART.match(t)
                                                     or SOLE_PAR.match(t))), None)
    if first is None:
        raise Hold("no_provisions")
    par_mode = bool(PAR.match(first) or SOLE_PAR.match(first))
    units: dict[str, dict] = {}
    order: list[str] = []
    pending: list[str] = []
    cur = "uvod"
    units[cur] = {"label": "Увод", "kind": "preamble", "lines": []}
    order.append(cur)

    def begin(key: str, label: str, kind: str, heading: str, rest: str):
        nonlocal cur
        if key in units:
            raise Hold(f"duplicate_unit:{key}")
        if pending:  # headings sort right after the provision before them: "par-001-zz-heading-1" < "par-002"
            prev = next((k for k in reversed(order) if k != "uvod"), None)
            for j, h in enumerate(pending, 1):
                hk = f"{prev}-zz-heading-{j}" if prev else f"0-heading-{j}"
                units[hk] = {"label": h, "kind": "heading", "lines": [f"# {h}"]}
                order.append(hk)
            pending.clear()
        units[key] = {"label": label, "kind": kind, "lines": [f"# {heading}"] + ([rest] if rest else [])}
        order.append(key)
        cur = key

    for t, d in body:
        if d == 0:
            m = ART.match(t) if not par_mode else None
            if m:
                begin(unit_key("art", int(m.group(1)), m.group(2)), f"Чл. {m.group(1)}{m.group(2)}", "art",
                      f"Чл. {m.group(1)}{m.group(2)}.", t[m.end():].strip())
                continue
            m = SOLE_ART.match(t) if not par_mode else None
            if m:
                begin("art-001", "Член единствен", "art", "Член единствен.", t[m.end():].strip())
                continue
            m = PAR.match(t)
            if m:
                begin(unit_key("par", int(m.group(1)), m.group(2)), f"§ {m.group(1)}{m.group(2)}", "transitional",
                      f"§ {m.group(1)}{m.group(2)}.", t[m.end():].strip())
                continue
            m = SOLE_PAR.match(t)
            if m:
                begin("par-001", "Параграф единствен", "transitional", "Параграф единствен.", t[m.end():].strip())
                continue
            if HEADINGS.match(t) and len(t) < 200:
                pending.append(t)
                continue
        units[cur]["lines"].append(t)
    if pending:  # a heading after the last provision: keep it as the act's last unit
        for j, h in enumerate(pending, 1):
            units[f"zz-heading-{j}"] = {"label": h, "kind": "heading", "lines": [f"# {h}"]}
            order.append(f"zz-heading-{j}")
    if annex_at is not None:
        units["prilozhenie-01"] = {"label": "Приложение", "kind": "annex", "lines": [t for t, _ in tail[annex_at:]]}
        order.append("prilozhenie-01")
    if not units["uvod"]["lines"]:
        del units["uvod"]
        order.remove("uvod")
    out = {}
    for key in order:
        u = units[key]
        if not u["lines"]:
            continue
        out[key] = {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"}
    if not any(k.startswith(("art-", "par-")) for k in out):
        raise Hold("no_provisions")
    return out


def parse_day(s: str) -> str | None:
    m = re.search(r"(\d{1,2})\s*\.?\s*(" + "|".join(MONTHS) + r")\s+(\d{4})", s)
    if m:
        return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\s*г", s)
    if m:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    return None


def in_force(units: dict, gazette_day: str) -> tuple[str, str]:
    """(day, how): the act's own final clause, else Gazette day + 3."""
    text = " ".join(u["text"].replace("\n", " ") for k, u in units.items() if k.startswith(("par-", "art-")))
    # Only clauses about this act itself: provisions an amending act inserts into another act are long quoted spans
    # (norm() turned the quotes into '"'); short quoted names such as "Държавен вестник" stay.
    text = re.sub(r'"[^"]{60,}?"', " ", text)
    clauses = [m.group(1) for m in IN_FORCE.finditer(text)]
    if not clauses:
        return (date.fromisoformat(gazette_day) + timedelta(days=3)).isoformat(), "default"
    c = clauses[-1]
    exceptions = bool(re.search(r"с изключение|освен", c))
    if re.match(r"от\s+(?:деня|датата)\s+на\s+обнародването", c):
        return gazette_day, "publication" + ("+exceptions" if exceptions else "")
    if re.match(r"три\s+дни\s+след\s+обнародването", c):
        return (date.fromisoformat(gazette_day) + timedelta(days=3)).isoformat(), "default" + ("+exceptions" if exceptions else "")
    m = re.match(r"(?:от|на)\s+(\d{1,2}\s*\.?\s*\S+\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{4})\s*г", c)
    if m:
        d = parse_day(m.group(1))
        if d:
            return d, "date" + ("+exceptions" if exceptions else "")
    raise Hold("in_force_unreadable:" + c[:120])


def title_key(s: str) -> str:
    s = re.sub(r"\s*\((?:обн\.\s*,?\s*)?ДВ[^)]*\)\s*$", "", s)
    return re.sub(r"\s+", " ", s.lower().replace('"', "")).strip(" .,;")


def subj_norm(s: str) -> str:
    s = s.lower().replace('"', "").replace("ё", "е")
    s = re.sub(r"\s+", " ", s).strip(" .,;")
    return s[:60]


def citations(text: str) -> set[tuple[str, int, int]]:
    """(subject, issue, year) for every act named with its original Gazette issue."""
    return {(subj_norm(m.group(1)), int(m.group(2)), int(m.group(3))) for m in NAMED_CITE.finditer(text)}


def subject(title: str) -> str | None:
    """'Закон за горите' -> 'за горите', 'Кодекс на труда' -> 'на труда' (what a citation names after the act word)."""
    m = re.match(r"^(?:[А-Я][а-я]+\s+)?(?:Закон|Кодекс|Правилник|Устав)\s+((?:за|на|относно)\s+.+)$", title.strip())
    return m.group(1) if m else None


TARGET = re.compile(r"\b(?:изменение|допълнение|отмяна|изменения|допълнения)\b.*?\bна\s+(?:Закона|Кодекса)\s+(за\s+.+)$", re.I)


def load(src: Path):
    acts = {}
    for line in (src / "acts.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        acts[int(r["L_Act_id"])] = r
    dv_days: dict[tuple[int, int], set[str]] = defaultdict(set)
    dv_texts: list[tuple[tuple[int, int], str]] = []
    seen_mat = set()
    for name, folder in (("dvmat.jsonl", "dv"), ("cc-dvmat.jsonl", "cc-dv")):
        p = src / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # a row being written
            if r.get("issue") and r.get("date") and int(r["date"][:4]) == r["year"]:
                dv_days[(r["issue"], r["year"])].add(r["date"])
                f = src / folder / str(r["idMat"] // 1000) / f"{r['idMat']}.html.gz"
                if f.exists() and r["idMat"] not in seen_mat:
                    seen_mat.add(r["idMat"])
                    dv_texts.append(((r["issue"], r["year"]), f))
    return acts, dv_days, dv_texts


def eurlex_days(path: str | None) -> dict[tuple[int, int], set[str]]:
    """Gazette issue dates as member-state reports to the EU record them (national implementing measures)."""
    out: dict[tuple[int, int], set[str]] = defaultdict(set)
    if not path or not Path(path).exists():
        return out
    import csv
    for r in csv.DictReader(Path(path).read_text(encoding="utf-8").splitlines()):
        n = (r.get("num") or "").strip().split(" ")[0].strip(".,")
        d = (r.get("date") or "")[:10]
        if n.isdigit() and re.fullmatch(r"\d{4}-\d\d-\d\d", d) and "вестник" in (r.get("name") or "вестник"):
            out[(int(n), int(d[:4]))].add(d)
    return out


def gazette_day(dv_days: dict, iss: int, year: int, eu: dict | None = None) -> tuple[str | None, str]:
    """(day, source). The Gazette's own page first; then an issue between two seen issues of one day; then the EU
    record, only when all its rows agree, the day is a Tuesday or Friday (the Gazette's regular days) and it falls
    between the days of the nearest issues seen on Gazette pages."""
    days = dv_days.get((iss, year))
    if days:
        return (next(iter(days)), "gazette") if len(days) == 1 else (None, "gazette_conflict")
    seen = [k for k in dv_days if k[1] == year and len(dv_days[k]) == 1]
    lo = max((k for k in seen if k[0] < iss), default=None)
    hi = min((k for k in seen if k[0] > iss), default=None)
    if lo and hi and dv_days[lo] == dv_days[hi]:
        return next(iter(dv_days[lo])), "gazette_between"
    e = (eu or {}).get((iss, year))
    if e and len(e) == 1:
        d = next(iter(e))
        wd = date.fromisoformat(d).weekday()
        if wd in (1, 4) and (not lo or next(iter(dv_days[lo])) <= d) and (not hi or d <= next(iter(dv_days[hi]))):
            return d, "eu_record"
    return None, "unknown"


DECREE_DAY = re.compile(r"Издаден в (?:София|[А-Я][а-я]+) на\s+([^.]{6,30}?\d{4})\s*г")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--report")
    ap.add_argument("--retrieved", required=True, help="the day the inputs were retrieved (YYYY-MM-DD)")
    ap.add_argument("--contested", help="the Constitutional Court's list of contested acts (constcourt.bg/bg/contested-acts)")
    ap.add_argument("--eurlex", help="CSV num,date,name: Gazette issue dates from the EU's national-measures records")
    ap.add_argument("--rejects", help="JSON {act id: reason}: acts held back by hand or by a failed read-back check")
    a = ap.parse_args()
    src = Path(a.src)
    acts, dv_days, dv_texts = load(src)
    eu = eurlex_days(a.eurlex)
    contested = set()
    if a.contested and Path(a.contested).exists():
        page = Path(a.contested).read_text(encoding="utf-8")
        for x in re.findall(r'<h3 class="toggle-item-title">(.*?)</h3>', page, flags=re.S):
            contested.add(title_key(norm(re.sub(r"<[^>]+>", "", x))))
    rejects = json.loads(Path(a.rejects).read_text(encoding="utf-8")) if a.rejects and Path(a.rejects).exists() else {}

    def body(i: int) -> tuple[bytes, dict]:
        raw = gzip.decompress((src / "raw" / str(i // 1000) / f"{i}.json.gz").read_bytes())
        return raw, json.loads(raw.decode("utf-8"))

    laws = {i: r for i, r in acts.items()
            if str(r.get("L_Act_T_id")) == "1" and r.get("final_len") and r.get("L_Act_dv_iss") and r.get("L_Act_dv_year")
            and str(r["L_Act_dv_iss"]).isdigit()}
    # Who cites which Gazette issue: every adopted final text (laws and decisions) and every Gazette page held.
    cited_by: dict[tuple[int, int], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    titles_named: dict[str, set[int]] = defaultdict(set)
    per_issue: dict[tuple[int, int], int] = defaultdict(int)
    for i, r in laws.items():
        per_issue[(int(r["L_Act_dv_iss"]), int(r["L_Act_dv_year"]))] += 1

    def note_cites(text: str, own: tuple[int, int], who: str):
        for subj, n, y in citations(text):
            if (n, y) != own:
                cited_by[(n, y)][subj].add(who)

    for i, r in acts.items():
        if not (r.get("final_len") and r.get("L_Act_dv_iss") and str(r["L_Act_dv_iss"]).isdigit()):
            continue
        own = (int(r["L_Act_dv_iss"]), int(r["L_Act_dv_year"]))
        _, d = body(i)
        note_cites(norm(re.sub(r"<[^>]+>", " ", d.get("L_ActL_final_body") or "")), own, f"na:{i}")
        m = TARGET.search(norm(r.get("L_ActL_final") or ""))
        if m:
            titles_named[subj_norm(m.group(1))].add(i)
    for own, f in dv_texts:
        t = norm(re.sub(r"<[^>]+>", " ", gzip.decompress(f.read_bytes()).decode("utf-8", "replace")))
        note_cites(t, own, f"dv:{f.name.split('.')[0]}")

    parts: dict[int, dict] = defaultdict(lambda: {"laws": {}, "acts": []})
    holds = []
    for i in sorted(laws):
        r = laws[i]
        iss, year = int(r["L_Act_dv_iss"]), int(r["L_Act_dv_year"])
        title = norm(r.get("L_ActL_final") or "")
        try:
            if str(i) in rejects:
                raise Hold("rejected:" + str(rejects[str(i)])[:200])
            raw, d = body(i)
            final_title = norm(d.get("L_ActL_final") or "")
            if final_title:
                title = final_title
            subj = subject(title)
            sn = subj_norm(subj) if subj else None
            later = set()
            for csubj, who in cited_by.get((iss, year), {}).items():
                # The citation names this act: same subject, or this act is the only law in that Gazette issue.
                if (sn and (csubj.startswith(sn[:40]) or sn.startswith(csubj[:40]))) or per_issue[(iss, year)] == 1:
                    later |= who - {f"na:{i}"}
            if later:
                raise Hold("cited_later:" + ",".join(sorted(later)[:5]))
            if sn and titles_named.get(sn, set()) - {i}:
                raise Hold("named_as_amended:" + ",".join(map(str, sorted(titles_named[sn] - {i})[:5])))
            if title_key(title) in contested:
                raise Hold("contested_constcourt")
            gday, gsrc = gazette_day(dv_days, iss, year, eu)
            if not gday:
                raise Hold("gazette_day_unknown" if gsrc == "unknown" else gsrc)
            # The President's decree comes first; the Gazette prints the law within days of it.
            m = DECREE_DAY.search(norm(re.sub(r"<[^>]+>", " ", d["L_ActL_final_body"]))[:3000])
            dday = parse_day(m.group(1) + " г") if m else None
            if not dday:
                raise Hold("decree_day_unreadable")
            if not (dday <= gday <= (date.fromisoformat(dday) + timedelta(days=20)).isoformat()):
                raise Hold(f"gazette_day_inconsistent:{gsrc} {gday} vs decree {dday}")
            units = split(raw_lines(d["L_ActL_final_body"]), title)
            day, how = in_force(units, gday)
        except Hold as h:
            holds.append({"id": i, "dv": f"{iss}/{year}", "title": title[:160], "reason": str(h)})
            continue
        kind = "kodeks" if re.match(r"^\S*\s*[Кк]одекс\b|^[А-Я][а-я]+\s+кодекс$|^Кодекс\b", title) and not re.search(r"изменение|допълнение|отмяна", title) else "zakon"
        slug = f"{kind}-{year}-dv{iss:03d}-{i}"
        label = f"{title} (ДВ, бр. {iss} от {year} г.)"
        adopted = (r.get("L_Act_date2") or "")[:10] or None
        note = None
        if "exceptions" in how:
            note = "Its final clause gives some provisions a different day; the whole text is dated by its general day."
        parts[year]["laws"][slug] = {"label": label, "title": title, "kind": "law", "enacted": adopted,
                                     "published": gday, "url": SOURCE_URL.format(id=i), "temporary_until": None,
                                     "restores": None, "note": None}
        parts[year]["acts"].append({
            "slug": slug, "short": title, "title": title, "url": SOURCE_URL.format(id=i), "first_law": slug,
            "earlier_laws": [],
            "versions": [{"from": day, "source_url": API_URL.format(id=i), "sha256": hashlib.sha256(raw).hexdigest(),
                          "units": units, "credits": {}, **({"note": note} if note else {})}]})
    PARTS.mkdir(exist_ok=True)
    written = []
    for year in sorted(parts):
        p = parts[year]
        p["acts"].sort(key=lambda x: x["slug"])
        p["sources"] = [{"name": "Народно събрание: приети закони (parliament.bg, окончателен текст)",
                         "url": "https://www.parliament.bg/bg/laws", "retrieved": a.retrieved,
                         "licence": "Official legal text; not subject to copyright (ЗАПСП чл. 4, т. 1)",
                         "notes": "The final adopted text of each law, with its State Gazette issue."},
                        {"name": "Държавен вестник: дати на броевете (dv.parliament.bg, Internet Archive)",
                         "url": "https://dv.parliament.bg/DVWeb/", "retrieved": a.retrieved,
                         "licence": "Official publication", "notes": "The date of each Gazette issue."}]
        p["decisions"] = [
            "A law is published here as adopted and promulgated, from the National Assembly's final text; the "
            "President's decree above it and the adoption formula below it are not part of the law.",
            "Its one version takes effect on the day its own final clause names, else three days after its State "
            "Gazette day (Constitution чл. 5, ал. 5).",
            "The Gazette day of an issue is read from the Gazette's own page; when none is held, from the EU's "
            "national-measures record, only if all its rows agree, the day is a Tuesday or Friday and it lies between "
            "the days of neighbouring issues; either way it must fall 0-20 days after the President's decree.",
            "A law is published only when no later text held cites its Gazette issue and no later law's title names "
            "it as amended or repealed; the others are held back until their later versions are built."]
        p["ai_use"] = ["none"]
        f = PARTS / f"40-zakoni-{year}.json"
        tmp = f.with_suffix(".tmp")
        tmp.write_text(json.dumps(p, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8", newline="\n")
        tmp.replace(f)
        written.append((f.name, len(p["acts"])))
    if a.report:
        Path(a.report).write_text("".join(json.dumps(h, ensure_ascii=False) + "\n" for h in holds), encoding="utf-8")
    reasons = defaultdict(int)
    for h in holds:
        reasons[h["reason"].split(":")[0]] += 1
    print(json.dumps({"laws_seen": len(laws), "published": sum(n for _, n in written), "held": len(holds),
                      "held_by_reason": dict(reasons), "parts": written, "dv_issues_dated": len(dv_days)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
