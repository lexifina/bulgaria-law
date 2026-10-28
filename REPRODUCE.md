# How this repository was made (Bulgaria)

This file is written by the build on 2026-10-28, the day the source data was retrieved. Everything below is enough to rebuild this repository hash for hash.

## Sources

| Source | Address | Retrieved | Requests | Licence |
| --- | --- | --- | ---: | --- |
| Народно събрание: Конституция на Република България (consolidated text, API) | <https://www.parliament.bg/api/v1/nav/bg/const> | 2026-10-28 | 1 | Official legal text; not subject to copyright (ЗАПСП чл. 4, т. 1) |

Every response is cached by the sha256 of its URL, and the table above lists every source with its retrieval date. Lexifina keeps its fetch scripts privately; `tools/parse.py` reads only the cache and writes `corpus.json`, so the same cache always gives the same corpus.

## What is in it

| Act | Title | Versions | Span |
| --- | --- | ---: | --- |
| `konstitutsiya` | Конституция на Република България | 1 | 2024-08-09 to 2024-08-09 |

The build made 1 commits:

| Commits | Kind |
| ---: | --- |
| 1 | first version of an act |
| 0 | one law on its in-force day |
| 0 | changes no amendment note explains, credited to the publisher |

Other counts:
- 0 commits on the branch `badeshte`: laws not yet in force on 2026-10-28.
- 0 commits dated 1 January 1970: in force before 1970, with the real day in their `In-force` trailer.
- 9 laws in the record.
- 1 tags.

## Dates

Each commit is dated at noon (Europe/Sofia) on the day the change took effect. The other dates, enacted and published, are trailers.

When a law gives no date of its own, the default rule applies: Конституция, чл. 5, ал. 5: нормативните актове влизат в сила три дни след обнародването им в Държавен вестник, освен когато в тях е определен друг срок; чл. 151, ал. 2: решенията на Конституционния съд влизат в сила три дни след обнародването им. https://www.parliament.bg/api/v1/nav/bg/const

## Commands, in order

```sh
# fill the cache from the sources listed above (network; Lexifina's fetch scripts are kept privately)
python -X utf8 tools/parse.py                  # cache -> corpus.json (no network)
python -X utf8 tools/build.py <folder> --repo <empty folder> --docs-date 2026-10-28
python -X utf8 tools/check_repo.py <repo> --corpus <folder>/corpus.json --write
python -X utf8 tools/build.py <folder> --repo <another empty folder> --docs-date 2026-10-28 --compare <repo>
```

In the main Lexifina repository these files live as follows:
- `fetch.py`, `parse.py` and `repo/`: in `scripts/bulgaria-law/`.
- `build.py`, `check_repo.py` (`check.py` there) and `on.py`: in `scripts/gitlaw_common/`, with the corpus format in `SCHEMA.md`.

## Exact inputs

- `corpus.json` sha256 `295b64feb01c3680c81ce7c33d02bfafece10f8bd469023c99b55f19bcd8eaf1` (173613 bytes)
- Script blob hashes (`git hash-object`):

| Script | Blob |
| --- | --- |
| build.py | `2bfc4ac9df193a7be844556d7f69cdb9d93ec3f2` |
| check.py | `cd346c7ff9996d450240e3bab52bcae03b2bc865` |
| on.py | `644a6c0857fbcc72562032b58d57aa113fee0641` |
| fetch.py | `f838a6f82f07cc89f6b3bc561c9bad996e8fb5ff` |
| parse.py | `052497d5562f5695c1011f1ab846b7c1d288684e` |

- Tools:
  - Python 3.14.0
  - git version 2.52.0.windows.1
  - curl 8.21.0 (Windows) libcurl/8.21.0 Schannel zlib/1.3.2 WinIDN WinLDAP

## Checks

1 versions of 1 acts read back from git on the day each took effect and on the day before: 0 mismatches. Trailers: 0 commits whose trailers git cannot parse. Health: 0 merge commits on main, 0 commit dates that go backwards, 0 commits dated after the build.

Not yet run for this build.

These results are from the check run on the build before this one, from the same corpus.

## Decisions made by hand

- Constitution: built from the National Assembly's consolidated text (parliament.bg API), the only free official consolidation found; lex.bg is a private service whose robots.txt disallows all but search engines, so it was not fetched.
- Constitution: one version only, credited to the publisher as the oldest version available; dated 2024-08-09, the in-force day of its last listed change (КС Решение № 13/2024, ДВ бр. 66 от 06.08.2024, + 3 days under чл. 151, ал. 2).
- Earlier versions (1991, 2003, 2005, 2006, 2007, 2015, 2023) are not built: archive.org was offline at fetch time and dv.parliament.bg refused connections from this machine.
- Inline amendment notes such as '(Нова - ДВ, бр. 18 от 2005 г.)' are kept in the text as the source prints them.
- Chapter and section headings are their own units, keyed just before the first article they precede.

## What AI did and did not do

The fetch, parse and check scripts were written by Claude Code running Claude Opus 5.5 (`claude-opus-5-5`) under Lexifina's direction.

No model wrote, translated or corrected legal text. No model runs at build time. Every word of law in this repository comes from the official sources above, through code that anyone can rerun.

The commit messages are written by `build.py` from the source data.

Model use at data-build time:
- none: parse.py is deterministic code; no model output is used as text or data.
