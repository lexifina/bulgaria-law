# Bulgarian law in 20 charts

[Български](README.md)

Charts on every country's law, from the whole of global-law: [global-law visualisations/](https://github.com/lexifina/global-law/tree/main/visualisations). These are the charts on Bulgaria alone.

Twenty charts on Bulgarian law, drawn only from the data in this repository: the acts of the official section of the State Gazette (Държавен вестник) from 2003 to 2026 (laws, Council of Ministers decrees, ordinances, rules and instructions), the record of adopted laws with their dates, the citations in the texts of laws that list every amendment of the law they amend, and the Constitution in its versions since 2008.

Open [`balgarskoto-pravo-v-20-grafiki.html`](balgarskoto-pravo-v-20-grafiki.html) in a browser. The page is one file with all its data inside; it loads only the d3 and topojson libraries, the world map of chart 19 and its fonts from the web. The controls at the top right switch the language (Bulgarian or English) and the theme (light or dark). Each chart names its data path in the repository, its record count and its limits, and has a table of every number under it. Hover over a mark for the exact values.

The charts are descriptive: they show what the sources record, not why.

## The charts

### I. The National Assembly

#### 1. National Assemblies

Every National Assembly since 2001 and the laws it adopted: seven assemblies in 2021–2024, five of which lasted less than a year.

![National Assemblies](stills/en/01.png)

#### 2. The legislative calendar

Laws by the month and year they were adopted: 13% in July, 2% in August.

![The legislative calendar](stills/en/02.png)

#### 3. What the assemblies pass

Amending laws, ratifications, new laws and budget laws by assembly: amending laws went from 53% in the 40th to 73% in the 49th.

![What the assemblies pass](stills/en/03.png)

#### 4. The State Budget

When each State Budget Act was published and took effect: for 2023 and 2026, 215 and 214 days after 1 January.

![The State Budget](stills/en/04.png)

### II. How laws are amended

#### 5. Amendments made in another law

An amendment by a law titled as amending that same law, or in the provisions of another law: 78% of 7,873 amendments in 2004–2026 were made in another law.

![Amendments made in another law](stills/en/05.png)

#### 6. One law, many laws amended

The laws whose provisions amend the most other laws: the 2026 amendment of the Investment Promotion Act amends 87.

![One law, many laws amended](stills/en/06.png)

#### 7. The most-amended laws

Amendments by year for 25 laws, 2004–2026: the Social Insurance Code was amended 166 times.

![The most-amended laws](stills/en/07.png)

#### 8. Amended again and again

The laws amended once, twice or more times in a year: in 2006, 90 laws were amended three or more times.

![Amended again and again](stills/en/08.png)

#### 9. The codes

Every amendment of eight codes since their first publication: the Criminal Code 126 times since 1968, the Social Insurance Code 183 times since 1999.

![The codes](stills/en/09.png)

#### 10. Laws from before 1990

Twenty laws and decrees from before 1990 that were amended after 2004 too; the oldest is the Obligations and Contracts Act of 1950.

![Laws from before 1990](stills/en/10.png)

### III. The Constitution and the Constitutional Court

#### 11. The Constitution

The provisions each version changes, by chapter: the 2023 amendment touched 27, 11 of them in the chapter on the judiciary.

![The Constitution](stills/en/11.png)

#### 12. The Constitutional Court in the record of laws

The decisions the laws' citations list: 116 decisions touch 73 laws, the Criminal Code most.

![The Constitutional Court in the record of laws](stills/en/12.png)

### IV. Secondary legislation and the State Gazette

#### 13. The State Gazette

Acts by year and kind: 5.5 acts of the executive for every law.

![The State Gazette](stills/en/13.png)

#### 14. Tuesdays and Fridays

The Gazette's issues by weekday: 95% come out on a Tuesday or a Friday.

![Tuesdays and Fridays](stills/en/14.png)

#### 15. Government decrees

What Council of Ministers decrees do: in 2024, 65% of them approved extra spending or transfers.

![Government decrees](stills/en/15.png)

#### 16. Entry into force

The day an act takes effect against the day it is published: one government decree in six takes effect before it is published.

![Entry into force](stills/en/16.png)

#### 17. Ordinances

Ordinances by topic: health leads, and 567 each set the qualification for one profession.

![Ordinances](stills/en/17.png)

### V. The European Union, treaties and the euro

#### 18. EU law in the statute book

The laws that name an EU directive or regulation: 48% in 2023, 0% in 2004.

![EU law in the statute book](stills/en/18.png)

#### 19. Ratifications

Ratification laws by the state the treaty is with, on a map and by period: most often the United States, Romania and Switzerland.

![Ratifications](stills/en/19.png)

#### 20. The euro

Money amounts in laws by currency: 60% of the amounts in 2026's laws are in euro.

![The euro](stills/en/20.png)

## Data

As of commit `0fc9bba08c` (15 November 2026).

| Dataset | Where in the repository | Records | Coverage |
| --- | --- | ---: | --- |
| Git history | branch `main` | 18,184 commits | each act is dated the day it took effect (`In-force:`); the issue day is in `Published:` |
| Acts with text | `zakon/`, `kodeks/`, `postanovlenie/`, `naredba/`, `pravilnik/`, `instruktsiya/` | 17,519 acts | State Gazette 2003–2026; one version each: the text as enacted |
| Held-back acts | `data/held.json` | 3,279 acts | title and Gazette issue only; they do not read cleanly |
| Record of laws | `data/laws.csv` | 3,018 rows | the days each law was adopted, published and took effect |
| Citations in laws | `zakon/**/uvod.md`, `zakon/**/par-*.md` | 7,873 amendments of 427 laws | the amendment history of each amended law since its first publication |
| Constitution | `konstitutsiya/` | 4 versions | 2008, 2015, 2023 and 2024 |

## Limits

- **Laws are held as enacted.** The repository holds each act as published; the amendment history of laws (charts 5–10 and 12) comes from the citations in the texts of the laws that amend them. So it covers only laws that a law with text in the repository amends; the codes themselves are not in the repository.
- **Some acts are held back.** 3,279 acts do not read cleanly and are known only by title (`data/held.json`). Charts that count acts by title and Gazette issue (1, 3, 4, 13, 15, 17, 19) include them; charts that read the acts' text or the history's trailers (5–12, 14, 16, 18, 20) do not. The texts of laws from 2003 and 2006–2008 are the least complete.
- **Categories are read from titles.** The kind of law (chart 3), what a decree does (15), the topic of an ordinance (17), the area of an amended law (5) and the other party to a treaty (19) come from words in the title, by the rules in `src/prep.py`; whatever no rule recognises is shown as "Other".
- **National Assemblies** are separated by the days of their first sittings, which are input data; the 52nd's first sitting is the day it elected its chairman (a decision in `reshenie/`).
- **Texts that end with an annex** may lack the provisions after it (the State Budget Acts, for example), so chart 6 counts fewer amendments by those laws.
- **Partial periods** (2026, the 52nd National Assembly, the 39th assembly before 2003) are drawn lighter, with hollow dots or hatched, and labelled as such.

## Rebuilding

```sh
python visualisations/src/make.py            # git log + the texts of the laws -> src/.build/ -> balgarskoto-pravo-v-20-grafiki.html
node visualisations/src/stills.cjs           # images for these READMEs (needs Playwright; PLAYWRIGHT=<path> if not global)
```

`make.py` reads everything from git objects, so it also works in a blobless or `--no-checkout` clone (missing blobs are fetched in one batch). It reads `origin/main` (or `HEAD`) by default; `--ref` picks another branch or commit. It writes nothing into the repository except the page and the `src/.build/` folder (which git ignores).

| File | What it does |
| --- | --- |
| `src/make.py` | extracts the history, the texts of the laws and the tables into `src/.build/`, then runs `prep.py` and `build.py` |
| `src/prep.py` | computes every number for the 20 charts and the data profile into `src/.build/data.json` |
| `src/page.tpl.html` | the page: text in both languages, the charts (d3), the tables |
| `src/build.py` | puts `data.json` into the template and writes the page |
| `src/stills.cjs` | draws each chart as a PNG into `stills/bg/` and `stills/en/` |
