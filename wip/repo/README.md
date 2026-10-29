# Bulgaria: law history in git

The law of Bulgaria as a git history: one file per provision, one commit per law on the day it took effect, and the law that made each change as the commit's author. `git blame` names the law behind every paragraph; `git log` lists every change to an article; the tool below gives the text in force on any day.

It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places it at `bg/`.

*На български: [по-долу](#на-български).*

**What is in it now: one act, four versions, 1 January 2008 to today.** The Constitution as the National Assembly publishes it: today's text from parliament.bg, and two earlier texts from the Internet Archive's copies of the National Assembly's old Constitution page (2010 to 2021). The record starts on 1 January 2008, with the oldest text the archive holds; the 1991 text and the versions of 2003 to 2007 are not in it.

| Folder | Act | Versions | History |
| --- | --- | ---: | --- |
| `konstitutsiya/` | Конституция на Република България (Constitution of the Republic of Bulgaria, 1991) | 4 | 2008-01-01 to today: the oldest version available, then the amendment of 2015, the amendment of 2023 and Constitutional Court Decision № 13 of 2024 |

| In force from | Text | Commits (author) | Source |
| --- | --- | --- | --- |
| 2008-01-01 | The text after the amendments of 2003, 2005, 2006 and 2007 and Decision № 7 of 2006 | Oldest version available (the publisher); its message names the six earlier gazette events | Internet Archive capture of parliament.bg/bg/const, 22 December 2010 |
| 2015-12-21 | ЗИД, ДВ бр. 100 от 18.12.2015: 10 provisions, every one marked "ДВ, бр. 100 от 2015 г." | `dv-2015-100` | Capture of 25 January 2016 |
| 2023-12-25 | ЗИД, ДВ бр. 106 от 22.12.2023: 8 provisions. 14 more provisions read "[Източникът не дава текста, действащ на тази дата.]" (see below), and 5 publisher's edits that no note explains | `dv-2023-106`; the publisher, "unexplained" | Today's text (parliament.bg API) |
| 2024-08-09 | Решение № 13 на КС, ДВ бр. 66 от 06.08.2024: 14 provisions | `dv-2024-66` | Today's text (parliament.bg API) |

The files are `konstitutsiya/art-NNN.md` for each article (a lettered article takes a number: `art-091-01.md` is чл. 91а, `art-091-02.md` чл. 91б, `art-130-01.md` to `art-130-03.md` чл. 130а to 130в, `art-132-01.md` чл. 132а); `preambyl.md` is the preamble; `art-NNN-0-heading-1.md` is the heading of the chapter that begins at that article (Глава първа to Глава десета); `prehodni-01.md` is the Constitution's own Преходни и заключителни разпоредби, and `prehodni-02.md` to `prehodni-06.md` are the transitional provisions of the amending laws of 2003, 2005, 2007, 2015 and 2023, as the National Assembly prints them after the Constitution. 192 files in all: articles 1 to 169, the six lettered articles, the preamble, ten chapter headings and six transitional sections. `konstitutsiya/README.md` lists them.

**The nine gazette events behind today's text.** The National Assembly's text opens with the list of every promulgation and change in the Държавен вестник (State Gazette). The first six came before the oldest version here and are named in its commit; the last three each have commits of their own:

| Key | State Gazette | What it is |
| --- | --- | --- |
| `dv-1991-56` | ДВ бр. 56 от 13.07.1991 | The Constitution, promulgated and in force from 13 July 1991 |
| `dv-2003-85` | ДВ бр. 85 от 26.09.2003 | Закон за изменение и допълнение (ЗИД) на Конституцията |
| `dv-2005-18` | ДВ бр. 18 от 25.02.2005 | ЗИД на Конституцията |
| `dv-2006-27` | ДВ бр. 27 от 31.03.2006 | ЗИД на Конституцията |
| `dv-2006-78` | ДВ бр. 78 от 26.09.2006 | Решение № 7 на Конституционния съд от 2006 г. (Constitutional Court decision) |
| `dv-2007-12` | ДВ бр. 12 от 06.02.2007 | ЗИД на Конституцията |
| `dv-2015-100` | ДВ бр. 100 от 18.12.2015 | ЗИД на Конституцията |
| `dv-2023-106` | ДВ бр. 106 от 22.12.2023 | ЗИД на Конституцията |
| `dv-2024-66` | ДВ бр. 66 от 06.08.2024 | Решение № 13 на Конституционния съд от 2024 г. |

Inside the text, the National Assembly marks each changed paragraph with a note naming the gazette issue: "(Нов - ДВ, бр. 27 от 2006 г.)" on чл. 91а, "(Нова - ДВ, бр. 18 от 2005 г.)" on a paragraph of чл. 4, "(Изм. - ДВ, бр. 85 от 2003 г., изм. - ДВ, бр. 12 от 2007 г., отм. - ДВ, бр. 100 от 2015 г.)" on чл. 131. These notes are kept in the text exactly as printed, so `git grep` finds every provision a given law touched (see below). They are the data the history is credited from: a changed provision is credited to an event only where its own note names that event's gazette issue.

## A lawyer's questions as git commands

| Question | Command |
| --- | --- |
| What does чл. 5 say today? | `python tools/on.py 2026-10-29 konstitutsiya 5` |
| A lettered article (чл. 91а) | `python tools/on.py 2026-10-29 konstitutsiya art-091-01` |
| The same, naming where the text comes from | `python tools/on.py --law 2026-10-28 konstitutsiya art-091-01` |
| The same, with raw git | `git show main:konstitutsiya/art-091-01.md` |
| The whole Constitution today | `python tools/on.py 2026-10-29 konstitutsiya` |
| Which provisions does the source say the 2023 amendment touched? | `git grep -l "бр. 106 от 2023" -- konstitutsiya/` |
| Every amendment note on чл. 129, as printed | `git grep -n "ДВ, бр" -- konstitutsiya/art-129.md` |
| The text on 1 January 2020 | `python tools/on.py 2020-01-01 konstitutsiya` |
| Чл. 130а before and after the 2015 amendment | `git diff konstitutsiya/2008-01-01 konstitutsiya/2015-12-21 -- konstitutsiya/art-130-01.md` |
| Which law last changed each line of чл. 129? | `git blame konstitutsiya/art-129.md` |
| Every change to чл. 84 | `git log -p -- konstitutsiya/art-084.md` |
| What the 2015 amendment changed | `git show law/dv-2015-100` (tags `law/<key>`; versions are tagged `konstitutsiya/<in-force day>`) |
| The six earlier events named for the oldest version | `git log -1 --format=%B konstitutsiya/2008-01-01` |
| Changes no note explains | `git log --author=ns@parliament.invalid` |
| Laws passed but not yet in force | `git log main..badeshte` (none today; the branch does not exist yet) |

After a rebuild, refresh tags with `git fetch --force --tags`: a plain fetch keeps stale tags.

## Dates

- Each commit is dated at **noon, Europe/Sofia, on the day the change took effect**. The in-force day is also in the `In-force:` trailer, which the tools read.
- **Default rule.** Constitution, чл. 5, ал. 5: normative acts enter into force three days after their promulgation in the State Gazette, unless they set another date. Чл. 151, ал. 2: decisions of the Constitutional Court enter into force three days after their promulgation.
- **2015-12-21, 2023-12-25 and 2024-08-09** are the gazette dates of ДВ бр. 100/2015, бр. 106/2023 and бр. 66/2024 plus three days; none of the three sets a day of its own.
- **The oldest version is dated 1 January 2008.** Its text holds the amendments up to ДВ бр. 12/2007, and parts of those took effect on days of their own, as the text prints them: § 7 of the 2003 law put § 1, т. 3 in force on 1 January 2004; § 7 of the 2005 law put чл. 22 in force with the EU Accession Treaty (the note: "в сила от 01.01.2007 г."); § 13 of the 2007 law put its §§ 1 and 2 (чл. 9 and 59) in force on 1 January 2008. The text was therefore whole from 1 January 2008, and nothing changed it again until 2015.
- **The archive's copy lags.** The National Assembly's page still showed the 2007 text on 16 January 2016 and the 2015 text from 25 January 2016. Versions are dated by the law, not by the capture.

## How it is checked

- **Today's text is the official text.** `tools/parse.py` reads the National Assembly's consolidated Constitution (one JSON response from parliament.bg, whose sha256 is recorded with the version) and splits it into provisions, with no other change than normalised spacing, quotes and dashes. Articles 1 to 169 are all present, plus 91а, 91б, 130а, 130б, 130в and 132а. The Internet Archive's copy of the same API response from 20 August 2025 is byte-identical.
- **One parser for every source.** The old page (2010 to May 2021) and today's API go through the same code, so a redesign of the site is not taken for a change of law. The test: the old page captured on 6 May 2021 and the API captured on 29 June 2021, after the redesign, give identical provisions.
- **One copy per distinct text.** `tools/fetch.py --history` read 46 of the 314 captures of the old page (the first of every quarter, then bisection wherever two neighbours differed) and parsed each one. Every capture from 22 December 2010 to 16 January 2016 gives the first text, every one from 25 January 2016 to 6 May 2021 the second. The two pinned captures are recorded with their sha256 in each version.
- **Every change is accounted for.** All 10 changes of 2015, 8 of 2023 and 14 of 2024 carry a note naming their gazette issue. Five small edits by the publisher carry none and are committed as unexplained (below).
- Each version is read back from git on the day it took effect and on the day before (`tools/check_repo.py`), and must match `corpus.json`: 0 mismatches. No merge commits on `main`, commit dates never go backwards, nothing is dated in the future, and every commit's trailers parse.
- The repository is rebuilt from the same data a second time and gives identical hashes. Details in [`REPRODUCE.md`](REPRODUCE.md).

## What "author" means

The author of a commit is the law that made the change, with an e-mail address that cannot exist, so `git blame` and `git log --author` name laws. The committer is always Lexifina.

- **The law commits** are authored by `dv-2015-100`, `dv-2023-106` and `dv-2024-66` (`<key>@parliament.invalid`), one commit per event on its in-force day.
- **The publisher's commits.** The first commit is authored by the Народно събрание на Република България (`ns@parliament.invalid`) and labelled "oldest version available"; its message names the six earlier gazette events without crediting any line to one of them. The publisher also authors the one "unexplained" commit, on 2023-12-25: the 14 provisions that read the placeholder that day, and five edits that no note explains (чл. 9 and 59: "в сила от 1 януари 2008 г." became "01.01.2008 г."; чл. 85, т. 8: a full stop became a semicolon; чл. 91а: its note joined to ал. 1; чл. 158, т. 5: "гл." became "глава"). The publisher made those edits between 29 June 2021 and 20 August 2025; they sit with the first version built from today's text.
- **Credits come only from the source.** A change is credited to a law only where the National Assembly's note on that provision names it.

## What it does not show

- **Anything before 1 January 2008.** The Internet Archive's oldest capture of the page is from 22 December 2010, so the 1991 text and the versions of 2003, 2005, 2006 and 2007 are not built. dv.parliament.bg (the State Gazette) refused connections from this machine, and the record does not rebuild old wording from the amending laws.
- **The full text between 25 December 2023 and 8 August 2024.** No copy of the text in force then was found: the old page stops in May 2021, and the Internet Archive caught the API only on 29 June 2021 and 20 August 2025 (Common Crawl's index could not be reached). So the version of 2023-12-25 is today's text, except that the 14 provisions whose notes name Decision № 13 of 2024 (чл. 23, 84, 91б, 99, 110, 126, 129, 130, 130а, 130б, 130в, 132а, 133 and 150) read "[Източникът не дава текста, действащ на тази дата.]" ("the source does not give the text in force on this date"). Their wording arrives on 2024-08-09, credited to the decision. The 2023 amendment's own words in those provisions are therefore not in the record.
- **The Penal Code (Наказателен кодекс) and the data protection law (Закон за защита на личните данни).** Neither is built. The candidate sources, cpdp.bg (the Commission for Personal Data Protection) for the data protection law and the parliament.bg routes for adopted laws (`/act/<id>`, `/bill/<id>`), have not been probed yet.
- **Other acts.** Only the Constitution is here.
- **The words of repealed or struck-down provisions.** Where a provision was repealed or the Constitutional Court declared it unconstitutional, the file holds what the National Assembly prints. `art-131.md` holds the note alone, "(Изм. - ДВ, бр. 85 от 2003 г., изм. - ДВ, бр. 12 от 2007 г., отм. - ДВ, бр. 100 от 2015 г.)"; `art-091-02.md` (чл. 91б) holds its note "(Нов - ДВ, бр. 106 от 2023 г.; обявен за противоконституционен с РКС № 13 от 2024 г. - ДВ, бр. 66 от 2024 г.)" and then the struck-down words between two rules of dashes, as the National Assembly prints them.
- **Notes in the text.** Because the amendment notes are kept, the text is the National Assembly's edition, not the bare words of the law. The notes are not separate units.

Only the text published by the National Assembly and the State Gazette is authoritative. This repository is a research aid, not legal advice.

## How it is built

`tools/fetch.py` downloads the source once with curl into a cache named by the sha256 of the URL; today's text took one request. `tools/fetch.py --history` reads the Internet Archive's raw (`id_`) captures through the shared client `gitlaw_common/wayback.py`, which keeps one polite rate for the whole machine and caches every response (52 requests). `tools/parse.py` reads only that cache and writes `corpus.json`; it also takes the nine law keys from the text's own header. The shared builder `tools/build.py` writes this repository from it. The same cache gives the same bytes and the same commit hashes. A model (Claude) wrote the scripts; it wrote no legal text. No model runs when the history is built.

## Sources

| Source | What it gives | Dated versions | Names the amending act | Access and terms | Used |
| --- | --- | --- | --- | --- | --- |
| [Народно събрание, Конституция](https://www.parliament.bg/bg/const) (API: `https://www.parliament.bg/api/v1/nav/bg/const`) | The official consolidated Constitution | No: today's text only | Yes, a note on each changed paragraph, and the full list of gazette events in the header | JSON with an HTML body. Official legal text, not subject to copyright (Закон за авторското право и сродните му права, чл. 4, т. 1) | Yes: today's text |
| [Държавен вестник](https://dv.parliament.bg) | The State Gazette: laws as promulgated | No consolidated texts | Partly | PDF. Refused connections (ports 80 and 443) from this machine | No |
| [lex.bg](https://lex.bg) | Consolidated texts (private, not official) | | | robots.txt disallows every reader but search engines | No: not fetched |
| [Internet Archive](https://web.archive.org/) | Captures of parliament.bg/bg/const: the full text on the old page from December 2010 to May 2021, the JavaScript shell after that; the API response on 29 June 2021 and 20 August 2025 | Yes, as captured | As the captures print it | Raw `id_` captures; the pages are the National Assembly's official text | Yes: the 2008 and 2015 versions (captures 20101222212318 and 20160125101631) |
| [Common Crawl](https://commoncrawl.org/) | Another web archive | | | Its index could not be reached from this machine on 2026-10-29 | No |

The register this repository started from said that consolidated texts of Bulgarian law exist only in private services. For the Constitution that is not so: the National Assembly publishes it consolidated, with its amendment notes.

Research guides that cover every country: [GlobaLex](https://www.nyulawglobal.org/globalex/) and the [Law Library of Congress Guide to Law Online](https://www.loc.gov/research-centers/law-library-of-congress/researcher-resources/guide-to-law-online/).

## Licence

See [LICENSE](LICENSE). The text of the Constitution is the official text published by the National Assembly of the Republic of Bulgaria (parliament.bg). Official legal texts are not subject to copyright in Bulgaria (Закон за авторското право и сродните му права, чл. 4, т. 1), and Lexifina makes no claim to it. The history, commit messages, tables and tools are released under [CC0 1.0](LICENSE).

---

## На български

Конституцията на Република България като история в git: по един файл за всеки член и по един commit за всеки закон на деня, в който е влязъл в сила, с този закон като автор.

- **Какво съдържа:** четири редакции на Конституцията, от 1 януари 2008 г. до днес, всички в текста на Народното събрание. Най-старата налична версия (в сила от 1 януари 2008 г., когато влизат в сила §§ 1 и 2 от ЗИД, ДВ, бр. 12/2007) е от копие на страницата parliament.bg/bg/const в Internet Archive от 22.12.2010 г. и е записана от името на издателя; съобщението на commit-а изброява шестте по-ранни обнародвания и изменения (ДВ, бр. 56/1991, бр. 85/2003, бр. 18/2005, бр. 27/2006, бр. 78/2006 - Решение № 7 на КС, бр. 12/2007). Следват ЗИД, ДВ, бр. 100/2015 (в сила от 21.12.2015 г., копие от 25.01.2016 г.), ЗИД, ДВ, бр. 106/2023 (в сила от 25.12.2023 г.) и Решение № 13 на КС, ДВ, бр. 66/2024 (в сила от 09.08.2024 г.), по актуалния текст. Всяка промяна е приписана на акта, който бележката към разпоредбата посочва.
- **Редакцията от 25.12.2023 г.:** не е намерено копие на текста, действащ между 25.12.2023 г. и 08.08.2024 г. 14-те разпоредби, чиито бележки посочват Решение № 13 на КС от 2024 г., гласят в нея „[Източникът не дава текста, действащ на тази дата.]“. Пет редакционни промени на издателя без бележка (чл. 9, 59, 85, 91а и 158) са отбелязани като необяснени.
- **Бележките за измененията** („Нов - ДВ, бр. 27 от 2006 г.“ и др.) са запазени в текста така, както са отпечатани.
- **Какво липсва:** редакциите отпреди 2008 г. (най-старото копие в архива е от 2010 г.), Наказателният кодекс и Законът за защита на личните данни.
- **Дати:** нормативните актове влизат в сила три дни след обнародването им в „Държавен вестник“, освен ако в тях е определен друг срок (чл. 5, ал. 5); решенията на Конституционния съд също влизат в сила три дни след обнародването им (чл. 151, ал. 2).

Официален е само текстът, публикуван от Народното събрание и в „Държавен вестник“. Това хранилище не е правен съвет.
