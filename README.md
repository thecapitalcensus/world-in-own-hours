# Holding the World in One's Own Hours

Code and derived data for the fifth Capital Census research note:

Nakanishi, K. (2026). *Holding the World in One's Own Hours: The Global Market Portfolio for the Residents of 43 Countries,
Hedged and Unhedged.* Research note, v1.0, 23 November 2026. SSRN: forthcoming.

The note asks the question a resident asks: a person who works in one country and holds the whole world — does the holding
grow or shrink against an hour of their own country's work? It measures the global market portfolio (GMP) in the *national
hour* (nominal GDP per hour worked in local currency) of each of the 43 countries in the world-hour panel, 1976–2025,
unhedged and with the dollar leg sold forward, and splits the result exactly into a world part (the GMP in world hours, the
same for everyone) and a country part (the world hour over the country's own hour in dollars). The analysis is exploratory
and was not pre-registered.

**Status: v1.0 (23 November 2026), reviewed by the author.** The review (code read against Section 2 of the note, pipeline
re-run from the stored inputs with byte-identical outputs, hand checks with `check/worksheet.py`) is recorded in the note's
revision history.

It builds on the first four notes in the series:

- Nakanishi (2026a), *Owning the Market as It Is*, doi:10.2139/ssrn.7394599 (the GMP index)
- Nakanishi (2026b), *Measuring Assets in Hours of the World's Work*, doi:10.2139/ssrn.7445203 (the world hour)
- Nakanishi (2026d), *What the World's Capital Earns and Pays*, doi:10.2139/ssrn.7515699 (code and data: https://github.com/thecapitalcensus/capital-earns-and-pays)
- Nakanishi (2026e), *What a Working Life Holds*, doi:10.2139/ssrn.7646578 (code and data: https://github.com/thecapitalcensus/working-life-holds)

## Layout

| Path | Content |
|---|---|
| `code/fetch.py` | Downloads BIS exchange rates, OECD short rates and FRED series into `data/raw/`, writes `MANIFEST.json`. Not needed to reproduce the note: the downloads used are shipped. |
| `code/build.py` | The analysis: national hours, GMP in local currency, hedge, identity, statistics, robustness, figures → `output/` |
| `check/check_countries.py` | Second computation of every per-country unhedged figure and four hedged ones, from the definitions, using the public CC-GMP TR level file |
| `check/worksheet.py` | Hand-check worksheet: `python3 check/worksheet.py JP 2023 --hedge` prints every input number for one country-year with its file and line, the formula with the numbers substituted, and the build's value |
| `check/source_check_JP2023.md` | The Japan 2022–2023 inputs compared with what the publishers serve |
| `code/build_paper.py`, `code/paper_template.html`, `code/style.css` | Fill the note from `output/`; writes `output/paper/resident.html` and `numbers_in_text.json` |
| `tools/html_to_pdf.py` | Prints the HTML to `output/paper/resident.pdf` with headless Chrome (A4, footer, page numbers); `tools/html_to_pdf.swift` is a WebKit fallback without Chrome, and `tools/pdf_footer.swift` adds the footer to its output |
| `inputs/engine/` | Frozen engine: monthly GMP return (`four_series_returns_corrected.csv`), annual weights, public CC-GMP TR levels (as in the capital-earns-and-pays repository and on the site) |
| `inputs/world_hour/` | CC-WH series (note 2), as in the capital-earns-and-pays repository |
| `inputs/pwt/` | Penn World Table persons engaged and hours via FRED, 43 countries |
| `inputs/wb/` | World Bank GDP in LCU and USD, labour force (year × ISO3 tables) |
| `data/raw/` | The BIS, OECD and FRED downloads used, with `MANIFEST.json` (URLs, dates, SHA-256) |
| `output/` | Tables (`table1_countries.csv` … `table4_robustness.csv`), annual and monthly panels, `numbers.json`, `build_log.json`, `check_result.json`, figures, and `paper/` (the note as HTML and PDF) |
| `MANIFEST.md` | Size and SHA-256 of every file in the repository (`tools/make_manifest.py`) |

## How to reproduce

Requires Python 3.9+ with pandas, numpy and matplotlib (v1.0 was re-run with Python 3.9.6 and pandas 2.3.3). No network
access is needed. From the repository root:

```
python3 code/build.py               # output/
python3 check/check_countries.py    # output/check_result.json
python3 code/build_paper.py         # output/paper/resident.html, numbers_in_text.json
python3 tools/html_to_pdf.py output/paper/resident.html output/paper/resident.pdf   # needs Google Chrome and websocket-client
```

`python3 code/fetch.py --refresh` re-downloads `data/raw/`; the publishers revise their data, so a refreshed run need not
reproduce the note's figures exactly.

## Conventions

- National hour: World Bank nominal GDP (LCU) ÷ (PWT persons engaged × annual hours); China and Saudi Arabia at 2,100 hours per worker; 2024–25 extended with World Bank labour-force growth (as notes 2 and 4).
- Annual returns December to December; GMP in LCU = USD level × BIS monthly-average rate; national-hour growth is the calendar-year change (note 4 baseline).
- Hedged = USD GMP return + (local short rate − US short rate)/12 each month, using the previous month's average rate (dollar leg only). OECD IR3TIB, except where IR3TIB begins after 1990 and IRSTCI begins earlier (then IRSTCI throughout: CH, CL, CN, GR, ID, IN, MX, PL, RU); US leg matched by instrument. Japan: IRSTCI from 1985-07, BoJ discount rate before, against US IRSTCI. Missing months carried forward (counts in `build_log.json`; Türkiye has nine in 2023, which understates its 2023 interest differential).
- Identity: net in own hours = (GMP − world hour) + (world hour − own hour in USD), exact with December exchange rates in both terms.

## Licence

See `LICENSE.md`. In short: code MIT; the note's text CC BY-NC-ND 4.0; series that depend on the frozen engine and the world
hour CC BY-NC 4.0 (CC-GMP TR, CC-WH); copies of third-party data under their publishers' terms (World Bank and PWT CC BY 4.0,
OECD terms, BIS and FRED with attribution).

This repository is general information and a research record. It is not investment advice.
