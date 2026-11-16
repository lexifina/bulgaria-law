# Tools

The scripts behind this Bulgaria-only run of global-law's vulnerability detectors. They run inside a copy of
[global-law/vulnerabilities/scripts](https://github.com/lexifina/global-law/tree/main/vulnerabilities/scripts) (Python 3.11+,
`pip install duckdb pyarrow`), with a bare clone of this repository at `sources/corpus/bulgaria-law.git`, a blobless bare
clone of global-law at `sources/global-law.git`, and a `pins.json` that names only bulgaria-law and its commit.

| Script | What it does |
| --- | --- |
| `run.sh` | Indexes the history and texts, adds Bulgaria's history rows, and runs the detectors |
| `add_root.py` | Builds Bulgaria's history rows from this repository's own commits, so the history detectors read every change |
| `run_triage.sh` | The model review: the 40 strongest flags per category, the 40 strongest lapsed time limits in law texts, and the empty periods (none here); run as `bash run_triage.sh '^(caselaw\|draft\|local\|data\|tools)/'` |
| `late_ext_select.py` | Chooses the empty periods for global-law's review of that category |
| `late_ext_rebut.py` | Adds the second, arguing-against pass to the empty-period review, as `triage.py` does for the other categories |
| `build_vulns.py` | Builds `data/flags.csv`, `data/reviewed.csv` and `data/by_category.csv` from the findings and the model review |
| `flags_chart.py` | Draws the chart at the top of the READMEs, in Bulgarian and English, light and dark |
| `patch_detectors.py` | Fixes blind spots found in runs on several country repositories in the copy of global-law's scripts (`python -X utf8 patch_detectors.py <scripts dir>`; a fix already in place is skipped) |
| `redo.py` | Runs `patch_detectors.py`, then again only the scans and detectors the fixes change, the model review of lapsed time limits, references to deleted provisions and empty periods, and the build (`python -X utf8 redo.py <run folder>`; `--keep-reviews` keeps every review already made and reviews only new strong flags; `EMBED_FONTS` names the script that embeds the chart's fonts) |
| `map_moved.py` | Run after `ingest/extract.py`: in a repository that moved its act folders (`data/paths.json`), names every file by its folder since the move, so each act keeps one history (here no path needed it) |
| `patch_detectors_vi.py`, `patch_es.py` | Later rounds of detector fixes found in the Vietnamese and Spanish runs (Vietnamese dates and references; Spanish dates, "marco" and "escudo"); they change nothing here |
| `patch_build_r7.py` | Fixes to `build_vulns.py`: reviews matched on 400 characters of context, links to files deleted before a folder move, and each retroactive date linked to the first file of its act |
| `config.json` | The categories in Bulgarian, the folders that are not law (`caselaw/`, `draft/`, `local/`, `data/`, `tools/`) and the chart's labels |

The model review needs `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and `LLM_AUTH` set for an OpenAI-compatible Responses API.

Two changes were needed for this repository:

- `add_root.py` counts as law only commits whose `Kind` is missing or one of a few values. This repository marks Council of Ministers decrees, ordinances, rules and instructions `Kind: decree`, acts taken from the State Gazette `as-enacted`, the Constitutional Court's 2024 decision on the Constitution `court`, and the Constitution's oldest version and its unexplained changes of 2023 `publisher`, so these four were added to the list. The decisions of the Constitutional Court and the Supreme Administrative Court printed in the Gazette (`caselaw/2026/`) also carry `as-enacted` and so count as law in the history table; none of them raised a flag.
- global-law's `detectors/placeholder_ref.py` read every file of the repository into memory at once, about 350,000 here, and ran out of memory; it now reads them one at a time and keeps only the acts that have a repealed placeholder, with the same output. It found none: this repository keeps each act as enacted, so there are no placeholders to find.
- The run was then repeated with `redo.py`. Of `patch_detectors.py`'s fixes, these change this repository's flags: lapsed time limits now read Bulgarian month names ("до 31 декември 2020 г.") and "до края на 2020 г." (355 flags became 4,340), and in the second round, with `--keep-reviews`, "не по-късно от" and "изтича на" before a date and months in Roman numerals ("31.XII.2005 г.") (4,871); every earlier flag is still among them. A later round made the sharded scans split the acts by a stable checksum (Python's `hash()` differs per process, so some acts were read twice and others not at all) and breaks ties in score the same way on every run; the flags did not change, and a further `--keep-reviews` pass reviewed 40 more lapsed time limits tied on score. "DM" counts as a currency only in capitals and "franco" only as a whole word, which removed the 4 false matches, "2 dm" (decimetres) and "Francoa ramosa" (dead currencies went from 4 to 0).
