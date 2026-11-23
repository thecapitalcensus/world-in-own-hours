"""Independent check of the per-country headline in output/table1_countries.csv (unhedged net, hours a year per 1,000)
and of the hedged net for a few countries. Written against the stated conventions, not against code/build.py:

  net_c[y] = log(GMP_Dec,y / GMP_Dec,y-1) + log(FX_Dec,y / FX_Dec,y-1) - log(NH_y / NH_{y-1})
  GMP level from the public CC-GMP TR file (site copy), not from the engine's return file;
  FX = BIS monthly average, December; NH = World Bank LCU GDP / (PWT persons engaged x annual hours), CN/SA at 2,100 hours,
  2024-25 hours extended with World Bank labour-force growth; an interior gap in hours per worker is log-linearly interpolated.
  hedged: monthly simple return = GMP monthly return + (i_c - i_US)/1200 with the rate of the previous month-end.
"""
import csv, json, math, os, sys
from collections import defaultdict

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN, RAW, OUT = os.path.join(H, "inputs"), os.path.join(H, "data", "raw"), os.path.join(H, "output")
ISO = {"AR": "ARG", "AT": "AUT", "AU": "AUS", "BE": "BEL", "BR": "BRA", "CA": "CAN", "CH": "CHE", "CL": "CHL", "CN": "CHN", "CO": "COL",
       "CZ": "CZE", "DE": "DEU", "DK": "DNK", "ES": "ESP", "FI": "FIN", "FR": "FRA", "GB": "GBR", "GR": "GRC", "HK": "HKG", "HU": "HUN",
       "ID": "IDN", "IE": "IRL", "IL": "ISR", "IN": "IND", "IT": "ITA", "JP": "JPN", "KR": "KOR", "MX": "MEX", "MY": "MYS", "NL": "NLD",
       "NO": "NOR", "NZ": "NZL", "PH": "PHL", "PL": "POL", "PT": "PRT", "RU": "RUS", "SA": "SAU", "SE": "SWE", "SG": "SGP", "TH": "THA",
       "TR": "TUR", "US": "USA", "ZA": "ZAF"}

# GMP level, December values, from the public CC-GMP TR series
lvl = {}
for r in csv.DictReader(open(os.path.join(IN, "engine", "cc_gmp_tr.csv"))):
    if r["date"].endswith("-12-31"): lvl[int(r["date"][:4])] = float(r["level"])
# cc_gmp_tr switches to the ETF implementation after June 2026 only, so December levels to 2025 are the backtested engine levels.

# BIS December averages
fx = defaultdict(dict)
for r in csv.DictReader(open(os.path.join(RAW, "bis_xru_m.csv"))):
    if r["FREQ"] == "M" and r["TIME_PERIOD"].endswith("-12") and r["OBS_VALUE"]: fx[r["REF_AREA"]][int(r["TIME_PERIOD"][:4])] = float(r["OBS_VALUE"])

# World Bank tables (year x ISO3)
def table(name):
    rows = list(csv.DictReader(open(os.path.join(IN, "wb", name)))); out = defaultdict(dict)
    for r in rows:
        y = int(r["year"])
        for k, v in r.items():
            if k != "year" and v not in ("", None): out[k][y] = float(v)
    return out
NG, LF = table("wb_ngdp_lcu.csv"), table("wb_lf.csv")

def pwt(sid):
    d = {}
    for r in csv.DictReader(open(os.path.join(IN, "pwt", sid + ".csv"))):
        v = list(r.values())
        if v[1] not in ("", "."): d[int(v[0][:4])] = float(v[1])
    return d

NH = {}
for c, c3 in ISO.items():
    emp = pwt(f"EMPENG{c}A148NRUG"); avh = {y: 2100.0 for y in emp} if c in ("CN", "SA") else pwt(f"AVHWPE{c}A065NRUG")
    for y in range(min(avh), max(avh) + 1):                                 # interior gap in hours per worker: log-linear interpolation (Section 3)
        if y not in avh:
            a = max(k for k in avh if k < y); b = min(k for k in avh if k > y)
            avh[y] = math.exp(math.log(avh[a]) + (math.log(avh[b]) - math.log(avh[a])) * (y - a) / (b - a))
    hrs = {y: emp[y] * 1e6 * avh[y] for y in emp if y in avh}
    for y in (2024, 2025):
        if y not in hrs and (y - 1) in hrs and y in LF[c3] and (y - 1) in LF[c3]: hrs[y] = hrs[y - 1] * LF[c3][y] / LF[c3][y - 1]
    NH[c] = {y: NG[c3][y] / hrs[y] for y in hrs if y in NG[c3]}

T1 = {r["cc"]: r for r in csv.DictReader(open(os.path.join(OUT, "table1_countries.csv")))}
bad = 0; out = []
for c in ISO:
    nets = []
    for y in range(1976, 2026):
        try: nets.append(math.log(lvl[y] / lvl[y - 1]) + math.log(fx[c][y] / fx[c][y - 1]) - math.log(NH[c][y] / NH[c][y - 1]))
        except KeyError: continue
    if not nets: continue
    mine = sum(nets) / len(nets) * 1000; theirs = float(T1[c]["net"]); n_theirs = int(T1[c]["years"])
    ok = abs(mine - theirs) < 0.05 and len(nets) == n_theirs
    bad += not ok; out.append((c, len(nets), round(mine, 2), round(theirs, 2), "ok" if ok else "DIFF"))
for o in out: print(*o)
print(f"unhedged: {len(out)} countries checked, {bad} differences above 0.05 hours per 1,000")

# hedged check for Japan, Germany, United Kingdom from the OECD / FRED files
def oecd(name, c3):
    d = {}
    for r in csv.DictReader(open(os.path.join(RAW, name))):
        if r["REF_AREA"] == c3 and r["OBS_VALUE"]: d[r["TIME_PERIOD"]] = float(r["OBS_VALUE"])
    return d
gm = {}
for r in csv.DictReader(open(os.path.join(IN, "engine", "four_series_returns_corrected.csv"))):
    gm[r["date"][:7]] = float(list(r.values())[1])
months = sorted(gm)
def prev(m):
    y, mo = int(m[:4]), int(m[5:7]); return f"{y-1}-12" if mo == 1 else f"{y}-{mo-1:02d}"
hbad = 0
for c, c3, src in (("DE", "DEU", "oecd_IR3TIB.csv"), ("GB", "GBR", "oecd_IR3TIB.csv"), ("CH", "CHE", "oecd_IRSTCI.csv"), ("KR", "KOR", "oecd_IR3TIB.csv")):
    ic, iu = oecd(src, c3), oecd(src, "USA")
    hf = int(float(T1[c]["hedge_from"])); lv = 1.0; dec = {hf - 1: 1.0}; last_c = last_u = None; filled = 0
    for m in months:
        y = int(m[:4])
        if y < hf or y > 2025: continue
        p = prev(m)
        if p in ic: last_c = ic[p]
        else: filled += 1
        if p in iu: last_u = iu[p]
        lv *= 1 + gm[m] + (last_c - last_u) / 1200.0          # a missing month carries the previous rate forward, as the build does
        if m.endswith("-12"): dec[y] = lv
    nets = [math.log(dec[y] / dec[y - 1]) - math.log(NH[c][y] / NH[c][y - 1]) for y in range(hf, 2026) if y in dec and (y - 1) in dec]
    mine = sum(nets) / len(nets) * 1000; theirs = float(T1[c]["net_h"]); ok = abs(mine - theirs) < 0.05
    hbad += not ok; print(c, "hedged", hf, len(nets), round(mine, 2), round(theirs, 2), "ok" if ok else "DIFF", f"(rate months carried forward: {filled})")
print(f"hedged: 4 countries checked, {hbad} differences above 0.05")
# row consistency of the published tables: every row must add up at the printed precision
rbad = 0
for c, r in T1.items():
    f = lambda k: float(r[k]) if r.get(k) not in ("", None) else float("nan")
    if abs(f("gmp_lcu") - f("need") - f("net")) > 0.05 or abs(f("term_world") + f("term_rel") - f("net")) > 0.05:
        rbad += 1; print(c, "unhedged row does not add up")
    if r.get("net_h") not in ("", None):
        if abs(f("net_h") - f("net_u_same") - f("hedge_minus_unhedged")) > 0.05 or abs(f("carry") - f("fx_change") - f("hedge_gain")) > 0.05 or abs(f("hedge_gain") - f("hedge_minus_unhedged")) > 0.05:
            rbad += 1; print(c, "hedged row does not add up")
T3 = list(csv.DictReader(open(os.path.join(OUT, "table3_hedge_periods.csv"))))
for r in T3:
    n = int(r["n_countries"])
    for k in ("share_hedge_higher", "share_hedge_lower_sd"):
        if abs(float(r[k]) * n - round(float(r[k]) * n)) > 0.02: rbad += 1; print(r["period"], k, "is not a count over", n, "countries")
T2 = list(csv.DictReader(open(os.path.join(OUT, "table2_periods.csv"))))
for r in T2:
    n = int(r["n_countries"])
    if abs(float(r["share_countries_positive"]) * n - round(float(r["share_countries_positive"]) * n)) > 0.03: rbad += 1; print(r["period"], "share positive is not a count over", n, "countries")
print(f"row consistency: {rbad} problems")
json.dump({"unhedged_checked": len(out), "unhedged_diff": bad, "hedged_checked": 4, "hedged_diff": hbad, "row_consistency_problems": rbad}, open(os.path.join(OUT, "check_result.json"), "w"), indent=1)
sys.exit(1 if (bad or hbad or rbad) else 0)
