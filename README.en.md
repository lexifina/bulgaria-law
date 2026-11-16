# Bulgaria: law history in git

**English** · **[Или прочетете на български](README.md)**

<picture>
<source media="(prefers-color-scheme: dark)" srcset="data/effort-dark.svg">
<img alt="Bulgarian law in this repository: what it holds, changes by the year they took effect, completeness against the official sources, and the correctness of what is held" src="data/effort-light.svg" width="880">
</picture>

The law of Bulgaria as a git history: one file per provision, one commit per version on the day it took effect, and the act that made each change as the commit's author. `git blame` names the act behind every provision; `git log` lists every change to an article; picking a date gives the text in force that day.

Part of [lexifina/global-law](https://github.com/lexifina/global-law), one git history for every country's law: this is Bulgaria's national law, which global-law reads at `bulgaria/national/acts/`.

**What is in it now:** the Constitution, with 4 versions from 2008; the 20 codes in `kodeks/` and, as Bulgaria has no civil code, its core civil-law acts in `zakon/` (each code's text is described under [What it does not show](#what-it-does-not-show)); and acts as published in the Държавен вестник (State Gazette) from 2003 to 2026: 2,782 laws, 7,538 Council of Ministers decrees, 6,168 ordinances, 967 rules, 471 instructions, 292 decisions, 63 presidential decrees and 9 other acts, 18,311 acts in all with the Constitution and the codes. Most acts have one version, their text as enacted; of the 17,368 acts of the first build listed in [`ACTS.md`](ACTS.md) with their status, 8,428 are amending acts. Case law: 54 decisions published in the State Gazette in 2026 (`caselaw/2026/`), 1,426 acts of the Върховен административен съд (Supreme Administrative Court, `caselaw/vas/`), and over 1.09 million entries from the public registers of acts of 171 courts, 2007 to 2022 (`caselaw/courts/`: the register's data with a link to the act's official file, not its text).

Each act is in `<kind>/<year>/dv<issue>-<material>/`, named by its State Gazette issue and material number (`kodeks/2011/dv009-10005/` is the Изборен кодекс, the Electoral Code, ДВ бр. 9/2011); the Constitution is in `konstitutsiya/`, one file per article (`art-091-01.md` is чл. 91а). `data/paths.json` maps each act id to its folder.

The text is in Bulgarian (Cyrillic), as the National Assembly and the State Gazette publish it. An English translation is not part of this record.

## Questions as git commands

| Question | Command |
| --- | --- |
| Every change to Article 129 of the Constitution | `git log -p --word-diff -- konstitutsiya/art-129.md` |
| Which act wrote each line of Article 129? | `git blame konstitutsiya/art-129.md` |
| Every version of the Constitution, with the day each took effect | `git log --format="%h %(trailers:key=In-force,valueonly,separator=) %an" --author=parliament.invalid -- konstitutsiya` |
| Article 129 as in force on 1 January 2020 | `python tools/on.py 2020-01-01 konstitutsiya 129` |

**Outside git**, we also host this record publicly, for free:

- **[Ask Claude about Bulgarian law](https://global-law.lexifina.com/v1/try_claude?country=bulgaria)**: opens Claude with a first question ready.
- **[Ask ChatGPT](https://global-law.lexifina.com/v1/try_chatgpt?country=bulgaria)**: the same question in ChatGPT.
- **[Search Bulgarian law on our site](https://lexifina.com/law?country=bulgaria&q=%D0%B3%D0%BE%D0%B4%D0%B8%D1%88%D0%B5%D0%BD+%D0%BE%D1%82%D0%BF%D1%83%D1%81%D0%BA)**: a search for "годишен отпуск", with each provision's text and its versions, no account needed.
- **[Developer REST API](https://global-law.lexifina.com/v1/search_law?query=%D0%B3%D0%BE%D0%B4%D0%B8%D1%88%D0%B5%D0%BD+%D0%BE%D1%82%D0%BF%D1%83%D1%81%D0%BA&jurisdiction=bulgaria)**: the same search as JSON, with no key. See the [documentation here](https://lexifina.com/api/global-law).

Both assistants read the record through the free Global law connector (MCP, `https://global-law.lexifina.com/mcp`); the first time, the chat gives you the link that adds it. Ask in Bulgarian or in English.

**Host it yourself easily.** All it takes is git and Python, and the tools run on your machine:

```sh
git clone --depth 1 https://github.com/lexifina/global-law && cd global-law
python3 tools/countries.py add bulgaria/national/acts
python3 tools/law.py show 2026-01-01 bulgaria/national/acts/konstitutsiya/art-129.md
```

Opened in Claude Code, Cursor, VS Code or Codex, the clone also starts a local MCP server with the same tools ([MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md)).

## Dates

Each commit is dated at noon, Europe/Sofia, on the day the version took effect, and carries it in its `In-force:` trailer:

- the day the act's own final provisions name; where they give some provisions a different day, the whole text is dated by its general day, and its commit says so;
- otherwise three days after the act's State Gazette day (Constitution, чл. 5, ал. 5; for Constitutional Court decisions, чл. 151, ал. 2), as the Gazette's own pages print that day;
- the Constitution's oldest version is dated 1 January 2008, when the last parts of the 2007 amendment took effect; its later versions take effect three days after ДВ бр. 100/2015, бр. 106/2023 and бр. 66/2024.

Each act is the author of its own commit (`zakon-2025-dv095-166613@parliament.invalid`). In the Constitution, a change is credited to the amending law or Constitutional Court decision only where the National Assembly's note on that provision names its Gazette issue; the oldest version and five edits no note explains are credited to the National Assembly as publisher.

## How it is checked

- Laws are the National Assembly's adopted final text (the Gazette's where its record has none), and other acts the State Gazette's official section as printed; the President's decree, signatures and editorial notes are cut, and only spacing, quotes and dashes are normalised.
- An act is published only when it reads cleanly (its provisions split with no gaps or repeats, its Gazette day and in-force day readable); the rest are held back, with the reason, in `data/held.json`.
- The Constitution's earlier texts come from Internet Archive captures of the National Assembly's page and go through the same parser as today's text, so a site redesign is not taken for a change of law.
- `tools/build/check_repo.py` reads every version back from git and compares it with the corpus, and the same corpus gives the same commit hashes; [`REPRODUCE.md`](REPRODUCE.md) records the corpus and builder hashes, and says these checks have not yet been run on the current build. There are no merge commits on `main`.
- [vulnerabilities/](vulnerabilities/README.en.md): possible drafting mistakes in Bulgarian law, found by global-law's detectors and checked by hand.

## What it does not show

- **Consolidated texts.** Apart from the Constitution and the consolidated codes and laws below, each act is its text as enacted: amendments are acts of their own, not merged into the acts they change. 2,039 acts are labelled "amended, not consolidated" and 161 "repealed, not consolidated" (`data/acts.json`).
- **The full history of the codes, and older law.** The codes are in `kodeks/` (20 folders). Current consolidated texts: the Наказателен кодекс (`kodeks/1968/dv026-nk/`) and the Кодекс на труда (`kodeks/1986/dv026-kt/`), the Ministry of Justice's texts to ДВ бр. 55/2026 and бр. 99/2026 (7 articles of the Labour Code differ between the two official copies checked); the Наказателно-процесуален кодекс, Граждански процесуален кодекс, Административнопроцесуален кодекс and Семеен кодекс, the Ministry of Justice's texts to ДВ бр. 59/2026, 92/2026, 17/2026 and 115/2025; the Данъчно-осигурителен процесуален кодекс, the National Revenue Agency's text to ДВ бр. 69/2026; the Кодекс за социално осигуряване (`kodeks/1999/dv110-65242/`), its 1999 text as enacted followed by the National Social Security Institute's text to ДВ бр. 68/2026; and the Кодекс на търговското корабоплаване (`kodeks/1970/dv055-ktk/`), the Maritime Administration's text to ДВ бр. 16/2026 (only one official copy). Each code that has a text as enacted keeps it as its first commit; the amending acts in between are not each built (some are, as their own commits). The Кодекс за застраховането of 2005 and the Изборен кодекс of 2014 are their text as enacted with some of their amending acts; the Кодекс на международното частно право, the Изборен кодекс of 2011 and the Кодекс за застраховането of 2015 are a single text as adopted (no readable current official copy was found); six international maritime codes (2021) are as published. Bulgaria has no civil code: its core civil law is in `zakon/`, as current consolidated texts: the Закон за задълженията и договорите (`zakon/1950/dv275-zzd/`), the Закон за лицата и семейството (`zakon/1949/dv182-zls/`) and the Закон за наследството (`zakon/1949/dv022-zn/`) from the Ministry of Justice, and the Закон за кадастъра и имотния регистър (`zakon/2000/dv034-zkir/`) from the Geodesy, Cartography and Cadastre Agency; the Закон за собствеността and the Търговски закон are not here yet (no official copy could be read). Every consolidated text was compared article by article with a second copy (lex.bg, a private publisher, where no second official copy exists), and its README lists any article that differs. The codes of 1968, 1970 and 1986 and the laws of 1949 and 1950 start at today's consolidated text: their original texts and their versions before 2003 are not online from an official source, and the amendments of 1989 to 2002 are not built. Apart from these codes and laws, the Constitution, the case law and some Council of Ministers decisions of 1989 (register data only), nothing older than the State Gazette of 2003 is here.
- **Every act of 2003 to 2026.** 4,674 acts in scope are held back because they do not read cleanly (`data/held.json`), and acts naming people (appointments, awards) are not taken. 21 acts published but not yet in force are listed in `data/pending.json` and appended on the day they take effect.
- **Annexes printed only in the Gazette's PDF**; the version's note says so.
- **The Constitution before 2008** (the 1991 text and the versions of 2003 to 2007), and the 2023 wording of 14 provisions the Constitutional Court ruled on in 2024: from 2023-12-25 to 2024-08-09 they read "[Източникът не дава текста, действащ на тази дата.]".
- **Most case law, local acts and EU law.** Case law is only what is listed above (nothing of the Върховен касационен съд, and the court registers give data on each act, not its text); the local acts are 58 documents of 14 institutions in `local/`.

## Sources

| Source | Kind | Past versions | Notes |
| --- | --- | --- | --- |
| [Народно събрание: приети закони](https://www.parliament.bg/bg/laws) | Laws as adopted (final text) | no: the text as adopted | 2,032 laws and 2 codes |
| [Държавен вестник](https://dv.parliament.bg/DVWeb/) | Official gazette, official section | no: each act as printed | 15,333 acts: decrees, ordinances, rules, instructions, and laws the National Assembly's record has no text for; the Gazette day of every issue; most acts and codes added since the first build |
| [Народно събрание: Конституция](https://www.parliament.bg/bg/const) | The consolidated Constitution | no: today's text only | A note on each changed paragraph names its Gazette issue |
| [Internet Archive](https://web.archive.org/) | Captures of parliament.bg/bg/const | yes, as captured | The Constitution's versions of 2008 and 2015 |
| [Министерство на правосъдието](https://mjs.bg) | Consolidated texts | no: today's text only | The Наказателен кодекс, Кодекс на труда, Наказателно-процесуален кодекс, Граждански процесуален кодекс, Административнопроцесуален кодекс and Семеен кодекс; the Закон за задълженията и договорите, Закон за лицата и семейството and Закон за наследството |
| [Национален осигурителен институт](https://nssi.bg) | Consolidated texts | no: today's text only | The Кодекс за социално осигуряване; a cross-check of the Кодекс на труда |
| [Изпълнителна агенция „Морска администрация“](https://www.marad.bg) | Consolidated text | no: today's text only | The Кодекс на търговското корабоплаване |
| [Национална агенция за приходите](https://nra.bg) | Consolidated text | no: today's text only | The Данъчно-осигурителен процесуален кодекс |
| [Агенция по геодезия, картография и кадастър](https://www.cadastre.bg) | Consolidated texts | no: today's text and the one before | The Закон за кадастъра и имотния регистър |
| [Върховен административен съд](https://sac.justice.bg) | Court acts | no | 1,426 acts |
| Courts' public registers of acts (`<court>.justice.bg`) | Register data on court acts | no | Over 1.09 million entries of 171 courts, without the acts' text |

## Licence

See [`LICENSE`](LICENSE). Official legal texts are not subject to copyright in Bulgaria (Закон за авторското право и сродните му права, чл. 4, т. 1), and Lexifina makes no claim to them. The history, commit messages, tables and tools are CC0 1.0.

No AI model wrote or changed legal text; the scripts were written by an AI model (see [`REPRODUCE.md`](REPRODUCE.md)).

## Visualisations

[visualisations/](visualisations/): Bulgarian law in 20 charts, drawn from this repository.

Including:

- How many laws each National Assembly passes, the legislative calendar and when the State Budget takes effect
- How laws are amended through other laws, the most-amended laws and codes, and the Constitution
- Government decrees, the State Gazette, EU law in Bulgarian laws, ratified treaties and the euro

## More

From [lexifina/global-law](https://github.com/lexifina/global-law):

- [FEATURES.md](https://github.com/lexifina/global-law/blob/main/FEATURES.md): every feature, and what every corpus must support (`git blame`, `law.py`, the MCP tools)
- [FAQ.md](https://github.com/lexifina/global-law/blob/main/FAQ.md): questions and answers · [CONTRIBUTING.md](https://github.com/lexifina/global-law/blob/main/CONTRIBUTING.md): proposing changes · [MCP.md](https://github.com/lexifina/global-law/blob/main/MCP.md): the MCP server · [REPRODUCE.md](https://github.com/lexifina/global-law/blob/main/REPRODUCE.md): how it was built · [CHANGELOG.md](https://github.com/lexifina/global-law/blob/main/CHANGELOG.md)
- [FRESHNESS.md](https://github.com/lexifina/global-law/blob/main/FRESHNESS.md): how current each corpus is · [Monitoring](https://github.com/lexifina/global-law/tree/main/monitoring): whether updates are running · [WATCHING.md](https://github.com/lexifina/global-law/blob/main/WATCHING.md): how each official source is watched for changes
- [performance/](https://github.com/lexifina/global-law/tree/main/performance): how fast the tools are, measured
- [visualisations/](https://github.com/lexifina/global-law/tree/main/visualisations): charts and bridges across the world's law
- [Vulnerabilities](https://github.com/lexifina/global-law/tree/main/vulnerabilities): mistakes in legislation as published
