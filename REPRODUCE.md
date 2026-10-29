# How this repository was made (Bulgaria)

This file is written by the build on 2026-10-29, the day the source data was retrieved.

## Sources

| Source | Address | Retrieved | Licence |
| --- | --- | --- | --- |
| Народно събрание: Конституция на Република България (consolidated text, API) | <https://www.parliament.bg/api/v1/nav/bg/const> | 2026-10-29 | Official legal text; not subject to copyright (ЗАПСП чл. 4, т. 1) |
| Internet Archive (Wayback Machine): captures of parliament.bg/bg/const | <https://web.archive.org/web/*/parliament.bg/bg/const*> | 2026-10-29 | The captured pages are the National Assembly's official text (not subject to copyright, ЗАПСП чл. 4, т. 1). |

Every word of law in this repository comes from these sources. Lexifina reads them and records each act's dated versions, and the laws that made each change, in one corpus file. This repository is built from that file.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `konstitutsiya` | Конституция на Република България | 4 | 2008-01-01 to 2024-08-09 |

The build made 5 commits:

| Commits | Kind |
| ---: | --- |
| 1 | first version of an act |
| 3 | one law on its in-force day |
| 1 | changes no amendment note explains, credited to the publisher |

Other counts:
- 0 commits on the branch `badeshte`: laws not yet in force on 2026-10-29.
- 0 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 9 laws in the record.
- 7 tags.

## Dates

Each commit is dated at noon (Europe/Sofia) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: Конституция, чл. 5, ал. 5: нормативните актове влизат в сила три дни след обнародването им в Държавен вестник, освен когато в тях е определен друг срок; чл. 151, ал. 2: решенията на Конституционния съд влизат в сила три дни след обнародването им. https://www.parliament.bg/api/v1/nav/bg/const

## How the history is built

`tools/build.py` turns the corpus into this history in one pass: one commit per law, on the day it took effect. The same corpus always gives the same commit hashes. `tools/check_repo.py` reads every version back from git and compares it with the corpus. `tools/on.py` shows the law as it stood on any date. The corpus format is described in `tools/SCHEMA.md`.

- Corpus: sha256 `7fc2e0ee790874cd8728d5249d98deb0323b6ee53d7d90d3e367b18c94e41715` (624309 bytes).
- Builder blob hashes (`git hash-object`): `build.py` `a4faa25af85facb64b956b372f6b528aafdd7ec1`, `check.py` `3d00541d258745461ab52b1b0cb4e1716a27a95d`, `on.py` `644a6c0857fbcc72562032b58d57aa113fee0641`.
- Python 3.12.10; git version 2.46.0.windows.1.

## Checks

4 versions of 1 acts read back from git on the day each took effect and on the day before: 0 mismatches. Trailers: 0 commits whose trailers git cannot parse. Health: 0 merge commits on main, 0 commit dates that go backwards, 0 commits dated after the build.

No second build of this corpus has been compared yet.

## Decisions made by hand

- Constitution: built from the National Assembly's own consolidated text: today's from parliament.bg, earlier ones from Internet Archive captures of the old parliament.bg/bg/const page (2010 to May 2021), one capture per distinct text. lex.bg is a private service, so it was not used.
- Every source is read the same way, so a site redesign that changes no words gives identical provisions.
- No capture is older than 2010-12-22, so the 1991 text and the versions of 2003-2007 are not built: the oldest version is credited to the publisher as the oldest version available and names the earlier events.
- In-force days: promulgation in the Държавен вестник + 3 days (Constitution чл. 5, ал. 5; for Constitutional Court decisions чл. 151, ал. 2), unless the event sets its own day: dv-1991-56: 1991-07-13 (the header: "в сила от 13.07.1991 г."; § 9 of the Constitution: in force from the day of its promulgation); dv-2003-85: 2004-01-01 (§ 7 of the 2003 law: "Параграф 1, т. 3 влиза в сила от 1 януари 2004 г." (the note on чл. 129: "в сила от 01.01.2004 г.")); dv-2005-18: 2007-01-01 (§ 7 of the 2005 law: § 2 in force from the entry into force of the EU Accession Treaty (the note on чл. 22: "в сила от 01.01.2007 г.")); dv-2007-12: 2008-01-01 (§ 13 of the 2007 law: "Параграфи 1 и 2 влизат в сила от 1 януари 2008 г." (the notes on чл. 9 and чл. 59: "в сила от 01.01.2008 г.")).
- A version holding an event with later-starting parts is dated by the last of those days (the oldest version: 2008-01-01, ДВ бр. 12/2007 § 13).
- Credits: a changed provision is credited to a new event only where its own amendment note names that event's gazette issue ("бр. N от YYYY"); any other change is committed by the publisher as unexplained.
- The Internet Archive holds no copy of the text between the 2023 amendment (ДВ бр. 106/2023, in force 2023-12-25) and Constitutional Court Decision № 13/2024 (ДВ бр. 66/2024, in force 2024-08-09): the old page ends in May 2021 and the current page was captured only on 2021-06-29 and 2025-08-20. The 2023-12-25 version is today's text with the text-before-its-law rule applied to the provisions whose notes name the 2024 decision.
- Five provisions differ between the 2016-2021 text and today's in ways no note explains (чл. 9 and 59: "в сила от 1 януари 2008 г." now "01.01.2008 г."; чл. 85, т. 8: "." now ";"; чл. 91а: the note joined to ал. 1; чл. 158, т. 5: "гл." now "глава"). The publisher made them after 2021-06-29 (the API captured then still has the old wording) and by 2025-08-20; they are committed as unexplained in the version of 2023-12-25, the first version built from today's text.
- The source types the dash in some amendment notes as a stray control character (U+001F in the current text, U+00AD in the old page: чл. 22, 25, 150); it is read as "-".
- Inline amendment notes such as '(Нова - ДВ, бр. 18 от 2005 г.)' are kept in the text as the source prints them.
- Chapter and section headings are their own units, keyed just before the first article they precede.
- Text before its law: in the version of 2023-12-25, art-023 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-084 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-091-02 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-099 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-110 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-126 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-129 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-130 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-130-01 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-130-02 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-130-03 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-132-01 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-133 reads the placeholder (its note names a later event); its wording arrives with that event.
- Text before its law: in the version of 2023-12-25, art-150 reads the placeholder (its note names a later event); its wording arrives with that event.

## What AI did and did not do

The scripts that read the sources and build this repository were written by Claude Code running Claude Opus 5.5 (`claude-opus-5-5`) under Lexifina's direction.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- none: the text is parsed by deterministic code; no model output is used as text or data.
