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
| `config.json` | The categories in Bulgarian, the folders that are not law (`caselaw/`, `draft/`, `local/`, `data/`, `tools/`) and the chart's labels |

The model review needs `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` and `LLM_AUTH` set for an OpenAI-compatible Responses API.

Two changes were needed for this repository:

- `add_root.py` counts as law only commits whose `Kind` is missing or one of a few values. This repository marks Council of Ministers decrees, ordinances, rules and instructions `Kind: decree`, acts taken from the State Gazette `as-enacted`, the Constitutional Court's 2024 decision on the Constitution `court`, and the Constitution's oldest version and its unexplained changes of 2023 `publisher`, so these four were added to the list. The decisions of the Constitutional Court and the Supreme Administrative Court printed in the Gazette (`caselaw/2026/`) also carry `as-enacted` and so count as law in the history table; none of them raised a flag.
- global-law's `detectors/placeholder_ref.py` read every file of the repository into memory at once, about 350,000 here, and ran out of memory; it now reads them one at a time and keeps only the acts that have a repealed placeholder, with the same output. It found none: this repository keeps each act as enacted, so there are no placeholders to find.
