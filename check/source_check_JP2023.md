# Source check: Japan 2022–2023 inputs against the live publishers (7 November 2026)

Every input number that `check/worksheet.py JP 2023 --hedge` prints was compared with the value the publisher serves today.
Stored = the file in `inputs/` or `data/raw/`; live = the publisher's API or page, retrieved 7 November 2026 (JST evening).

| Input | Stored | Live | Source consulted |
|---|---|---|---|
| Nominal GDP 2022, JPY | 584,900,600,000,000 | 584,900,600,000,000 | World Bank API NY.GDP.MKTP.CN, JPN (last updated 2026-10-08) |
| Nominal GDP 2023, JPY | 616,033,000,000,000 | 616,033,000,000,000 | same |
| Persons engaged 2022, millions | 67.6910705566406 | 67.6910705566406 | FRED EMPENGJPA148NRUG (PWT 11.0, updated 2026-02-04) |
| Persons engaged 2023, millions | 67.9327163696289 | 67.9327163696289 | same |
| Hours per worker 2022 | 1652.13 | 1652.13 | FRED AVHWPEJPA065NRUG (PWT 11.0, updated 2026-02-04) |
| Hours per worker 2023 | 1653.90 | 1653.90 | same |
| JPY per USD, Dec 2022 monthly average | 134.886621 | 134.886621 | BIS WS_XRU, M.JP..A |
| JPY per USD, Dec 2023 monthly average | 144.208058 | 144.208058 | same |
| OECD IRSTCI JPN, 2022-12 … 2023-11 (12 values) | as in data/raw | identical | OECD DF_FINMARK |
| OECD IRSTCI USA, 2022-12 … 2023-11 (12 values) | as in data/raw | identical | same |
| CC-GMP TR levels, Dec 2022 and Dec 2023 | 44,748.1969 / 50,488.8045 | identical; whole file SHA-256 abf229a6… equal | https://thecapitalcensus.github.io/cc_gmp_tr.csv |

Result: no difference in any input. The engine's monthly return file and the public level file also agree (12-month compounding of the monthly returns gives ln 0.120699 against 0.120700 from the levels).

Notes
- FRED's CSV endpoint refused command-line downloads during this check (HTTP/2 stream errors and time-outs); the values were read from FRED's table pages in a browser instead. `fetch.py --refresh` may fail on the FRED files while this lasts; the default run does not re-download them.
- This is one country-year. The same comparison can be repeated for any other with the worksheet's output as the list of numbers to look up.
