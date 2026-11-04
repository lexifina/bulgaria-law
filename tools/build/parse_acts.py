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
A law already published as it was adopted (listed by --keep) stays published as before when a later citation or title
is found afterwards: that does not make its text as published wrong. It is written to corpus.d/41-zakoni-kept.json
until its later versions are built.

The State Gazette's own material pages also give acts of other kinds (corpus.d/50-dv-<kind>-<year>.json): Council of
Ministers decrees (postanovlenie), regulations (naredba), rules (pravilnik), tariffs (tarifa), instructions
(instruktsiya), and laws the National Assembly's record holds no text for (before 2009, or missing). One page is one
act, as printed in the official section, slug <kind>-<year>-dv<issue>-<page id>. Its one version takes effect on the
day its own final provisions name, else, for a normative act, three days after its Gazette day (Constitution чл. 5,
ал. 5); a decree that is not normative and names no day is held. It is held back, too, when a later text held here
cites it by name and Gazette issue or a later title names it as amended or repealed, when it amends or repeals an act
whose text is not held here, or when its page or structure doesn't read cleanly (cut short, printed only in the PDF,
provisions out of sequence, signatures inside a quotation). Acts naming people (appointments, awards) are not taken.
Most Gazette issues are captured only in part, so a base act's later amendment may be missing: acts already published
(--on-main: the repository's data/paths.json) keep their part, and any other act is taken only if it is an amending act
(corpus.d/51-dv-lowrisk-<kind>-<year>.json).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import sys
import time
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


# ---------------------------------------------------------------------------------------------------------------------
# State Gazette material pages (dv.parliament.bg showMaterialDV): Council of Ministers decrees, regulations, rules,
# instructions and tariffs, and laws the National Assembly's record holds no text for. One act is one material page,
# as the Gazette printed it in its official section; the issue and its date come from the page's own header.

DV_URL = "https://dv.parliament.bg/DVWeb/showMaterialDV.jsp?idMat={id}"
# The act's kind, from the first words of the Gazette's title for the material.
DV_KIND = [(re.compile(r"^Устройствен\s+правилник\b"), "pravilnik"), (re.compile(r"^Постановление\b"), "postanovlenie"),
           (re.compile(r"^[НH]аредба\b"), "naredba"), (re.compile(r"^Правилник\b"), "pravilnik"),
           (re.compile(r"^Тарифа\b"), "tarifa"), (re.compile(r"^Инструкция\b"), "instruktsiya"),
           (re.compile(r"^Закон\b"), "zakon"),
           (re.compile(r"^(?:Кодекс|Изборен кодекс|[А-Я][а-я]+(?:-[а-я]+)?\s+(?:процесуален\s+)?кодекс)\b"), "kodeks")]
DV_SECTIONS = {"postanovlenie": {"МИНИСТЕРСКИ СЪВЕТ"}, "zakon": {"НАРОДНО СЪБРАНИЕ"}, "kodeks": {"НАРОДНО СЪБРАНИЕ"}}
DV_REG_SECTIONS = {"МИНИСТЕРСКИ СЪВЕТ", "МИНИСТЕРСТВА И ДРУГИ ВЕДОМСТВА", "НАРОДНО СЪБРАНИЕ"}
DV_NORMATIVE = {"naredba", "pravilnik", "tarifa", "instruktsiya"}
# Acts about named people (appointments, awards, pardons, pensions) are not published here.
DV_PERSONAL = re.compile(r"(?:назначаване|освобождаване|награждаване|удостояване|помилване)\s+(?:на\s+)?(?:[а-я-]+\s+){0,3}"
                         r"[А-Я][а-я]+\s+(?:[А-Я][а-я]+\s+)?[А-Я][а-я]+(?:ов|ев|ски|ова|ева|ска|ин|ина)\b|"
                         r"персонална\s+пенсия|приемане\s+в\s+българско\s+гражданство")
DV_MARK = re.compile(r'<span class="mark">\s*брой:\s*(\d+),\s*от дата\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s*г\.(.*?)</span>', re.S)
DV_TITLE_SPAN = re.compile(r'<span class="tdHead1">(.*?)</span>', re.S)
# The first line of an act's own title, and of a text a decree adopts.
DV_TITLE_LINE = {"postanovlenie": re.compile(r"^(?:ПОСТАНОВЛЕНИЕ|Постановление)\b"),
                 "naredba": re.compile(r"^(?:[НH]АРЕДБА|[НH]аредба)\b"),
                 "pravilnik": re.compile(r"^(?:(?:УСТРОЙСТВЕН\s+)?ПРАВИЛНИК|(?:Устройствен\s+)?[Пп]равилник)\b"),
                 "tarifa": re.compile(r"^(?:ТАРИФА|Тарифа)\b"), "instruktsiya": re.compile(r"^(?:ИНСТРУКЦИЯ|Инструкция)\b")}
# The issuing body's name, printed in capitals above some titles ('МИНИСТЕРСТВО НА ФИНАНСИТЕ').
ISSUER_LINE = re.compile(r"^[А-Я][А-Я \-,\"]{3,200}$")
ADOPTED_TITLE = re.compile(r"^(НАРЕДБА|ПРАВИЛНИК|УСТРОЙСТВЕН ПРАВИЛНИК|ТАРИФА|ИНСТРУКЦИЯ|ПРАВИЛА|МЕТОДИКА|СПИСЪК|СТАТУТ|"
                           r"УСТАВ|ПОЛОЖЕНИЕ|РЕГЛАМЕНТ|КРИТЕРИИ|ПОРЯДЪК|НОМЕНКЛАТУРА|КЛАСИФИКАТОР|КОДЕКС)\b")
ADOPTED_KEY = {"НАРЕДБА": "naredba", "ПРАВИЛНИК": "pravilnik", "УСТРОЙСТВЕН ПРАВИЛНИК": "ustroystven-pravilnik",
               "ТАРИФА": "tarifa", "ИНСТРУКЦИЯ": "instruktsiya", "ПРАВИЛА": "pravila", "МЕТОДИКА": "metodika",
               "СПИСЪК": "spisak", "СТАТУТ": "statut", "УСТАВ": "ustav", "ПОЛОЖЕНИЕ": "polozhenie",
               "РЕГЛАМЕНТ": "reglament", "КРИТЕРИИ": "kriterii", "ПОРЯДЪК": "poryadak", "НОМЕНКЛАТУРА": "nomenklatura",
               "КЛАСИФИКАТОР": "klasifikator", "КОДЕКС": "kodeks"}
ADOPTED_BASE = {"naredba": "naredba", "pravilnik": "pravilnik", "ustroystven-pravilnik": "pravilnik", "tarifa": "tarifa",
                "instruktsiya": "instruktsiya"}
FORMULA = re.compile(r"^(?:МИНИСТЕРСКИЯТ СЪВЕТ|ПОСТАНОВИ|РЕШИ|НАРЕЖДАМ|УТВЪРЖДАВАМ)\s*:?$")
SIG = re.compile(r"^(?:(?i:за|и\.\s*д\.|временно\s+изпълняващ[аи]?(?:\s+длъжността)?|изпълняващ[аи]?\s+длъжността)\s+)?"
                 r"(?i:министър(?:-председател)?|заместник[- ]министър(?:-председател)?|главен\s+секретар|председател|"
                 r"заместник[- ]председател|управител|подуправител|изпълнителен\s+директор|директор|главен\s+прокурор|"
                 r"кмет|президент\s+на\s+републиката|вицепрезидент|омбудсман|главен\s+инспектор|ректор|началник|"
                 r"главнокомандващ)"
                 r"[^:]{0,160}:\s*(?:[А-ЯA-Z][^:]{0,70})?$")
STAMP = re.compile(r"^Подпечатан с държавния печат\.?$")
NAME_ONLY = re.compile(r"^[А-Я][а-я]*\.?(?:\s+[А-Я][а-я-]*\.?){0,3}$")
EDNOTE = re.compile(r"^\(?\s*(?:Забележка на редакцията|Вижте|Виж)\b[^.]{0,120}PDF", re.I)
ANNEX_HEAD = re.compile(r"^(?:Приложение|ПРИЛОЖЕНИЕ)(?!.*\b(?:се|думите|изменя|отменя|създава|допълва)\b)(?:\s+№\s*\S+)?"
                        r"(?:\s+(?:към|по)\s+.{0,160})?(?<!:)$")
AMENDING_TITLE = re.compile(r"^(?:за\s+)?(?:изменение|допълнение|изменения|отмяна|отменяне|отмeняне)\b", re.I)
# The acts taken from these pages when not already published: amending acts (not repeals).
LOW_RISK = re.compile(r"^за\s+(?:изменение|допълнение|изменения)\b")
DV_CITE = re.compile(
    r"\b(Постановление|Наредба(?:та)?|Правилник(?:а|ът)?|Устройствени?(?:ят|я)?\s+правилник|Тарифа(?:та)?|"
    r"Инструкция(?:та)?|Закона?|Кодекса?)"
    r"((?:(?!\b(?:Постановление|Наредба|Правилник|Устройствен|Тарифа|Инструкция|Закон|Кодекс))[^()]){0,400}?)"
    r"\(\s*(?:обн\.\s*,?\s*)?(?:ДВ|\"Държавен вестник\")\s*,?\s*бр\.\s*(\d+)\s+от\s+(?:\d{1,2}[\s.]+(?:\S+\s+)?)?(\d{4})")
CITE_BASE = [("Постановление", "postanovlenie"), ("Наредба", "naredba"), ("Устройствен", "pravilnik"),
             ("Правилник", "pravilnik"), ("Тарифа", "tarifa"), ("Инструкция", "instruktsiya"), ("Закон", "zakon"),
             ("Кодекс", "kodeks")]
AMEND_TARGET = re.compile(
    r"\b(?:изменение|допълнение|изменения|отмяна|отменяне|отмeняне)\b.*?\bна\s+(Постановление|Наредба(?:та)?|"
    r"Правилника|Устройствения\s+правилник|Тарифата|Инструкция(?:та)?|Закона|Кодекса)(.*)$")
TITLE_PREFIX = r"^\S+(?:\s+правилник)?(?:\s+№\s*\S+)?(?:\s+на\s+.{0,120}?)?"


def cite_base(word: str) -> str:
    return next(b for w, b in CITE_BASE if word.startswith(w))


def num_norm(s: str | None) -> str | None:
    """An act number compared across Latin and Cyrillic look-alike letters ('Н-5' and 'H-5')."""
    if not s:
        return None
    s = s.lower().translate(str.maketrans("aeiohkmpctxy", "аеіонкмрстху"))
    return re.sub(r"[^0-9a-zа-яі]", "", s) or None


def name_parts(rest: str) -> tuple[str | None, str | None, str | None]:
    """(number, year, subject) from what follows an act's kind word: '№ 5 от 2 март 2020 г. за ...'."""
    m = re.match(r"\s*№\s*([^\s,;]+)", rest)
    num = m.group(1).rstrip(".") if m else None
    m = re.search(r"\bот\s+(?:\d{1,2}\s*\.?\s*\S+\s+)?(\d{4})\s*г", rest[:200])
    yr = m.group(1) if m else None
    m = re.search(r"(?:^|\s)((?:за|относно)\s+.+)$", rest)
    subj = subj_norm(m.group(1)) if m else None
    return num, yr, subj


def dv_citations(text: str) -> list[list]:
    """[kind, number, year, subject, issue, issue year] for every act cited by name with its Gazette issue."""
    out = set()
    for m in DV_CITE.finditer(text):
        num, yr, subj = name_parts(m.group(2))
        out.add((cite_base(m.group(1)), num, yr, subj, int(m.group(3)), int(m.group(4))))
    return sorted([list(x) for x in out], key=lambda x: tuple(str(v) for v in x))


def act_desc(title: str, kind: str) -> dict:
    """The act's number, year and subjects (its own, and those of a text it adopts), from the Gazette's title."""
    t = title.replace('"', "")
    m = re.match(r"^\S+(?:\s+правилник)?((?:\s+№\s*\S+)?(?:\s+на\s+.{0,120}?)?(?:\s+от\s+\d{1,2}\s+\S+\s+\d{4}\s*г\.)?)\s*(.*)$", t)
    num, yr, _ = name_parts(m.group(1)) if m else (None, None, None)
    rest = m.group(2) if m else t
    subjects = set()
    if re.match(r"(?:за|относно|на)\s", rest):
        subjects.add(subj_norm(rest))
    kinds = {kind}
    ma = re.match(r"за\s+(?:приемане|одобряване|утвърждаване|издаване)\s+на\s+(Наредба|Правилник|Устройствен\s+правилник|"
                  r"Тарифа|Инструкция|Правила|Методика|Списък|Статут)(?:\s+№\s*\S+)?\s+((?:за|на|относно)\s+.+)$", rest)
    if ma:
        subjects.add(subj_norm(ma.group(2)))
        w = ma.group(1)
        if w in ("Наредба", "Правилник", "Тарифа", "Инструкция") or w.startswith("Устройствен"):
            kinds.add(cite_base(w))
    if kind in ("zakon", "kodeks"):
        s = subject(title)
        if s:
            subjects.add(subj_norm(s))
    return {"num": num_norm(num), "year": yr, "subjects": {s for s in subjects if s}, "kinds": kinds, "kind": kind}


def desc_matches(d: dict, kb: str, num: str | None, yr: str | None, subj: str | None, strict: bool) -> bool:
    """Whether a citation (kind, number, year, subject) names the act described by d. Not strict: a citation of the
    act's kind that gives neither number nor subject counts as naming it."""
    if num and d["num"] and kb == d["kind"]:
        # Both give the act's number: it decides (a different number is a different act of the same name).
        return num_norm(num) == d["num"] and (not yr or not d["year"] or yr == d["year"])
    if subj and kb in d["kinds"]:
        for s in d["subjects"]:
            # An amending act's subject starts with the same words as every other's ('за изменение и допълнение на
            # Наредба № ...'): compare it as far as it is held, so the amended act's number counts.
            n = 60 if AMENDING_TITLE.match(s) or AMENDING_TITLE.match(subj) else 40
            if subj.startswith(s[:n]) or s.startswith(subj[:n]):
                return True
    return bool(not strict and not num and not subj and kb in d["kinds"])


def dv_page(t: str):
    """(issue, year, day, section or None if unofficial, title, content html) of a material page, or None."""
    m = DV_MARK.search(t)
    mt = DV_TITLE_SPAN.search(t)
    if not m or not mt:
        return None
    iss, y = int(m.group(1)), int(m.group(4))
    day = date(y, int(m.group(3)), int(m.group(2))).isoformat()
    sec = norm(re.sub(r"<[^>]+>", "", m.group(5)))
    section = sec.split("/", 1)[1].strip() if "/" in sec else ""
    title = norm(re.sub(r"<[^>]+>", "", mt.group(1)))
    end = t.lower().rfind("</html>")
    # A page cut short (no closing </html> after the act) yields content None: it is held back as truncated.
    content = t[mt.end():end] if end > mt.end() else None
    return iss, y, day, (section if sec.startswith("Официален") else None), title, content


def dv_clean(lines: list[tuple[str, int]], content: str) -> tuple[list[tuple[str, int]], list[str]]:
    """The Gazette's editorial notes and its material number at the end are not part of the act."""
    notes, out = [], []
    for t, d in lines:
        if EDNOTE.match(t):
            if re.search(r"(?:този|целия)\s+материал", t):
                raise Hold("material_in_pdf")
            notes.append(t)
            continue
        out.append((t, d))
    if not out or not re.fullmatch(r"\d{1,6}", out[-1][0]):
        raise Hold("no_material_number")
    # The number is printed in its own paragraph after the act; inside a table of the act it would be a table cell.
    pre = content[:content.rfind(out[-1][0])].lower()
    if pre.count("<table") > pre.count("</table>"):
        raise Hold("material_number_in_table")
    return out[:-1], notes


ENDS_CLOSED = re.compile(r"[“”][\s.;,:)]*$")


def dv_lines(fragment: str) -> list[tuple[str, int]]:
    """raw_lines() with the Gazette's quoting read line by line: a name inside a quotation shares its closing mark
    ('думите „дирекция „Бюджет“ се заменят'), so marks are not counted across lines. A quotation spans lines when a line
    opens more marks than it closes and doesn't end on a closing mark; it ends at the line that closes more than it
    opens. Depth is 1 inside such a quotation, else 0."""
    fragment = re.sub(r"<!--.*?-->", "", fragment, flags=re.S)
    fragment = re.sub(r"<(style|script|xml)\b.*?</\1>", "", fragment, flags=re.S | re.I)
    out, inside = [], False
    for chunk in BLOCK.split(fragment):
        t = html.unescape(re.sub(r"<[^>]+>", "", chunk))
        n = norm(t)
        if not n or re.fullmatch(r"[.\s]+", n):
            continue
        out.append((n, 1 if inside else 0))
        opens, closes = t.count(OPEN_Q), sum(t.count(c) for c in CLOSE_Q)
        if inside:
            inside = not (closes > opens)
        else:
            inside = opens > closes and not ENDS_CLOSED.search(t.strip())
    return out


def check_numbering(keys: list[str], prefix: str = ""):
    """The act's own articles, and its own paragraphs (§), run 1, 2, 3 ... in order (a letter suffix follows its number):
    a gap or a step back means quoted text was taken for the act's own provisions, or the reverse."""
    for kind in ("art", "par"):
        prev = None
        for k in keys:
            m = re.fullmatch(re.escape(prefix) + kind + r"-(\d{3})(?:-(\d{2}))?", k)
            if not m:
                continue
            n, s = int(m.group(1)), int(m.group(2) or 0)
            ok = (n == 1 and not s) if prev is None else ((n == prev[0] + 1 and not s) or (n == prev[0] and s == prev[1] + 1))
            if not ok:
                raise Hold(f"numbering_gap:{k}")
            prev = (n, s)


def is_provision(t: str) -> bool:
    return bool(ART.match(t) or PAR.match(t) or SOLE_ART.match(t) or SOLE_PAR.match(t))


def dv_units(body: list[tuple[str, int]], prefix: str = "") -> dict:
    """Provisions, headings and preamble of one text, keyed as in split(); a chapter's title lines stay with its heading."""
    first = next((t for t, d in body if d == 0 and is_provision(t)), None)
    if first is None:
        raise Hold("no_provisions" + (f":{prefix.rstrip('-')}" if prefix else ""))
    par_mode = bool(PAR.match(first) or SOLE_PAR.match(first))
    units: dict[str, dict] = {}
    order: list[str] = []
    pending: list[list[str]] = []
    cur = prefix + "uvod"
    units[cur] = {"label": "Увод", "kind": "preamble", "lines": []}
    order.append(cur)

    def flush_headings(final: bool = False):
        prev = next((k for k in reversed(order) if k != prefix + "uvod"), None)
        for j, h in enumerate(pending, 1):
            if final:
                hk = f"{prefix}zz-heading-{j}"
            else:
                hk = f"{prev}-zz-heading-{j}" if prev else f"{prefix}0-heading-{j}"
            if hk in units:
                raise Hold(f"duplicate_unit:{hk}")
            units[hk] = {"label": " ".join(h)[:200], "kind": "heading", "lines": [f"# {h[0]}"] + h[1:]}
            order.append(hk)
        pending.clear()

    def begin(key: str, label: str, kind: str, heading: str, rest: str):
        nonlocal cur
        key = prefix + key
        if key in units:
            raise Hold(f"duplicate_unit:{key}")
        flush_headings()
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
                pending.append([t])
                continue
            if pending:
                if len(t) >= 300:
                    raise Hold("text_between_heading_and_provision")
                pending[-1].append(t)
                continue
        units[cur]["lines"].append(t)
    if pending:
        flush_headings(final=True)
    out = {}
    for key in order:
        u = units[key]
        if u["lines"]:
            out[key] = {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"}
    if not any(k[len(prefix):].startswith(("art-", "par-")) for k in out):
        raise Hold("no_provisions")
    check_numbering(list(out), prefix)
    return out


def title_block(L: list[tuple[str, int]], i: int) -> int:
    """Index after an act's title: its first line, a continuation in capitals ('№ 5', 'ОТ ...') and the subtitle
    ('за ...', with the cited act's '(обн., ДВ, ...)')."""
    j = i + 1
    while j < len(L) and j <= i + 6:
        t = L[j][0]
        if FORMULA.match(t) or is_provision(t) or HEADINGS.match(t) or SIG.match(t):
            break
        # A title line runs on in lower case ('за ...', 'приета с ...'), or gives the act's number, date or the cited
        # act's Gazette issues in brackets; a preamble starts with a capital ('На основание ...').
        if re.match(r"^(?:\d{0,2}[а-я]|\(|№|ОТ\s+\d)", t):
            j += 1
            continue
        break
    return j


def segment_end(L: list[tuple[str, int]], i: int) -> int:
    """Where a text's provisions end: its signatures or its first annex (at quote depth 0, after a provision)."""
    seen = False
    for k in range(i, len(L)):
        t, d = L[k]
        if d:
            # Signatures inside a quotation: a quotation mark the Gazette left unclosed, so the provisions after it
            # can't be told from quoted text.
            if seen and ((SIG.match(t) and not t.rstrip().endswith(":")) or STAMP.match(t)):
                raise Hold("unbalanced_quotes")
            continue
        if seen and (SIG.match(t) or STAMP.match(t) or ANNEX_HEAD.match(t)):
            return k
        if is_provision(t):
            seen = True
    if L and L[-1][1]:
        raise Hold("unbalanced_quotes")
    return len(L)


def dv_split(L: list[tuple[str, int]], kind: str) -> tuple[dict, str, list[str]]:
    """(units, title text, kinds of adopted texts) of a regulation or decree page; a decree's adopted text follows its
    signatures."""
    s = 0
    while s < min(3, len(L)) and not DV_TITLE_LINE[kind].match(L[s][0]) and ISSUER_LINE.match(L[s][0]) and L[s][1] == 0:
        s += 1
    if s >= len(L) or not DV_TITLE_LINE[kind].match(L[s][0]):
        raise Hold("no_title_line" if not any(DV_TITLE_LINE[kind].match(t) for t, _ in L[:6]) else "text_before_title")
    i = title_block(L, s)
    title_text = " ".join(t for t, _ in L[s:i])
    e = segment_end(L, i)
    units = dv_units(L[i:e], "")
    top = [t for t, d in L[i:e] if d == 0]
    k = e
    last_prefix = ""
    adopted = []
    while True:
        prev_named = False
        while k < len(L) and (SIG.match(L[k][0]) or STAMP.match(L[k][0])
                              or (prev_named and NAME_ONLY.match(L[k][0]))):
            prev_named = bool(SIG.match(L[k][0]) and L[k][0].rstrip().endswith(":"))
            k += 1
        if kind == "postanovlenie" and k < len(L) and L[k][1] == 0 and ADOPTED_TITLE.match(L[k][0]):
            word = ADOPTED_TITLE.match(L[k][0]).group(1)
            last_prefix = ADOPTED_KEY[word] + "-"
            adopted.append(ADOPTED_KEY[word])
            j = title_block(L, k)
            e = segment_end(L, j)
            more = dv_units(L[j:e], last_prefix)
            clash = set(more) & set(units)
            if clash:
                raise Hold("duplicate_unit:" + sorted(clash)[0])
            units.update(more)
            top += [t for t, d in L[j:e] if d == 0]
            k = e
            continue
        break
    if k < len(L):
        if not re.match(r"^(?:Приложени[ея]|ПРИЛОЖЕНИ[ЕЯ])\b", L[k][0]):
            raise Hold("text_after_end:" + L[k][0][:80])
        annex = L[k:]
        # Some acts are signed after their annexes: the signatures at the end are not part of the annex.
        while annex and (SIG.match(annex[-1][0]) or STAMP.match(annex[-1][0])
                         or (len(annex) > 1 and NAME_ONLY.match(annex[-1][0]) and SIG.match(annex[-2][0])
                             and annex[-2][0].rstrip().endswith(":"))):
            annex = annex[:-1]
        if any(d == 0 and (ART.match(t) or PAR.match(t)) for t, d in annex):
            raise Hold("provisions_after_annex")
        units[last_prefix + "prilozhenie-01"] = {"label": "Приложение", "kind": "annex",
                                                 "text": "\n".join(t for t, _ in annex) + "\n"}
    return units, title_text, adopted, top


NUMBER_WORDS = {"един": 1, "два": 2, "три": 3, "четири": 4, "пет": 5, "шест": 6, "седем": 7, "осем": 8, "девет": 9,
                "десет": 10, "дванадесет": 12, "четиринадесет": 14, "петнадесет": 15, "двадесет": 20, "тридесет": 30}


def dv_resolve(c: str, gday: str, own_day: str | None) -> tuple[str, str]:
    exceptions = bool(re.search(r"с изключение|освен", c))
    tag = "+exceptions" if exceptions else ""
    if re.match(r"(?:от|в)\s+(?:деня|датата)\s+на\s+обнародването|от\s+обнародването", c):
        return gday, "publication" + tag
    if re.match(r"три\s+дни\s+след\s+обнародването", c):
        return (date.fromisoformat(gday) + timedelta(days=3)).isoformat(), "default" + tag
    m = re.match(r"(\d{1,3}|" + "|".join(NUMBER_WORDS) + r")\s+(дни|дена|месеца?)\s+след\s+(?:деня\s+на\s+)?обнародването", c)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBER_WORDS[m.group(1)]
        g = date.fromisoformat(gday)
        if m.group(2).startswith("д"):
            return (g + timedelta(days=n)).isoformat(), "days_after_publication" + tag
        # A term in months ends on the same day of the month n months on; with no such day, the act is held.
        y, mo = divmod(g.month - 1 + n, 12)
        try:
            return date(g.year + y, mo + 1, g.day).isoformat(), "months_after_publication" + tag
        except ValueError:
            raise Hold("in_force_month_end:" + c[:80])
    if re.match(r"от\s+(?:деня|датата)\s+на\s+(?:приемането|издаването|подписването)\s+(?:му|ѝ|й)\b", c):
        if own_day:
            return own_day, "adoption" + tag
        raise Hold("in_force_adoption_day_unknown")
    m = re.match(r"(?:от|на)\s+(\d{1,2}\s*\.?\s*\S+\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{4})\s*г", c)
    if m:
        d = parse_day(m.group(1))
        if d:
            return d, "date" + tag
    raise Hold("in_force_unreadable:" + c[:120])


PROVISION_MARK = re.compile(r"^(?:(?:§|Чл\.)\s*\d+\s*[а-я]?\s*\.\s*|(?:Член|Параграф)\s+единствен\s*\.?\s*)?(?:\(\d+\)\s*)?")
CLAUSE_SUBJ = re.compile(
    r"^(?:Постановлението|Наредбата|Правилникът|Устройственият правилник|Тарифата|Инструкцията|"
    r"Настоящ(?:ата|ият|ото)\s+(?:наредба|правилник|инструкция|тарифа|постановление)|Тази\s+(?:наредба|инструкция|тарифа)|"
    r"Този\s+(?:устройствен\s+)?правилник|Това\s+постановление)(?:\s+и\s+[^.]{0,80}?)?"
    r"(?:\s+се\s+(?:приема|издава)\s+на\s+основание\s+[^;]{0,400}?\s+и)?\s+влиза(?:т)?\s+в\s+сила\s+(.*)$")


def dv_in_force(top: list[str], gday: str, own_day: str | None, normative: bool) -> tuple[str, str]:
    """(day, how): the act's own in-force clauses (all must give one day), else for a normative act Gazette day + 3.
    Only lines of the act itself count (quote depth 0): a clause an amending act writes into another act is quoted."""
    found, partial = set(), False
    for t in top:
        m = CLAUSE_SUBJ.match(t[PROVISION_MARK.match(t).end():])
        if m:
            found.add(dv_resolve(re.match(r"(?:\d\.(?=\d)|[^.])*", m.group(1)).group(0), gday, own_day))
        elif re.search(r"\bвлиза(?:т)?\s+в\s+сила\s+(?:от|на)\s", t) and not t.startswith('"'):
            partial = True
    if not found:
        if normative:
            return (date.fromisoformat(gday) + timedelta(days=3)).isoformat(), "default" + ("+exceptions" if partial else "")
        raise Hold("no_in_force_clause")
    days = {d for d, _ in found}
    if len(days) > 1:
        raise Hold("in_force_conflict:" + ",".join(sorted(days)))
    return days.pop(), "+".join(sorted({h for _, h in found})) + ("+exceptions" if partial else "")


def dv_load(src: Path) -> list[dict]:
    """Every dated material page held: idMat, issue, year, day and file (the first copy listed for a material)."""
    out, seen = [], set()
    for name, folder in (("dvmat.jsonl", "dv"), ("cc-dvmat.jsonl", "cc-dv")):
        p = src / name
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("issue") and r.get("date") and int(r["date"][:4]) == r["year"]:
                f = src / folder / str(r["idMat"] // 1000) / f"{r['idMat']}.html.gz"
                if f.exists() and r["idMat"] not in seen:
                    seen.add(r["idMat"])
                    out.append({"id": r["idMat"], "issue": r["issue"], "year": r["year"], "date": r["date"], "file": f})
    return out


def dv_publish(a, src: Path, acts: dict, dv_days: dict, cites_of, memo, contested: set, rejects: dict, cited_by: dict,
               titles_named: dict) -> dict:
    # Acts already published from these pages (the repository's data/paths.json): they keep their part.
    on_main: set[str] = set()
    if a.on_main:
        on_main = set(json.loads(Path(a.on_main).read_text(encoding="utf-8")).get("paths", {}))
    # Each page's header (issue, day, section, title) is near its top: only that is read for every page; the whole page
    # is read for the acts of the kinds published here (and, on a cache miss, for its citations).
    pages = {}
    for m in dv_load(src):
        with gzip.open(m["file"]) as fh:
            head = fh.read(65536).decode("utf-8", "replace")
        pages[m["id"]] = (m, dv_page(head))

    def full(m) -> tuple[bytes, str]:
        raw = gzip.decompress(m["file"].read_bytes())
        return raw, raw.decode("utf-8", "replace")

    # Who cites which act by name and Gazette issue: every final text of the National Assembly and every page held.
    dv_cited: dict[tuple[int, int], list] = defaultdict(list)

    def note(found, own, who):
        for kb, num, yr, subj, n, y in found:
            if (n, y) != own:
                dv_cited[(n, y)].append((kb, num, yr, subj, who))

    for i, r in acts.items():
        if not (r.get("final_len") and r.get("L_Act_dv_iss") and str(r["L_Act_dv_iss"]).isdigit()):
            continue
        f = src / "raw" / str(i // 1000) / f"{i}.json.gz"
        own = (int(r["L_Act_dv_iss"]), int(r["L_Act_dv_year"]))
        note(cites_of(f, lambda f=f: norm(re.sub(r"<[^>]+>", " ", json.loads(gzip.decompress(f.read_bytes()).decode("utf-8"))
                                                .get("L_ActL_final_body") or ""))), own, f"na:{i}")
    for mid, (m, pg) in pages.items():
        note(cites_of(m["file"], lambda m=m: norm(re.sub(r"<[^>]+>", " ", full(m)[1]))), (m["issue"], m["year"]), f"dv:{mid}")

    # What each held page is (is an amending act's target held?), and which acts later titles name as amended.
    descs: dict[tuple[int, int], list] = defaultdict(list)
    amended: dict[str, list] = defaultdict(list)
    for mid, (m, pg) in pages.items():
        if not pg:
            continue
        title = pg[4]
        kind = next((k for rx, k in DV_KIND if rx.match(title)), None)
        if kind:
            descs[(m["issue"], m["year"])].append((mid, act_desc(title, kind)))
        mt = AMEND_TARGET.search(title.replace('"', ""))
        if mt:
            kb = cite_base(mt.group(1))
            amended[kb].append((kb, *name_parts(mt.group(2)), (m["year"], m["issue"]), f"dv:{mid}"))
    law_texts: dict[tuple[int, int], list] = defaultdict(list)
    for i, r in acts.items():
        if str(r.get("L_Act_T_id")) != "1" or not str(r.get("L_Act_dv_iss") or "").isdigit() or not r.get("L_Act_dv_year"):
            continue
        key = (int(r["L_Act_dv_iss"]), int(r["L_Act_dv_year"]))
        title = norm(r.get("L_ActL_final") or r.get("L_ActL_title") or "")
        if r.get("final_len"):
            law_texts[key].append((i, title))
        mt = AMEND_TARGET.search(title.replace('"', ""))
        if mt:
            kb = cite_base(mt.group(1))
            amended[kb].append((kb, *name_parts(mt.group(2)), (key[1], key[0]), f"na:{i}"))

    def target_held(kb, num, yr, subj, n, y) -> bool:
        if any(desc_matches(d, kb, num, yr, subj, strict=True) for _, d in descs.get((n, y), [])):
            return True
        if kb in ("zakon", "kodeks") and subj:
            for _, lt in law_texts.get((n, y), []):
                s = subject(lt)
                if s and (subj.startswith(subj_norm(s)[:40]) or subj_norm(s).startswith(subj[:40])):
                    return True
        return False

    # Every National Assembly law or bill record by year (its Gazette year, else the year it was filed): a law adopted
    # from 2009 on may gain its final text on parliament.bg later, and the 40-zakoni parts would then publish it.
    law_records: dict[int, list] = defaultdict(list)
    for i, r in acts.items():
        if str(r.get("L_Act_T_id")) != "1":
            continue
        y = int(r["L_Act_dv_year"]) if r.get("L_Act_dv_year") else int((r.get("L_Act_date") or "0")[:4] or 0)
        title = norm(r.get("L_ActL_final") or r.get("L_ActL_title") or "")
        title = re.sub(r"^Законопроект\b", "Закон", title)
        lt = re.sub(r"[^а-я0-9]", "", title.lower())
        law_records[y].append((bool(r.get("final_len")), lt))
    st = (src / "acts.jsonl").stat()
    records_sig = f"{st.st_size}:{st.st_mtime_ns}"

    def law_on_record(title: str, year: int) -> tuple[float, bool]:
        """(similarity, has text) of the National Assembly record whose title best matches this law's, of the same
        year or the year before (below 0.6 reads as 0). Cached with the record file's size and mtime."""
        def compute():
            import difflib
            k = re.sub(r"[^а-я0-9]", "", title.lower())
            sm = difflib.SequenceMatcher(None)
            sm.set_seq2(k)
            best = [0.0, False]
            for y in (year, year - 1):
                for has_text, lt in law_records.get(y, []):
                    sm.set_seq1(lt)
                    # quick_ratio() bounds ratio() from above: a record that can't reach 0.6 or the best so far is skipped.
                    if sm.real_quick_ratio() < max(0.6, best[0]) or sm.quick_ratio() < max(0.6, best[0]):
                        continue
                    best = max(best, [sm.ratio(), has_text])
            return best
        score, has_text = memo(f"dvlawrec|{records_sig}|{year}|{title}", compute)
        return score, has_text

    parts: dict[tuple[str, int], dict] = defaultdict(lambda: {"laws": {}, "acts": []})
    holds, skipped = [], defaultdict(int)
    for mid in sorted(pages):
        m, pg = pages[mid]
        if not pg:
            skipped["not_a_material_page"] += 1
            continue
        title, section = pg[4], pg[3]
        kind = next((k for rx, k in DV_KIND if rx.match(title)), None)
        if not kind or section is None:
            skipped["other_kind_or_unofficial"] += 1
            continue
        if section not in DV_SECTIONS.get(kind, DV_REG_SECTIONS):
            skipped["kind_outside_its_section"] += 1
            continue
        if DV_PERSONAL.search(title):
            skipped["about_named_people"] += 1
            continue
        raw, t = full(m)
        iss, year, gday, section, title, content = dv_page(t)
        try:
            if f"dv:{mid}" in rejects:
                raise Hold("rejected:" + str(rejects[f"dv:{mid}"])[:200])
            if (iss, year) != (m["issue"], m["year"]) or gday != m["date"]:
                raise Hold("header_mismatch")
            if len(dv_days.get((iss, year), ())) > 1:
                raise Hold("gazette_conflict")
            if content is None:
                raise Hold("page_truncated")
            d = act_desc(title, kind)
            # An act already published keeps its part: the hold rules on later texts and amended targets, which apply
            # to acts not yet published, are not applied to it again (a later version is appended, never a removal).
            known = any(f"{k}-{year}-dv{iss:03d}-{mid}" in on_main for k in (kind, "kodeks"))
            if kind in ("zakon", "kodeks"):
                score, has_text = law_on_record(title, year)
                if score >= 0.85 and has_text:
                    skipped["law_on_national_assembly_record"] += 1
                    continue
                if score >= 0.85 and year >= 2009:
                    raise Hold("law_on_record_without_text")
                if 0.6 <= score < 0.85:
                    raise Hold(f"law_maybe_on_record:{score:.2f}")
            # A later text held here cites it by name and Gazette issue.
            later = {who for kb, num, yr, subj, who in dv_cited.get((iss, year), [])
                     if who != f"dv:{mid}" and desc_matches(d, kb, num, yr, subj, strict=False)}
            if kind in ("zakon", "kodeks"):
                for csubj, who in cited_by.get((iss, year), {}).items():
                    if any(csubj.startswith(s[:40]) or s.startswith(csubj[:40]) for s in d["subjects"]):
                        later |= who - {f"dv:{mid}"}
            if later and not known:
                raise Hold("cited_later:" + ",".join(sorted(later)[:5]))
            named = {who for k in d["kinds"] for kb, num, yr, subj, when, who in amended.get(k, ())
                     if who != f"dv:{mid}" and when > (year, iss) and desc_matches(d, kb, num, yr, subj, strict=True)}
            if kind in ("zakon", "kodeks"):
                for s in d["subjects"]:
                    named |= {f"na:{x}" for x in titles_named.get(s, ())}
            if named and not known:
                raise Hold("named_as_amended:" + ",".join(sorted(named)[:5]))
            if kind in ("zakon", "kodeks") and title_key(title) in contested:
                raise Hold("contested_constcourt")
            m_day = re.match(TITLE_PREFIX + r"\s+от\s+(\d{1,2}\s+\S+\s+\d{4})\s*г", title)
            own_day = parse_day(m_day.group(1)) if m_day else None
            if own_day and own_day > gday:
                raise Hold(f"dated_after_gazette:{own_day}")
            L, notes = dv_clean(dv_lines(content), content)
            if kind in ("zakon", "kodeks"):
                mdec = DECREE_DAY.search(norm(re.sub(r"<[^>]+>", " ", content))[:3000])
                dday = parse_day(mdec.group(1) + " г") if mdec else None
                if not dday:
                    raise Hold("decree_day_unreadable")
                if not (dday <= gday <= (date.fromisoformat(dday) + timedelta(days=20)).isoformat()):
                    raise Hold(f"gazette_day_inconsistent:{gday} vs decree {dday}")
                units = split(L, title)
                check_numbering(list(units))
                madopt = next((x for x, _ in L if ADOPTED.match(x)), "")
                own_day = parse_day(madopt) if madopt else None
                start = next(i for i, (x, _) in enumerate(L) if x == x.upper()
                             and x.upper().startswith(("ЗАКОН", "КОДЕКС", "ИЗБОРЕН КОДЕКС")))
                stop = next((i for i in range(start, len(L)) if is_provision(L[i][0]) or HEADINGS.match(L[i][0])), len(L))
                title_text = " ".join(x for x, _ in L[start:min(stop, start + 6)])
                normative = True
            else:
                units, title_text, adopted, top = dv_split(L, kind)
                normative = kind in DV_NORMATIVE or any(x in ADOPTED_BASE for x in adopted) or bool(re.search(
                    r"за\s+(?:изменение|допълнение|отменяне|отмяна)\S*(?:\s+и\s+\S+)?\s+на\s+(?:Наредба|Правилник|"
                    r"Устройствени?я?\s+правилник|Тарифа|Инструкция|нормативни)", title))
            # An amending or repealing act is published only when its target's text is held here.
            m_rest = re.match(TITLE_PREFIX + r"(?:\s+от\s+\d{1,2}\s+\S+\s+\d{4}\s*г\.)?\s*(.*)$", title)
            if AMENDING_TITLE.match(m_rest.group(1) if m_rest else ""):
                targets = {tuple(x) for x in dv_citations(title_text + " " + title)}
                if re.search(r"нормативни\s+актове", title):
                    for k, u in units.items():
                        if re.search(r"(?:^|-)(?:par|art)-\d", k) and "\n" in u["text"]:
                            targets |= {tuple(x) for x in dv_citations(u["text"].split("\n")[1])}
                if not targets:
                    raise Hold("amending_target_unidentified")
                missing = [x for x in sorted(targets, key=str) if not target_held(*x)]
                if missing and not known:
                    kb, num, yr, subj, n, y = missing[0]
                    raise Hold(f"amending_target_not_held:{kb} {num or ''} бр. {n}/{y}")
            if kind in ("zakon", "kodeks"):
                day, how = in_force(units, gday)
            else:
                day, how = dv_in_force(top, gday, own_day, normative)
        except Hold as h:
            holds.append({"id": mid, "kind": kind, "dv": f"{iss}/{year}", "title": title[:160], "reason": str(h)})
            continue
        if kind == "zakon" and re.match(r"^\S*\s*[Кк]одекс\b|^[А-Я][а-я]+\s+кодекс$|^Кодекс\b", title) \
                and not re.search(r"изменение|допълнение|отмяна", title):
            kind = "kodeks"
        slug = f"{kind}-{year}-dv{iss:03d}-{mid}"
        # Acts already published stay in their part. Any other act is taken only when it amends another act: an
        # amending act is rarely amended in turn, while a base act's later amendment may sit in an issue not captured.
        if slug in on_main:
            family = f"50-dv-{kind}-{year}"
        elif LOW_RISK.match(m_rest.group(1) if m_rest else ""):
            family = f"51-dv-lowrisk-{kind}-{year}"
        else:
            holds.append({"id": mid, "kind": kind, "dv": f"{iss}/{year}", "title": title[:160],
                          "reason": "base_act_not_low_risk"})
            continue
        note_parts = []
        if "exceptions" in how:
            note_parts.append("Its final provisions give some provisions a different day; the whole text is dated by its "
                              "general day.")
        if notes:
            note_parts.append("The Gazette printed part of this act only in the issue's PDF facsimile (its note: "
                              + "; ".join(sorted(set(notes)))[:300] + "); that part is not carried.")
        parts[(family, kind)]["laws"][slug] = {
            "label": f"{title} (ДВ, бр. {iss} от {year} г.)", "title": title,
            "kind": "law" if kind in ("zakon", "kodeks") else "decree", "enacted": own_day, "published": gday,
            "url": DV_URL.format(id=mid), "temporary_until": None, "restores": None, "note": None}
        parts[(family, kind)]["acts"].append({
            "slug": slug, "short": title, "title": title, "url": DV_URL.format(id=mid), "first_law": slug,
            "earlier_laws": [],
            "versions": [{"from": day, "source_url": DV_URL.format(id=mid), "sha256": hashlib.sha256(raw).hexdigest(),
                          "units": units, "credits": {}, **({"note": " ".join(note_parts)} if note_parts else {})}]})

    # Coverage: Gazette issues from 2009 (their count read from the highest issue number seen in each year) with no
    # captured page at all.
    issue_top: dict[int, int] = defaultdict(int)
    for n, y in list(dv_days) + [(int(r["L_Act_dv_iss"]), int(r["L_Act_dv_year"])) for r in acts.values()
                                 if str(r.get("L_Act_dv_iss") or "").isdigit() and r.get("L_Act_dv_year")]:
        issue_top[y] = max(issue_top[y], n)
    years = [y for y in issue_top if y >= 2009]
    coverage = (sum(issue_top[y] for y in years),
                sum(1 for y in years for n in range(1, issue_top[y] + 1) if (n, y) not in dv_days),
                max(years) if years else 2009)

    written = []
    stale = {f.stem for f in PARTS.glob("50-dv-*.json")} | {f.stem for f in PARTS.glob("51-dv-lowrisk-*.json")}
    for (name, kind) in sorted(parts):
        p = parts[(name, kind)]
        p["acts"].sort(key=lambda x: x["slug"])
        stale.discard(name)
        write_part(name, dv_part_meta(p, a.retrieved, coverage, name.startswith("51-")))
        written.append((f"{name}.json", len(p["acts"])))
    for name in sorted(stale):  # every act of an earlier part is held back now: the part stays, empty
        write_part(name, dv_part_meta({"laws": {}, "acts": []}, a.retrieved, coverage, name.startswith("51-")))
        written.append((f"{name}.json", 0))
    if a.report:
        rp = Path(a.report)
        rp.with_name(rp.stem + "-dv" + rp.suffix).write_text(
            "".join(json.dumps(h, ensure_ascii=False) + "\n" for h in holds), encoding="utf-8")
    by_kind = defaultdict(lambda: [0, 0])
    for (name, kind), p in parts.items():
        by_kind[kind][0] += len(p["acts"])
    for h in holds:
        by_kind[h["kind"]][1] += 1
    reasons = defaultdict(int)
    for h in holds:
        reasons[h["reason"].split(":")[0]] += 1
    return {"dv_published": sum(n for _, n in written),
            "dv_lowrisk_new": sum(len(p["acts"]) for (name, _), p in parts.items() if name.startswith("51-")),
            "dv_held": len(holds), "dv_issues_without_page": f"{coverage[1]} of {coverage[0]}",
            "dv_published_held_by_kind": dict(sorted(by_kind.items())), "dv_held_by_reason": dict(reasons),
            "dv_skipped": dict(skipped), "dv_parts": len(written)}


def dv_part_meta(p: dict, retrieved: str, coverage: tuple[int, int, int], lowrisk: bool) -> dict:
    p["sources"] = [{"name": "Държавен вестник: материали от официалния раздел (dv.parliament.bg, копия в Internet Archive и "
                             "Common Crawl)",
                     "url": "https://dv.parliament.bg/DVWeb/", "retrieved": retrieved,
                     "licence": "Official legal text; not subject to copyright (ЗАПСП чл. 4, т. 1)",
                     "notes": "Each act's text as the State Gazette printed it, with the issue number and date from the "
                              "page's own header."}]
    p["decisions"] = [
        "Each act here is one State Gazette material page of the official section, as printed; the Gazette issue and its "
        "date are read from the page's own header.",
        "The text runs from the act's title to its signatures; the issuing body's name above the title, the signatures, "
        "the Gazette's material number and its editorial notes are not part of the act. An annex the Gazette printed only in the issue's PDF is not carried, "
        "and the version's note says so.",
        "A Council of Ministers decree that adopts a regulation, rules, tariff or other text is one act: the decree's "
        "provisions keep their own keys, the adopted text's provisions carry its kind in front (naredba-art-001).",
        "Its one version takes effect on the day its own final provisions name (all such clauses must agree); a "
        "normative act (regulation, rules, instruction, tariff, a decree adopting, amending or repealing one, or a law) "
        "with no such clause takes effect three days after its Gazette day (Constitution чл. 5, ал. 5); any other "
        "decree with no such clause is held back.",
        "An act is published only when no later text held here cites it by name and Gazette issue and no later act's "
        "title names it as amended or repealed; an amending or repealing act only when its target's text is held here.",
        "A law comes from these pages only when the National Assembly's record holds no text for it; a law whose title "
        "matches a record with text is left to the 40-zakoni parts.",
        f"These acts come only from the State Gazette pages that archives captured: of about {coverage[0]:,} Gazette "
        f"issues from 2009 to {coverage[2]}, {coverage[1]:,} have no captured page at all. A later amendment printed in an "
        "issue that was not captured is not shown here, so check the official State Gazette (dv.parliament.bg) before "
        "relying on an act's current text."]
    if lowrisk:
        p["decisions"].append(
            "Acts in this part are amending acts only (titles 'за изменение', 'за допълнение', 'за изменение и "
            "допълнение'): an amending act is rarely amended in turn. Base acts (regulations, rules, instructions, "
            "tariffs, decrees that adopt or approve them, one-off decrees) not already published are held back.")
    p["ai_use"] = ["none"]
    return {k: p[k] for k in ("laws", "acts", "sources", "decisions", "ai_use")}


def write_part(name: str, p: dict):
    """Atomic write of corpus.d/<name>.json (only when changed) and its .PUBLISH marker."""
    PARTS.mkdir(exist_ok=True)
    f = PARTS / f"{name}.json"
    data = (json.dumps(p, ensure_ascii=False, indent=1, sort_keys=False) + "\n").encode("utf-8")
    if not (f.exists() and f.read_bytes() == data):
        tmp = f.with_suffix(".tmp")
        tmp.write_bytes(data)
        for attempt in range(10):
            try:
                tmp.replace(f)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(1)
    pub = f.with_suffix(".PUBLISH")
    if not pub.exists():
        pub.write_text("Parsed by parse_acts.py from State Gazette material pages; one version, as published; acts cited "
                       "by a later text, named as amended, or amending a text not held are held back.\n",
                       encoding="utf-8", newline="\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--report")
    ap.add_argument("--retrieved", required=True, help="the day the inputs were retrieved (YYYY-MM-DD)")
    ap.add_argument("--contested", help="the Constitutional Court's list of contested acts (constcourt.bg/bg/contested-acts)")
    ap.add_argument("--eurlex", help="CSV num,date,name: Gazette issue dates from the EU's national-measures records")
    ap.add_argument("--cache", help="file caching each input file's citations by size and mtime (speeds up re-runs)")
    ap.add_argument("--rejects", help="JSON {act id: reason}: acts held back by hand or by a failed read-back check")
    ap.add_argument("--keep", help="JSON list of law slugs already published: a later citation or title found "
                                   "afterwards doesn't hold them back (they keep their text as published)")
    ap.add_argument("--on-main", help="the repository's data/paths.json: State Gazette acts already published keep their "
                                      "part; any other is taken only if it is an amending act")
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
    # --keep: slugs of laws already published; a later citation or title found afterwards doesn't hold them back.
    keep_slugs = set(json.loads(Path(a.keep).read_text(encoding="utf-8"))) if a.keep and Path(a.keep).exists() else set()
    keep_ids = {int(s.rsplit("-", 1)[1]) for s in keep_slugs if s.rsplit("-", 1)[-1].isdigit()}

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

    # The citations found in each input file are cached by the file's size and modification time (--cache): a run
    # then reads only files that are new or changed. The cache holds only what citations() returns for the file.
    cache_path = Path(a.cache) if a.cache else None
    cache: dict = {}
    if cache_path and cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cache = {}
    fresh: dict = {}

    def cites_of(f: Path, read_text) -> set:
        st = f.stat()
        sig = f"{st.st_size}:{st.st_mtime_ns}"
        hit = cache.get(str(f))
        if hit and hit[0] == sig:
            fresh[str(f)] = hit
            return {tuple(x) for x in hit[1]}
        found = citations(read_text())
        fresh[str(f)] = [sig, sorted(list(x) for x in found)]
        return found

    def note_cites(found: set, own: tuple[int, int], who: str):
        for subj, n, y in found:
            if (n, y) != own:
                cited_by[(n, y)][subj].add(who)

    for i, r in acts.items():
        if not (r.get("final_len") and r.get("L_Act_dv_iss") and str(r["L_Act_dv_iss"]).isdigit()):
            continue
        own = (int(r["L_Act_dv_iss"]), int(r["L_Act_dv_year"]))
        f = src / "raw" / str(i // 1000) / f"{i}.json.gz"
        note_cites(cites_of(f, lambda: norm(re.sub(r"<[^>]+>", " ", body(i)[1].get("L_ActL_final_body") or ""))),
                   own, f"na:{i}")
        m = TARGET.search(norm(r.get("L_ActL_final") or ""))
        if m:
            titles_named[subj_norm(m.group(1))].add(i)
    for own, f in dv_texts:
        note_cites(cites_of(f, lambda: norm(re.sub(r"<[^>]+>", " ", gzip.decompress(f.read_bytes()).decode("utf-8", "replace")))),
                   own, f"dv:{f.name.split('.')[0]}")

    def dv_cites_of(f: Path, read_text) -> list:
        """dv_citations() of a file, cached like cites_of() under its own key."""
        st = f.stat()
        sig = f"{st.st_size}:{st.st_mtime_ns}"
        key = "dvcite|" + str(f)
        hit = cache.get(key)
        if hit and hit[0] == sig:
            fresh[key] = hit
            return [tuple(x) for x in hit[1]]
        found = dv_citations(read_text())
        fresh[key] = [sig, found]
        return [tuple(x) for x in found]

    def memo(key: str, compute):
        """A value cached under a key that names every input it depends on."""
        if key in cache:
            fresh[key] = cache[key]
        else:
            fresh[key] = compute()
        return fresh[key]

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
            kept = i in keep_ids
            named = sn and titles_named.get(sn, set()) - {i}
            kept_held = kept and bool(later or named)  # published before; held now only by what was found afterwards
            if later and not kept:
                raise Hold("cited_later:" + ",".join(sorted(later)[:5]))
            if named and not kept:
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
        if kept_held and slug not in keep_slugs:  # the kept slug was another act's: hold as without --keep
            holds.append({"id": i, "dv": f"{iss}/{year}", "title": title[:160], "reason": f"keep_slug_mismatch:{slug}"})
            continue
        label = f"{title} (ДВ, бр. {iss} от {year} г.)"
        adopted = (r.get("L_Act_date2") or "")[:10] or None
        note = None
        if "exceptions" in how:
            note = "Its final clause gives some provisions a different day; the whole text is dated by its general day."
        pk = 0 if kept_held else year  # part 0: corpus.d/41-zakoni-kept.json
        parts[pk]["laws"][slug] = {"label": label, "title": title, "kind": "law", "enacted": adopted,
                                   "published": gday, "url": SOURCE_URL.format(id=i), "temporary_until": None,
                                   "restores": None, "note": None}
        parts[pk]["acts"].append({
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
        if year == 0:
            p["decisions"].append(
                "The laws in this part were published under that rule before a later text citing them, or a later "
                "law's title naming them, was found; that doesn't make their text as published wrong, so each keeps "
                "its one version as published until its later versions are built.")
        p["ai_use"] = ["none"]
        f = PARTS / ("41-zakoni-kept.json" if year == 0 else f"40-zakoni-{year}.json")
        data = (json.dumps(p, ensure_ascii=False, indent=1, sort_keys=False) + "\n").encode("utf-8")
        # Rewrite a part only when it changed (readers may hold it open; Windows refuses to replace an open file).
        if not (f.exists() and f.read_bytes() == data):
            tmp = f.with_suffix(".tmp")
            tmp.write_bytes(data)
            for attempt in range(10):
                try:
                    tmp.replace(f)
                    break
                except PermissionError:
                    if attempt == 9:
                        raise
                    time.sleep(1)
        # Every part this parser writes has passed its checks: mark it for publishing.
        pub = f.with_suffix(".PUBLISH")
        if not pub.exists():
            pub.write_text("Parsed by parse_acts.py from the National Assembly's final adopted text; one version, as "
                           "published; acts cited by a later text or named as amended are held back.\n",
                           encoding="utf-8", newline="\n")
        written.append((f.name, len(p["acts"])))
    if 0 not in parts:  # no kept law is held now: a stale kept part would repeat acts written above
        for stale in (PARTS / "41-zakoni-kept.PUBLISH", PARTS / "41-zakoni-kept.json"):
            if stale.exists():
                stale.unlink()
    if a.report:
        Path(a.report).write_text("".join(json.dumps(h, ensure_ascii=False) + "\n" for h in holds), encoding="utf-8")
    reasons = defaultdict(int)
    for h in holds:
        reasons[h["reason"].split(":")[0]] += 1
    # State Gazette material pages: decrees, regulations and laws with no National Assembly text (50-dv-* parts).
    # A failure here leaves the law parts above as written and is reported, not hidden.
    try:
        dv = dv_publish(a, src, acts, dv_days, dv_cites_of, memo, contested, rejects, cited_by, titles_named)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        dv = {"dv_error": f"{type(e).__name__}: {e}"[:300]}
    if cache_path:
        tmp = cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(fresh, ensure_ascii=False), encoding="utf-8")
        tmp.replace(cache_path)
    print(json.dumps(dv, ensure_ascii=False))
    print(json.dumps({"laws_seen": len(laws), "published": sum(n for _, n in written), "held": len(holds),
                      "held_by_reason": dict(reasons), "kept_as_published": len(parts[0]["acts"]) if 0 in parts else 0,
                      "parts": written, "dv_issues_dated": len(dv_days)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
