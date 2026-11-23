#!/usr/bin/env python3
"""Hand-check worksheet: prints, for one country and one year, every input number behind the unhedged net
(and, with --hedge, the twelve monthly terms behind the hedged net), each with the file and the line it comes from,
then the formula with the numbers substituted and the build's value for comparison.

  python3 check/worksheet.py JP 2023
  python3 check/worksheet.py JP 2023 --hedge
  python3 check/worksheet.py ZA 2016          (a year whose hours were interpolated)
  python3 check/worksheet.py CN 2010          (fixed 2,100 hours per worker)
  python3 check/worksheet.py JP 2025          (hours extended with labour-force growth)

Reads only inputs/, data/raw/ and the output CSVs it compares against. No pandas; csv and math only.
"""
import csv, math, os, sys

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN, RAW, OUT = os.path.join(H, "inputs"), os.path.join(H, "data", "raw"), os.path.join(H, "output")
ISO = {"AR": "ARG", "AT": "AUT", "AU": "AUS", "BE": "BEL", "BR": "BRA", "CA": "CAN", "CH": "CHE", "CL": "CHL", "CN": "CHN", "CO": "COL",
       "CZ": "CZE", "DE": "DEU", "DK": "DNK", "ES": "ESP", "FI": "FIN", "FR": "FRA", "GB": "GBR", "GR": "GRC", "HK": "HKG", "HU": "HUN",
       "ID": "IDN", "IE": "IRL", "IL": "ISR", "IN": "IND", "IT": "ITA", "JP": "JPN", "KR": "KOR", "MX": "MEX", "MY": "MYS", "NL": "NLD",
       "NO": "NOR", "NZ": "NZL", "PH": "PHL", "PL": "POL", "PT": "PRT", "RU": "RUS", "SA": "SAU", "SE": "SWE", "SG": "SGP", "TH": "THA",
       "TR": "TUR", "US": "USA", "ZA": "ZAF"}
FIXED_HOURS = {"CN", "SA"}

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(args) != 2 or args[0] not in ISO: sys.exit(__doc__)
c, y = args[0], int(args[1]); c3 = ISO[c]; hedge = "--hedge" in sys.argv
rel = lambda p: os.path.relpath(p, H)
rows = []                                                   # (label, value, file, locator)
def note(label, value, path, where):
    if not any(r[0] == label for r in rows): rows.append((label, value, rel(path), where))    # the extension step recurses; list each input once


def find(path, pred, col):
    """first row satisfying pred; returns (value, 'line N') with the 1-based line number in the file"""
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r, start=2):
            if pred(row): return float(row[col]), f"line {i}"
    return None, None


# ---------------------------------------------------------------- GMP, December levels (public CC-GMP TR file)
P = os.path.join(IN, "engine", "cc_gmp_tr.csv")
G = {}
for yy in (y - 1, y):
    v, w = find(P, lambda r, yy=yy: r["date"] == f"{yy}-12-31", "level"); G[yy] = v; note(f"GMP level, Dec {yy} (USD, 1975-12 = 1000)", v, P, f'{w}, date {yy}-12-31, column "level"')

# ---------------------------------------------------------------- exchange rate, December monthly average (BIS)
P = os.path.join(RAW, "bis_xru_m.csv")
X = {}
for yy in (y - 1, y):
    v, w = find(P, lambda r, yy=yy: r["FREQ"] == "M" and r["REF_AREA"] == c and r["TIME_PERIOD"] == f"{yy}-12", "OBS_VALUE")
    X[yy] = v; note(f"FX, Dec {yy} ({c} currency per USD, monthly average)", v, P, f'{w}, REF_AREA {c}, TIME_PERIOD {yy}-12, column "OBS_VALUE"')

# ---------------------------------------------------------------- nominal GDP in local currency (World Bank table, year x ISO3)
P = os.path.join(IN, "wb", "wb_ngdp_lcu.csv")
NG = {}
for yy in (y - 1, y):
    v, w = find(P, lambda r, yy=yy: int(r["year"]) == yy, c3); NG[yy] = v; note(f"Nominal GDP {yy} (LCU)", v, P, f"{w}, year {yy}, column {c3}")

# ---------------------------------------------------------------- hours worked = persons engaged x hours per worker (PWT via FRED)
def pwt(sid):
    d, L = {}, {}
    with open(os.path.join(IN, "pwt", sid + ".csv"), newline="") as f:
        for i, row in enumerate(csv.reader(f), start=1):
            if i == 1: continue
            if row[1] not in ("", "."): d[int(row[0][:4])] = float(row[1]); L[int(row[0][:4])] = i
    return d, L

EMP, EMPL = pwt(f"EMPENG{c}A148NRUG")
if c in FIXED_HOURS: AVH, AVHL = {yy: 2100.0 for yy in EMP}, {}
else: AVH, AVHL = pwt(f"AVHWPE{c}A065NRUG")
LF = {}
with open(os.path.join(IN, "wb", "wb_lf.csv"), newline="") as f:
    for i, row in enumerate(csv.DictReader(f), start=2):
        if row[c3] not in ("", None): LF[int(row["year"])] = (float(row[c3]), i)

def hours(yy):
    """total hours in year yy with the note's conventions; records the inputs used"""
    pe = os.path.join(IN, "pwt", f"EMPENG{c}A148NRUG.csv"); pa = os.path.join(IN, "pwt", f"AVHWPE{c}A065NRUG.csv")
    if yy in EMP and (yy in AVH or c in FIXED_HOURS):
        note(f"Persons engaged {yy} (millions)", EMP[yy], pe, f"line {EMPL[yy]}, date {yy}-01-01")
        if c in FIXED_HOURS: note(f"Hours per worker {yy}", 2100.0, "(convention)", "fixed at 2,100: no PWT hours series for this country")
        else: note(f"Hours per worker {yy}", AVH[yy], pa, f"line {AVHL[yy]}, date {yy}-01-01")
        return EMP[yy] * 1e6 * AVH[yy]
    if yy in EMP and yy not in AVH and c not in FIXED_HOURS and min(AVH) < yy < max(AVH):      # interior gap: log-linear interpolation
        a = max(k for k in AVH if k < yy); b = min(k for k in AVH if k > yy)
        v = math.exp(math.log(AVH[a]) + (math.log(AVH[b]) - math.log(AVH[a])) * (yy - a) / (b - a))
        note(f"Persons engaged {yy} (millions)", EMP[yy], pe, f"line {EMPL[yy]}, date {yy}-01-01")
        note(f"Hours per worker {a}", AVH[a], pa, f"line {AVHL[a]}"); note(f"Hours per worker {b}", AVH[b], pa, f"line {AVHL[b]}")
        note(f"Hours per worker {yy} (interpolated)", v, "(computed)", f"exp(ln {AVH[a]:.4f} + (ln {AVH[b]:.4f} - ln {AVH[a]:.4f}) x {yy - a}/{b - a}): PWT has no {yy} row")
        return EMP[yy] * 1e6 * v
    if yy in (2024, 2025) and (yy - 1) in LF and yy in LF:                                  # extension with labour-force growth
        h_prev = hours(yy - 1)
        note(f"Labour force {yy - 1}", LF[yy - 1][0], os.path.join(IN, "wb", "wb_lf.csv"), f"line {LF[yy - 1][1]}, column {c3}")
        note(f"Labour force {yy}", LF[yy][0], os.path.join(IN, "wb", "wb_lf.csv"), f"line {LF[yy][1]}, column {c3}")
        note(f"Total hours {yy} (extended)", h_prev * LF[yy][0] / LF[yy - 1][0], "(computed)", f"total hours {yy - 1} x labour force {yy} / labour force {yy - 1}: PWT ends before {yy}")
        return h_prev * LF[yy][0] / LF[yy - 1][0]
    sys.exit(f"no hours for {c} in {yy}; pick another year (Table A1 gives each country's sample)")

HRS = {y - 1: hours(y - 1), y: hours(y)}
NH = {yy: NG[yy] / HRS[yy] for yy in (y - 1, y)}

# ---------------------------------------------------------------- print the worksheet
W = max(len(r[0]) for r in rows) + 2
print(f"\nWORKSHEET  {c} ({c3}), year {y}: the GMP held unhedged, net of the growth of the national hour\n")
print("Inputs (open each file at the line given and compare):")
for label, v, path, where in rows:
    shown = f"{v:,.0f}" if abs(v) >= 1e9 else f"{v:,.12g}"           # full precision as stored, so the totals can be reproduced exactly
    print(f"  {label:<{W}} {shown:>26}   {path}  [{where}]")
print("\nStep 1  national hour = nominal GDP / total hours   (total hours = persons engaged x 1e6 x hours per worker)")
for yy in (y - 1, y):
    print(f"  NH_{yy} = {NG[yy]:,.0f} / {HRS[yy]:,.0f} = {NH[yy]:,.6f} LCU per hour")
a = math.log(G[y] / G[y - 1]); b = math.log(X[y] / X[y - 1]); n = math.log(NH[y] / NH[y - 1])
print("\nStep 2  three log changes")
print(f"  GMP in USD        ln({G[y]:,.4f} / {G[y - 1]:,.4f}) = {a:+.6f}")
print(f"  currency per USD  ln({X[y]:,.6f} / {X[y - 1]:,.6f}) = {b:+.6f}   (positive = {c} currency depreciated against the dollar)")
print(f"  national hour     ln({NH[y]:,.6f} / {NH[y - 1]:,.6f}) = {n:+.6f}")
net = a + b - n
print(f"\nStep 3  net in own hours = (GMP in USD + currency per USD) - national hour\n        = ({a:+.6f}) + ({b:+.6f}) - ({n:+.6f}) = {net:+.6f}  ->  x 1000 = {net * 1000:+.2f} hours per 1,000")
P = os.path.join(OUT, "net_unhedged_annual.csv")
bv, w = find(P, lambda r: int(float(r[""] if "" in r else list(r.values())[0])) == y, c)
print(f"\nBuild   {rel(P)} [{w}, row {y}, column {c}] = {bv * 1000:+.2f}    difference {abs(net - bv) * 1000:.4f}  {'OK' if abs(net - bv) * 1000 < 0.01 else 'DIFFERS'}")

# ---------------------------------------------------------------- hedged: twelve monthly terms
if hedge:
    src, hw = None, None
    with open(os.path.join(OUT, "table1_countries.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["cc"] == c: src = r["rate_source"]; hf = r["hedge_from"]
    if not src: sys.exit(f"\n{c} has no short-rate series; the hedge is not built for it")
    if c == "JP" and y < 1986: sys.exit("\nfor Japan pick 1986 or later; before July 1985 the build splices in the Bank of Japan discount rate from FRED")
    if hf and y < int(float(hf)): sys.exit(f"\nhedged series for {c} starts in {int(float(hf))}; pick a later year")
    series = "IRSTCI" if src.startswith("IRSTCI") else "IR3TIB"
    P = os.path.join(RAW, f"oecd_{series}.csv")
    R = {}
    with open(P, newline="") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            if row["REF_AREA"] in (c3, "USA") and row["OBS_VALUE"] not in ("", None): R[(row["REF_AREA"], row["TIME_PERIOD"])] = (float(row["OBS_VALUE"]), i)
    PE = os.path.join(IN, "engine", "four_series_returns_corrected.csv")
    GM = {}
    with open(PE, newline="") as f:
        rd = csv.reader(f); hdr = next(rd)
        for i, row in enumerate(rd, start=2): GM[row[0][:7]] = (float(row[1]), i)
    def prev(m):
        yy, mo = int(m[:4]), int(m[5:7]); return f"{yy - 1}-12" if mo == 1 else f"{yy}-{mo - 1:02d}"
    def last_before(area, m):          # the rate of the previous month, carried forward over a gap as the build does
        k = m
        for _ in range(60):
            k = prev(k)
            if (area, k) in R: return R[(area, k)], k
        return None, None
    print(f"\nHEDGED  rate series: OECD {series} ({rel(P)}), {c3} leg and USA leg; GMP monthly return from {rel(PE)} column \"{hdr[1]}\"")
    print(f"  monthly hedged return = GMP monthly return + (rate_{c3} - rate_USA) / 1200, both rates from the PREVIOUS month\n")
    print(f"  {'month':8} {'GMP return':>12} {'line':>6}   {c3 + ' rate':>9} {'(month, line)':>16}   {'USA rate':>9} {'(month, line)':>16}   {'carry/1200':>11}   {'1 + hedged':>11}")
    level = 1.0
    for mo in range(1, 13):
        m = f"{y}-{mo:02d}"
        g, gl = GM[m]; (ic, il), km = last_before(c3, m); (iu, ul), ku = last_before("USA", m)
        carry = (ic - iu) / 1200.0; level *= 1 + g + carry
        flag = "" if (km == prev(m) and ku == prev(m)) else "  <- rate carried forward"
        print(f"  {m:8} {g:>12.6f} {gl:>6}   {ic:>9.3f} {'(' + km + ', ' + str(il) + ')':>16}   {iu:>9.3f} {'(' + ku + ', ' + str(ul) + ')':>16}   {carry:>+11.6f}   {1 + g + carry:>11.6f}{flag}")
    hr = math.log(level)
    print(f"\n  product of the twelve (1 + hedged) = {level:.6f};  ln = {hr:+.6f}  (the hedged GMP return in {c} currency, Dec to Dec)")
    hnet = hr - n
    print(f"  hedged net = {hr:+.6f} - national hour {n:+.6f} = {hnet:+.6f}  ->  x 1000 = {hnet * 1000:+.2f} hours per 1,000")
    P = os.path.join(OUT, "net_hedged_annual.csv")
    bh, w = find(P, lambda r: int(float(list(r.values())[0])) == y, c)
    print(f"  Build   {rel(P)} [{w}, row {y}, column {c}] = {bh * 1000:+.2f}    difference {abs(hnet - bh) * 1000:.4f}  {'OK' if abs(hnet - bh) * 1000 < 0.01 else 'DIFFERS'}")
    print(f"\n  (the unhedged Dec-to-Dec return in {c} currency was {a + b:+.6f}; hedged minus unhedged this year = {(hr - (a + b)) * 1000:+.2f} per 1,000)")
print()
