"""Note 5: the global market portfolio in each country's own hours, hedged and unhedged.

Reads  inputs/engine  (frozen GMP monthly return, note 1), inputs/world_hour (CC-WH, note 2),
       inputs/pwt (PWT employment and hours via FRED), inputs/wb (World Bank GDP in LCU and USD, labour force),
       data/raw (BIS exchange rates, OECD short rates, FRED).
Writes output/*.csv, output/fig*.png, output/build_log.json, output/numbers.json.

Conventions (same as notes 3 and 4 unless stated):
  national hour      = nominal GDP in local currency (World Bank) / total hours worked (PWT persons engaged x annual hours);
                       China and Saudi Arabia: 2,100 hours per worker (note 2); 2024-25 extended with World Bank labour-force growth
  annual return      = December-to-December log change of a monthly level; GMP level in LCU = USD level x BIS monthly-average LCU/USD
  national-hour growth (annual) = calendar-year log change (as note 4 baseline); Dec-to-Dec interpolated variant in robustness
  hedged GMP (LCU)   = USD GMP return + (i_c - i_US)/12 each month, i.e. the USD leg sold forward one month under covered interest parity;
                       i = OECD 3-month interbank (IR3TIB) where published, otherwise OECD immediate rate (IRSTCI), US leg matched by instrument;
                       Japan 1976-01..1985-06: Bank of Japan discount rate (IMF, via FRED) against the US immediate rate
  world hour         = CC-WH monthly index (gdph), Dec-to-Dec
  weights            = previous year's World Bank GDP in USD, renormalised over the countries with data
  hours per 1,000    = annual log return in % x 10
"""
import hashlib, json, os
import numpy as np, pandas as pd

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN, RAW, OUT = os.path.join(H, "inputs"), os.path.join(H, "data", "raw"), os.path.join(H, "output")
os.makedirs(OUT, exist_ok=True)
LOG = {"inputs_sha256": {}, "notes": []}

ISO = {"AR": "ARG", "AT": "AUT", "AU": "AUS", "BE": "BEL", "BR": "BRA", "CA": "CAN", "CH": "CHE", "CL": "CHL", "CN": "CHN", "CO": "COL",
       "CZ": "CZE", "DE": "DEU", "DK": "DNK", "ES": "ESP", "FI": "FIN", "FR": "FRA", "GB": "GBR", "GR": "GRC", "HK": "HKG", "HU": "HUN",
       "ID": "IDN", "IE": "IRL", "IL": "ISR", "IN": "IND", "IT": "ITA", "JP": "JPN", "KR": "KOR", "MX": "MEX", "MY": "MYS", "NL": "NLD",
       "NO": "NOR", "NZ": "NZL", "PH": "PHL", "PL": "POL", "PT": "PRT", "RU": "RUS", "SA": "SAU", "SE": "SWE", "SG": "SGP", "TH": "THA",
       "TR": "TUR", "US": "USA", "ZA": "ZAF"}
NAMES = {"AR": "Argentina", "AT": "Austria", "AU": "Australia", "BE": "Belgium", "BR": "Brazil", "CA": "Canada", "CH": "Switzerland",
         "CL": "Chile", "CN": "China", "CO": "Colombia", "CZ": "Czechia", "DE": "Germany", "DK": "Denmark", "ES": "Spain", "FI": "Finland",
         "FR": "France", "GB": "United Kingdom", "GR": "Greece", "HK": "Hong Kong", "HU": "Hungary", "ID": "Indonesia", "IE": "Ireland",
         "IL": "Israel", "IN": "India", "IT": "Italy", "JP": "Japan", "KR": "Korea", "MX": "Mexico", "MY": "Malaysia", "NL": "Netherlands",
         "NO": "Norway", "NZ": "New Zealand", "PH": "Philippines", "PL": "Poland", "PT": "Portugal", "RU": "Russia", "SA": "Saudi Arabia",
         "SE": "Sweden", "SG": "Singapore", "TH": "Thailand", "TR": "Türkiye", "US": "United States", "ZA": "South Africa"}
CC = list(ISO)
Y0, Y1 = 1976, 2025
PERIODS = [(1976, 1981), (1982, 2000), (2001, 2020), (2021, 2025), (1976, 2025)]
FIXED_HOURS = {"CN", "SA"}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def inp(*parts):
    p = os.path.join(IN, *parts); LOG["inputs_sha256"][os.path.relpath(p, H)] = sha(p); return p


def raw(name):
    p = os.path.join(RAW, name); LOG["inputs_sha256"][os.path.relpath(p, H)] = sha(p); return p


# ------------------------------------------------------------------ 1. GMP (frozen engine) and world hour
g = pd.read_csv(inp("engine", "four_series_returns_corrected.csv"), index_col=0, parse_dates=True)
gmp_r = g.iloc[:, 0].astype(float)                                        # monthly simple return, 1976-01..2026-08
gmp_r.index = gmp_r.index + pd.offsets.MonthEnd(0)
GMP_L = pd.concat([pd.Series([1.0], index=[pd.Timestamp("1975-12-31")]), (1 + gmp_r).cumprod()])   # USD level, 1975-12 = 1
LOG["gmp_months"] = [str(gmp_r.index[0].date()), str(gmp_r.index[-1].date()), int(len(gmp_r))]

wh = pd.read_csv(inp("world_hour", "world_yardsticks_usd.csv"), index_col=0, parse_dates=True)["gdph"]
wh.index = wh.index + pd.offsets.MonthEnd(0)
LOG["world_hour_months"] = [str(wh.index[0].date()), str(wh.index[-1].date())]

# ------------------------------------------------------------------ 2. exchange rates (BIS, LCU per USD, monthly average)
b = pd.read_csv(raw("bis_xru_m.csv"))
b = b[b["FREQ"] == "M"]
FX = b.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE", aggfunc="first")
FX.index = pd.PeriodIndex(FX.index, freq="M").to_timestamp(how="end").normalize()
FX = FX[CC].astype(float)
LOG["fx_first_month"] = {c: str(FX[c].first_valid_index().date()) for c in CC}

# ------------------------------------------------------------------ 3. national hour (annual, LCU GDP per hour worked)
NG = pd.read_csv(inp("wb", "wb_ngdp_lcu.csv"), index_col=0)
GU = pd.read_csv(inp("wb", "wb_gdp.csv"), index_col=0)
LF = pd.read_csv(inp("wb", "wb_lf.csv"), index_col=0)


def pwt(sid):
    s = pd.read_csv(inp("pwt", sid + ".csv"), index_col=0, parse_dates=True).iloc[:, 0]
    s.index = s.index.year; return pd.to_numeric(s, errors="coerce").dropna()


HRS, HOURS_NOTE = {}, {}
for c in CC:
    emp = pwt(f"EMPENG{c}A148NRUG") * 1e6
    if c in FIXED_HOURS:
        avh = pd.Series(2100.0, index=emp.index); HOURS_NOTE[c] = "hours per worker fixed at 2,100 (no PWT series)"
    else:
        avh = pwt(f"AVHWPE{c}A065NRUG")
        full_idx = range(int(avh.index.min()), int(avh.index.max()) + 1)
        missing = [y for y in full_idx if y not in avh.index]
        if missing:                                                       # interior gap in the PWT hours series: log-linear interpolation
            avh = np.exp(np.log(avh.reindex(full_idx)).interpolate(limit_area="inside"))
            HOURS_NOTE[c] = "hours per worker interpolated (log-linear) for " + ", ".join(str(y) for y in missing)
    h = (emp * avh.reindex(emp.index)).dropna()
    e = LF[ISO[c]].dropna()
    for y in (2024, 2025):                                                # extend with labour-force growth (note 2 / note 4)
        if y not in h.index and (y - 1) in h.index and y in e.index and (y - 1) in e.index:
            h.loc[y] = h.loc[y - 1] * e.loc[y] / e.loc[y - 1]
    HRS[c] = h.sort_index()
HRS = pd.DataFrame(HRS)
NGc = NG[[ISO[c] for c in CC]].copy(); NGc.columns = CC
NH = (NGc / HRS.reindex(NGc.index))                                       # LCU per hour, annual
NH = NH.loc[1960:Y1]
g_nat = np.log(NH).diff()                                                 # calendar-year growth, baseline
g_nat_dec = 0.5 * (g_nat + g_nat.shift(-1))                               # Dec-to-Dec from mid-year points (note 4 robustness)
GUc = GU[[ISO[c] for c in CC]].copy(); GUc.columns = CC

# FX, December average and annual average, in annual form
FX_dec = FX[FX.index.month == 12].copy(); FX_dec.index = FX_dec.index.year
FX_avg = FX.groupby(FX.index.year).mean()
fx = np.log(FX_dec).diff()                                                # LCU per USD, Dec-to-Dec
fx_avg = np.log(FX_avg).diff()
# national hour in USD (annual average FX, a flow at the year's prices)
NH_usd = NH / FX_avg.reindex(NH.index)
g_nat_usd = np.log(NH_usd).diff()

# GMP annual, USD, Dec-to-Dec
L_dec = GMP_L[GMP_L.index.month == 12].copy(); L_dec.index = L_dec.index.year
r_gmp = np.log(L_dec).diff().loc[Y0:Y1]
WH_dec = wh[wh.index.month == 12].copy(); WH_dec.index = WH_dec.index.year
g_wh = np.log(WH_dec).diff().loc[Y0:Y1]

# diagnostics: redenomination mismatches would show as huge jumps in NH_usd
jumps = np.log(NH_usd).diff().abs().loc[Y0:Y1].max()
LOG["max_abs_annual_log_change_nat_hour_usd"] = jumps.round(3).to_dict()
LOG["notes"].append("national hour in USD: largest absolute annual log change by country is logged; values above 1.0 would indicate a unit mismatch between World Bank LCU GDP and BIS exchange rates")

# ------------------------------------------------------------------ 4. unhedged GMP in national hours (annual)
YEARS = list(range(Y0, Y1 + 1))
R_LCU = pd.DataFrame({c: r_gmp + fx[c].reindex(YEARS) for c in CC}).loc[YEARS]          # GMP in LCU, Dec-to-Dec
NEED = g_nat.reindex(YEARS)                                                              # growth of the national hour
NET_U = R_LCU - NEED                                                                     # unhedged net, log
# decomposition: net = (GMP - world hour) + (world hour - national hour in USD) + (FX timing term)
TERM_W = (r_gmp - g_wh).reindex(YEARS)
G_NAT_USD_DEC = (g_nat - fx).reindex(YEARS)                                             # national hour in USD with Dec-to-Dec FX (so identity is exact)
TERM_REL = pd.DataFrame({c: g_wh.reindex(YEARS) - G_NAT_USD_DEC[c] for c in CC})
assert np.allclose((TERM_W.values[:, None] + TERM_REL.values), NET_U.values, equal_nan=True)

# ------------------------------------------------------------------ 5. short rates and the hedged GMP (monthly)
def oecd(name):
    d = pd.read_csv(raw(name), low_memory=False)
    d = d[d["OBS_VALUE"].notna()]
    t = d.pivot_table(index="TIME_PERIOD", columns="REF_AREA", values="OBS_VALUE", aggfunc="first")
    t.index = pd.PeriodIndex(t.index, freq="M").to_timestamp(how="end").normalize(); return t.astype(float)


IR3, IRS = oecd("oecd_IR3TIB.csv"), oecd("oecd_IRSTCI.csv")
fred = lambda sid: pd.read_csv(raw(f"fred_{sid}.csv"), index_col=0, parse_dates=True).iloc[:, 0].pipe(lambda s: s.set_axis(s.index + pd.offsets.MonthEnd(0))).astype(float)
TB3, JP_DISC = fred("TB3MS"), fred("INTDSRJPM193N")
RATE, RATE_US, RATE_SRC = {}, {}, {}
for c in CC:
    c3 = ISO[c]
    if c3 in IR3 and IR3[c3].first_valid_index() is not None and IR3[c3].first_valid_index() <= pd.Timestamp("1990-01-31"):
        RATE[c], RATE_US[c], RATE_SRC[c] = IR3[c3], IR3["USA"], "IR3TIB"
    elif c3 in IR3 and c3 not in IRS:
        RATE[c], RATE_US[c], RATE_SRC[c] = IR3[c3], IR3["USA"], "IR3TIB"
    elif c3 in IRS and c3 in IR3:
        # both exist: take the one that starts earlier (3-month preferred on a tie)
        s3, si = IR3[c3].first_valid_index(), IRS[c3].first_valid_index()
        if s3 is not None and (si is None or s3 <= si): RATE[c], RATE_US[c], RATE_SRC[c] = IR3[c3], IR3["USA"], "IR3TIB"
        else: RATE[c], RATE_US[c], RATE_SRC[c] = IRS[c3], IRS["USA"], "IRSTCI"
    elif c3 in IRS:
        RATE[c], RATE_US[c], RATE_SRC[c] = IRS[c3], IRS["USA"], "IRSTCI"
    else:
        RATE_SRC[c] = None
# Japan: immediate rate from 1985-07 (OECD), Bank of Japan discount rate before (note: the yen-in-world-hours chapter uses the same splice)
jp = IRS["JPN"].copy()
pre = JP_DISC[(JP_DISC.index >= "1975-12-31") & (JP_DISC.index < jp.first_valid_index())]
RATE["JP"] = pd.concat([pre, jp.dropna()]).sort_index(); RATE_US["JP"] = IRS["USA"]; RATE_SRC["JP"] = "IRSTCI from 1985-07; BoJ discount rate (IMF) 1975-12..1985-06"
US_SRC = RATE_SRC.get("US")
LOG["rate_source"] = RATE_SRC
LOG["rate_first_month"] = {c: str(RATE[c].first_valid_index().date()) for c in RATE if RATE[c].first_valid_index() is not None}

M = pd.DataFrame(index=gmp_r.index)
M["gmp_usd"] = gmp_r
HEDGED_L, LOCAL_BILL_L, USD_BILL_L = {}, {}, {}
for c in CC:
    if c not in RATE: continue
    ic, iu = RATE[c].reindex(M.index).shift(1), RATE_US[c].reindex(M.index).shift(1)          # rate at the start of the month
    carry = (ic - iu) / 1200.0
    hr = (gmp_r + carry).where(ic.notna() & iu.notna())
    first = hr.first_valid_index()
    if first is None: continue
    hr = hr.loc[first:]
    if hr.isna().any():
        # fill isolated gaps in the rate with the previous value (logged)
        n = int(hr.isna().sum()); LOG.setdefault("rate_gaps_filled", {})[c] = n
        ic2, iu2 = RATE[c].reindex(M.index).ffill().shift(1), RATE_US[c].reindex(M.index).ffill().shift(1)
        hr = (gmp_r + (ic2 - iu2) / 1200.0).loc[first:]
    lvl = (1 + hr).cumprod(); lvl.loc[first - pd.offsets.MonthEnd(1)] = 1.0
    HEDGED_L[c] = lvl.sort_index()
    bl = (1 + RATE[c].reindex(M.index).ffill().shift(1).loc[first:] / 1200.0).cumprod(); bl.loc[first - pd.offsets.MonthEnd(1)] = 1.0
    LOCAL_BILL_L[c] = bl.sort_index()
usd_bill = (1 + TB3.reindex(M.index).shift(1).loc[gmp_r.index[0]:] / 1200.0).cumprod(); usd_bill.loc[pd.Timestamp("1975-12-31")] = 1.0
USD_BILL_L = usd_bill.sort_index()


def dec_to_dec(level):
    l = level[level.index.month == 12].copy(); l.index = l.index.year; return np.log(l).diff()


R_HEDGED = pd.DataFrame({c: dec_to_dec(HEDGED_L[c]) for c in HEDGED_L}).reindex(YEARS)
R_LBILL = pd.DataFrame({c: dec_to_dec(LOCAL_BILL_L[c]) for c in LOCAL_BILL_L}).reindex(YEARS)
R_UBILL = dec_to_dec(USD_BILL_L).reindex(YEARS)
NET_H = R_HEDGED - NEED[R_HEDGED.columns]
NET_LBILL = R_LBILL - NEED[R_LBILL.columns]
NET_UBILL = pd.DataFrame({c: R_UBILL + fx[c].reindex(YEARS) - NEED[c] for c in CC})          # USD bills held unhedged, in national hours
CARRY = R_HEDGED.sub(r_gmp.reindex(YEARS), axis=0)                                          # interest differential earned on the hedge (log, annual)
HEDGE_GAIN = (R_HEDGED - R_LCU[R_HEDGED.columns])                                           # hedged minus unhedged = carry minus FX change

# ------------------------------------------------------------------ 6. statistics
def nw_se(x, lag=1):
    x = np.asarray(x, float); x = x[~np.isnan(x)]; n = len(x)
    if n < 3: return np.nan
    e = x - x.mean(); s = (e @ e) / n
    for k in range(1, lag + 1):
        w = 1 - k / (lag + 1); s += 2 * w * (e[k:] @ e[:-k]) / n
    return float(np.sqrt(max(s, 0) / n))


def windows(x, w):
    x = x.dropna()
    if len(x) < w: return np.nan, np.nan, 0
    s = x.rolling(w).sum().dropna() / w
    return float(s.min()), float((s < 0).mean()), int(len(s))


def weights(avail):
    """GDP (USD, previous year) weights over the countries available each year."""
    W = GUc.shift(1).reindex(avail.index).where(avail)
    return W.div(W.sum(axis=1), axis=0)


def agg(NET, a, b):
    n = NET.loc[a:b]
    w = weights(n.notna() & GUc.shift(1).reindex(n.index).notna())
    return float((w * n).sum(axis=1).mean() * 1000), float(n.mean().median() * 1000)


rows = []
for c in CC:
    u = NET_U[c].dropna(); u = u.loc[Y0:Y1]
    if len(u) == 0: continue
    a, b_ = int(u.index[0]), int(u.index[-1]); yrs = u.index                 # every column of the row is a mean over the same years
    worst10, neg10, n10 = windows(u, 10); worst20, neg20, n20 = windows(u, 20)
    r = {"cc": c, "country": NAMES[c], "from": a, "to": b_, "years": len(u),
         "gmp_lcu": R_LCU[c].loc[yrs].mean() * 1000, "need": NEED[c].loc[yrs].mean() * 1000,
         "net": u.mean() * 1000, "net_se": nw_se(u) * 1000, "net_sd": u.std() * 1000, "share_pos": (u > 0).mean(),
         "term_world": TERM_W.loc[yrs].mean() * 1000, "term_rel": TERM_REL[c].loc[yrs].mean() * 1000,
         "cum_ratio": float(np.exp(u.sum())), "worst10": worst10 * 1000 if n10 else np.nan, "neg10": neg10, "worst20": worst20 * 1000 if n20 else np.nan, "neg20": neg20,
         "usd_bill_net": NET_UBILL[c].loc[yrs].mean() * 1000}
    assert abs(r["gmp_lcu"] - r["need"] - r["net"]) < 1e-6 and abs(r["term_world"] + r["term_rel"] - r["net"]) < 1e-6
    if c in NET_H:
        h = NET_H[c].dropna(); h = h.loc[max(a, int(h.index[0]) if len(h) else 9999):b_]
        h = h[h.index.isin(yrs)]                                          # hedged and unhedged compared over identical years
        if len(h) >= 10:
            ha = int(h.index[0]); hy = h.index; uu = u.loc[hy]
            r.update({"hedge_from": ha, "hedge_years": len(h), "net_h": h.mean() * 1000, "net_h_sd": h.std() * 1000,
                      "net_u_same": uu.mean() * 1000, "net_u_same_sd": uu.std() * 1000,
                      "hedge_minus_unhedged": (h - uu).mean() * 1000, "hmu_se": nw_se(h - uu) * 1000,
                      "carry": CARRY[c].loc[hy].mean() * 1000, "fx_change": fx[c].loc[hy].mean() * 1000, "hedge_gain": HEDGE_GAIN[c].loc[hy].mean() * 1000,
                      "local_bill_net": NET_LBILL[c].loc[hy].mean() * 1000, "rate_source": RATE_SRC[c]})
            assert abs(r["net_h"] - r["net_u_same"] - r["hedge_minus_unhedged"]) < 1e-6 and abs(r["carry"] - r["fx_change"] - r["hedge_gain"]) < 1e-6 and abs(r["hedge_gain"] - r["hedge_minus_unhedged"]) < 1e-6
    rows.append(r)
T1 = pd.DataFrame(rows).set_index("cc")
T1.round(4).to_csv(os.path.join(OUT, "table1_countries.csv"))

# balanced panel (full 1976-2025) and period table
FULL = [c for c in CC if T1.loc[c, "from"] == Y0 and T1.loc[c, "to"] == Y1]
LOG["balanced_panel"] = FULL
prow = []
for a, b_ in PERIODS:
    gw, med = agg(NET_U, a, b_); gwf, medf = agg(NET_U[FULL], a, b_)
    gwx, medx = agg(TERM_REL, a, b_)
    prow.append({"period": f"{a}-{b_}", "gmp_usd": r_gmp.loc[a:b_].mean() * 1000, "world_hour": g_wh.loc[a:b_].mean() * 1000,
                 "gmp_in_world_hours": (r_gmp - g_wh).loc[a:b_].mean() * 1000,
                 "net_gdp_weighted": gw, "net_median": med, "net_gdp_weighted_balanced": gwf, "net_median_balanced": medf,
                 "rel_hour_gdp_weighted": gwx, "rel_hour_median": medx,
                 "share_countries_positive": float((NET_U.loc[a:b_].mean().dropna() > 0).mean()), "n_countries": int(NET_U.loc[a:b_].notna().any().sum()),
                 "n_countries_positive": int((NET_U.loc[a:b_].mean().dropna() > 0).sum()),
                 "us_net": NET_U["US"].loc[a:b_].mean() * 1000, "jp_net": NET_U["JP"].loc[a:b_].mean() * 1000})
T2 = pd.DataFrame(prow).set_index("period"); T2.round(3).to_csv(os.path.join(OUT, "table2_periods.csv"))

# hedged vs unhedged, period table on the common hedge sample
hrow = []
HC = [c for c in T1.index if "net_h" in T1 and pd.notna(T1.loc[c, "net_h"])]
for a, b_ in PERIODS:
    sub_h, sub_u = NET_H[HC].loc[a:b_], NET_U[HC].loc[a:b_].where(NET_H[HC].loc[a:b_].notna())
    d = (sub_h - sub_u); have = d.notna().any(); have = have[have].index          # shares are over the countries with data in the period
    sub_h, sub_u, d = sub_h[have], sub_u[have], d[have]
    hrow.append({"period": f"{a}-{b_}", "n_countries": int(len(have)),
                 "net_unhedged_median": sub_u.mean().median() * 1000, "net_hedged_median": sub_h.mean().median() * 1000,
                 "hedged_minus_unhedged_median": d.mean().median() * 1000, "share_hedge_higher": float((d.mean() > 0).mean()), "n_hedge_higher": int((d.mean() > 0).sum()),
                 "sd_unhedged_median": sub_u.std().median() * 1000, "sd_hedged_median": sub_h.std().median() * 1000,
                 "share_hedge_lower_sd": float((sub_h.std() < sub_u.std()).mean()), "n_hedge_lower_sd": int((sub_h.std() < sub_u.std()).sum())})
T3 = pd.DataFrame(hrow).set_index("period"); T3.round(3).to_csv(os.path.join(OUT, "table3_hedge_periods.csv"))

# world-hour consistency: GDP-weighted national hour in USD vs CC-WH
avail = g_nat_usd.reindex(YEARS).notna()
w = weights(avail)
agg_nat_usd = (w * g_nat_usd.reindex(YEARS)).sum(axis=1)
chk = pd.DataFrame({"gdp_weighted_national_hour_usd": agg_nat_usd, "world_hour_dec_to_dec": g_wh,
                    "world_hour_annual_avg": np.log(wh.groupby(wh.index.year).mean()).diff().reindex(YEARS)}).loc[Y0:Y1]
chk.round(5).to_csv(os.path.join(OUT, "check_world_hour_vs_panel.csv"))
LOG["world_hour_check"] = {"corr_dec": round(float(chk.iloc[:, 0].corr(chk.iloc[:, 1])), 3), "corr_avg": round(float(chk.iloc[:, 0].corr(chk.iloc[:, 2])), 3),
                           "mean_diff_pp_dec": round(float((chk.iloc[:, 0] - chk.iloc[:, 1]).mean() * 100), 3), "mean_diff_pp_avg": round(float((chk.iloc[:, 0] - chk.iloc[:, 2]).mean() * 100), 3)}

# ------------------------------------------------------------------ 7. robustness
def summary(NET, label):
    gw, med = agg(NET, Y0, Y1); gwf, medf = agg(NET[[c for c in FULL if c in NET]], Y0, Y1)
    per = NET.loc[Y0:Y1].mean() * 1000
    return {"variant": label, "gdp_weighted": gw, "median": med, "gdp_weighted_balanced": gwf, "median_balanced": medf,
            "share_positive": float((per > 0).mean()), "US": per.get("US", np.nan), "JP": per.get("JP", np.nan), "DE": per.get("DE", np.nan), "CH": per.get("CH", np.nan)}


rob = [summary(NET_U, "Baseline: Dec-to-Dec market returns, calendar-year national hour")]
rob.append(summary(R_LCU - g_nat_dec.reindex(YEARS), "National hour interpolated to Dec-to-Dec (note 4 variant)"))
R_LCU_AVG = pd.DataFrame({c: r_gmp + fx_avg[c].reindex(YEARS) for c in CC})
rob.append(summary(R_LCU_AVG - NEED, "Annual-average exchange rate instead of December"))
# GDP per worker (no hours): need = growth of LCU GDP / persons engaged
EMP = pd.DataFrame({c: pwt(f"EMPENG{c}A148NRUG") for c in CC})
for c in CC:
    e = LF[ISO[c]].dropna()
    for y in (2024, 2025):
        if y not in EMP[c].dropna().index and (y - 1) in EMP[c].dropna().index and y in e.index: EMP.loc[y, c] = EMP.loc[y - 1, c] * e.loc[y] / e.loc[y - 1]
g_pw = np.log(NGc / EMP.reindex(NGc.index)).diff().reindex(YEARS)
rob.append(summary(R_LCU - g_pw, "GDP per worker instead of GDP per hour"))
# excluding the 2024-25 labour-force extension (sample to 2023)
rob.append(dict(summary(NET_U.loc[:2023], "Sample to 2023 (no labour-force extension)"), **{}))
# PPP-free check: equal weights
eq_gw = float(NET_U.loc[Y0:Y1].mean(axis=1).mean() * 1000)
rob.append({"variant": "Equal country weights", "gdp_weighted": eq_gw, "median": rob[0]["median"], "gdp_weighted_balanced": float(NET_U[FULL].loc[Y0:Y1].mean(axis=1).mean() * 1000), "median_balanced": rob[0]["median_balanced"], "share_positive": rob[0]["share_positive"], "US": rob[0]["US"], "JP": rob[0]["JP"], "DE": rob[0]["DE"], "CH": rob[0]["CH"]})
T4 = pd.DataFrame(rob).set_index("variant"); T4.round(2).to_csv(os.path.join(OUT, "table4_robustness.csv"))

# ------------------------------------------------------------------ 8. monthly series for figures (national hour placed at December, log-interpolated)
NH_m = {}
for c in CC:
    s = NH[c].dropna(); idx = pd.to_datetime([f"{y}-12-31" for y in s.index])
    m = pd.Series(np.log(s.values), index=idx).reindex(pd.date_range("1975-12-31", f"{Y1}-12-31", freq="ME")).interpolate(limit_area="inside")
    NH_m[c] = np.exp(m)
NH_m = pd.DataFrame(NH_m)
GMP_LCU_m = pd.DataFrame({c: GMP_L.reindex(NH_m.index) * FX[c].reindex(NH_m.index) for c in CC})
GMP_NAT_m = (GMP_LCU_m / NH_m)
GMP_NAT_m = GMP_NAT_m / GMP_NAT_m.loc["1975-12-31"] * 100
GMP_NAT_m.round(4).to_csv(os.path.join(OUT, "gmp_in_national_hours_monthly.csv"))
# hedged level in LCU: equal to the unhedged GMP in LCU on the hedge start date, then grown with the hedged return; same base as GMP_NAT_m
BASE = GMP_LCU_m.loc["1975-12-31"] / NH_m.loc["1975-12-31"] / 100
HED_NAT_m = {}
for c in HEDGED_L:
    t0 = HEDGED_L[c].index[0]
    HED_NAT_m[c] = HEDGED_L[c].reindex(NH_m.index) * GMP_LCU_m[c].loc[t0] / NH_m[c] / BASE[c]
HED_NAT_m = pd.DataFrame(HED_NAT_m)
HED_NAT_m.round(4).to_csv(os.path.join(OUT, "gmp_hedged_in_national_hours_monthly.csv"))
# annual panels
NET_U.round(6).to_csv(os.path.join(OUT, "net_unhedged_annual.csv")); NET_H.round(6).to_csv(os.path.join(OUT, "net_hedged_annual.csv"))
pd.DataFrame({"gmp_usd": r_gmp, "world_hour": g_wh, "usd_bill": R_UBILL}).round(6).to_csv(os.path.join(OUT, "annual_world.csv"))
g_nat.loc[Y0:Y1].round(6).to_csv(os.path.join(OUT, "national_hour_growth_annual.csv")); NH_usd.loc[1975:Y1].round(4).to_csv(os.path.join(OUT, "national_hour_usd_level_annual.csv"))
fx.loc[Y0:Y1].round(6).to_csv(os.path.join(OUT, "fx_dec_to_dec_annual.csv"))

# ------------------------------------------------------------------ 9. headline numbers
full = T1.loc[FULL]
num = {
    "n_countries": int(len(T1)), "n_balanced": len(FULL), "balanced": FULL,
    "gmp_usd_1976_2025": round(float(r_gmp.mean() * 1000), 1), "world_hour_1976_2025": round(float(g_wh.mean() * 1000), 1),
    "gmp_in_world_hours_1976_2025": round(float((r_gmp - g_wh).mean() * 1000), 1),
    "net_gdp_weighted": round(T2.loc["1976-2025", "net_gdp_weighted"], 1), "net_median": round(T2.loc["1976-2025", "net_median"], 1),
    "net_gdp_weighted_balanced": round(T2.loc["1976-2025", "net_gdp_weighted_balanced"], 1), "net_median_balanced": round(T2.loc["1976-2025", "net_median_balanced"], 1),
    "n_positive": int((T1["net"] > 0).sum()), "n_negative": int((T1["net"] <= 0).sum()),
    "n_sig_pos": int(((T1["net"] - 1.645 * T1["net_se"]) > 0).sum()), "n_sig_neg": int(((T1["net"] + 1.645 * T1["net_se"]) < 0).sum()),
    "best": T1.sort_values("net").iloc[-1][["country", "net", "from"]].to_dict(), "worst": T1.sort_values("net").iloc[0][["country", "net", "from"]].to_dict(),
    "balanced_min": full.sort_values("net").iloc[0][["country", "net"]].to_dict(), "balanced_max": full.sort_values("net").iloc[-1][["country", "net"]].to_dict(),
    "US": T1.loc["US"].to_dict(), "JP": T1.loc["JP"].to_dict(), "DE": T1.loc["DE"].to_dict(), "CH": T1.loc["CH"].to_dict(), "GB": T1.loc["GB"].to_dict(), "KR": T1.loc["KR"].to_dict(), "CN": T1.loc["CN"].to_dict(),
    "rel_term_share_of_variance": round(float(T1["term_rel"].var() / (T1["net"].var())), 3),
    "corr_net_vs_rel": round(float(T1["net"].corr(T1["term_rel"])), 3),
    "hedge_n": int(T3.loc["1976-2025", "n_countries"]), "hedge_share_higher": round(float(T3.loc["1976-2025", "share_hedge_higher"]), 3),
    "hedge_share_lower_sd": round(float(T3.loc["1976-2025", "share_hedge_lower_sd"]), 3),
    "hedge_minus_unhedged_median": round(float(T3.loc["1976-2025", "hedged_minus_unhedged_median"]), 1),
    "sd_unhedged_median": round(float(T3.loc["1976-2025", "sd_unhedged_median"]), 1), "sd_hedged_median": round(float(T3.loc["1976-2025", "sd_hedged_median"]), 1),
    "world_hour_check": LOG["world_hour_check"],
    "uip": (lambda d: {"n": int(len(d)), "corr_carry_fx": round(float(d["carry"].corr(d["fx_change"])), 3),
                       "slope_fx_on_carry": round(float(np.polyfit(d["carry"], d["fx_change"], 1)[0]), 3),
                       "corr_gain_carry": round(float(d["hedge_gain"].corr(d["carry"])), 3),
                       "n_gain_pos": int((d["hedge_gain"] > 0).sum()), "n_gain_sig": int(((d["hedge_gain"].abs() - 1.645 * d["hmu_se"]) > 0).sum()),
                       "sig_list": d[(d["hedge_gain"].abs() - 1.645 * d["hmu_se"]) > 0]["country"].tolist(),
                       "n_sd_lower": int((d["net_h_sd"] < d["net_u_same_sd"]).sum()),
                       "low_rate": d[d["carry"] < 0]["country"].tolist(), "low_rate_gain_median": round(float(d[d["carry"] < 0]["hedge_gain"].median()), 1),
                       "high_rate_gain_median": round(float(d[d["carry"] >= 0]["hedge_gain"].median()), 1)})(T1.dropna(subset=["net_h"]).drop(index="US")),
    "n_countries_net_nonpositive": T1[T1["net"] <= 0]["country"].tolist(),
    "usd_bill_positive": T1[T1["usd_bill_net"] > 0].sort_values("usd_bill_net", ascending=False)["country"].tolist(),
    "usd_bill_positive_n": int((T1["usd_bill_net"] > 0).sum()),
    "local_bill_positive_n": int((T1["local_bill_net"] > 0).sum()), "local_bill_n": int(T1["local_bill_net"].notna().sum()),
    "local_bill_beats_gmp": T1[T1["local_bill_net"] > T1["net_u_same"]].sort_values("local_bill_net", ascending=False)["country"].tolist(),
    "low_rate_lost": T1[(T1["carry"] < 0) & (T1["hedge_gain"] < 0)].drop(index="US", errors="ignore")["country"].tolist(),
    "low_rate_gained": T1[(T1["carry"] < 0) & (T1["hedge_gain"] >= 0)].drop(index="US", errors="ignore")["country"].tolist(),
    "high_rate_lost": T1[(T1["carry"] >= 0) & (T1["hedge_gain"] < 0)].drop(index="US", errors="ignore")["country"].tolist(),
    "high_rate_n": int(((T1["carry"] >= 0) & T1["hedge_gain"].notna()).drop(index="US", errors="ignore").sum()),
    "p2_positive_n": int(T2.loc["1982-2000", "n_countries_positive"]), "p2_n": int(T2.loc["1982-2000", "n_countries"]),
    "p1_positive_n": int(T2.loc["1976-1981", "n_countries_positive"]),
    "n_countries_net_below10": T1[T1["net"] < 10]["country"].tolist(),
    "cum_ratio_median_balanced": round(float(full["cum_ratio"].median()), 2), "cum_ratio_min_balanced": round(float(full["cum_ratio"].min()), 2), "cum_ratio_max_balanced": round(float(full["cum_ratio"].max()), 2),
    "net_sd_median": round(float(T1["net_sd"].median()), 1), "share_pos_median": round(float(T1["share_pos"].median()), 3),
    "world_term_sd": round(float((r_gmp - g_wh).std() * 1000), 1), "rel_term_sd_median": round(float(TERM_REL.loc[Y0:Y1].std().median() * 1000), 1),
    "corr_world_rel_median": round(float(pd.Series({c: TERM_W.corr(TERM_REL[c]) for c in CC}).median()), 3),
    "worst10_median": round(float(T1["worst10"].median()), 1), "neg20_countries_any": int((T1["neg20"] > 0).sum()), "neg10_median": round(float(T1["neg10"].median()), 3),
}
json.dump(num, open(os.path.join(OUT, "numbers.json"), "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))

# ------------------------------------------------------------------ 10. figures
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 8.5, "axes.spines.top": False, "axes.spines.right": False})
# fig 1: GMP in national hours, selected countries, log scale
sel = ["US", "JP", "DE", "GB", "CH", "KR", "CN", "IN", "BR", "TR"]
fig, ax = plt.subplots(figsize=(8, 4.6))
for c in sel:
    s = GMP_NAT_m[c].dropna(); ax.plot(s.index, s.values, lw=1.1 if c in ("US", "JP") else 0.8, label=f"{NAMES[c]} ({s.iloc[-1]:.0f})")
ax.set_yscale("log"); ax.axhline(100, color="k", lw=0.5, ls=":")
ax.set_title("The GMP held unhedged, measured in each country's own hours (December 1975 = 100; end value in brackets)", loc="left", fontsize=9)
ax.legend(fontsize=7.5, frameon=False, ncol=2); ax.set_ylabel("index, log scale"); fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig1_gmp_in_national_hours.png"), dpi=160); plt.close(fig)
# fig 2: country bars, net split into the world term and the relative-hour term
t = T1.sort_values("net")
fig, ax = plt.subplots(figsize=(8, 7.2))
y = np.arange(len(t))
ax.barh(y, t["term_world"], color="#999", label="GMP over the world hour (same for all)")
ax.barh(y, t["term_rel"], left=t["term_world"], color=np.where(t["term_rel"] >= 0, "#7a5c00", "#8c4a3c"), label="world hour over the country's own hour")
ax.scatter(t["net"], y, color="k", s=10, zorder=3, label="net, hours a year per 1,000")
ax.set_yticks(y); ax.set_yticklabels([f"{NAMES[c]} ({int(t.loc[c,'from'])})" if t.loc[c, "from"] > Y0 else NAMES[c] for c in t.index], fontsize=7.5)
ax.axvline(0, color="k", lw=0.6); ax.legend(fontsize=7.5, frameon=False, loc="lower right")
ax.set_title("The GMP held unhedged, net of the growth of the country's own hour, hours a year per 1,000, 1976-2025", loc="left", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig2_country_net.png"), dpi=160); plt.close(fig)
# fig 3: hedged vs unhedged, same sample per country
th = T1.dropna(subset=["net_h"]).sort_values("net_u_same")
fig, axs = plt.subplots(1, 2, figsize=(8, 6.4), sharey=True)
y = np.arange(len(th))
axs[0].scatter(th["net_u_same"], y, color="#555", s=14, label="unhedged"); axs[0].scatter(th["net_h"], y, color="#7a5c00", s=14, marker="s", label="hedged (USD leg sold forward)")
axs[0].axvline(0, color="k", lw=0.6); axs[0].set_yticks(y); axs[0].set_yticklabels([f"{NAMES[c]} ({int(th.loc[c,'hedge_from'])})" for c in th.index], fontsize=7.5)
axs[0].set_title("Mean net, hours a year per 1,000", loc="left", fontsize=9); axs[0].legend(fontsize=7.5, frameon=False, loc="lower right")
axs[1].scatter(th["net_u_same_sd"], y, color="#555", s=14); axs[1].scatter(th["net_h_sd"], y, color="#7a5c00", s=14, marker="s")
axs[1].set_title("Standard deviation of annual net, per 1,000", loc="left", fontsize=9)
fig.suptitle("The GMP in each country's own hours, hedged and unhedged, from each country's rate data start (in brackets) to 2025", x=0.01, ha="left", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig3_hedged_vs_unhedged.png"), dpi=160); plt.close(fig)
# fig 4: the identity for Japan and the United States: GMP in world hours, relative hour, GMP in national hours (cumulative)
fig, axs = plt.subplots(1, 2, figsize=(8, 3.8), sharey=True)
for ax, c in zip(axs, ["JP", "US"]):
    cw = np.exp((r_gmp - g_wh).cumsum()); rel = np.exp(TERM_REL[c].cumsum()); nat = np.exp(NET_U[c].cumsum())
    ax.plot(cw.index, cw.values, color="#999", label="GMP in world hours"); ax.plot(rel.index, rel.values, color="#8c4a3c", label="world hour / own hour"); ax.plot(nat.index, nat.values, color="k", lw=1.3, label="GMP in own hours")
    ax.set_yscale("log"); ax.axhline(1, color="k", lw=0.5, ls=":"); ax.set_title(NAMES[c], loc="left", fontsize=9)
axs[0].legend(fontsize=7.5, frameon=False)
fig.suptitle("GMP in own hours = GMP in world hours x (world hour / own hour), cumulative from end-1975 (log scale)", x=0.01, ha="left", fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig4_identity_jp_us.png"), dpi=160); plt.close(fig)

LOG["hours_note"] = HOURS_NOTE
LOG["national_hour_first_year"] = {c: int(g_nat[c].first_valid_index()) for c in CC}
json.dump(LOG, open(os.path.join(OUT, "build_log.json"), "w"), indent=1, default=str)
print(json.dumps(num, indent=1, default=str))
print(T2.round(1).to_string()); print(T3.round(2).to_string()); print(T4.round(1).to_string())
print(T1[["country", "from", "net", "net_se", "term_world", "term_rel", "cum_ratio", "worst10", "neg20"]].sort_values("net").round(1).to_string())
print(T1.dropna(subset=["net_h"])[["country", "hedge_from", "net_u_same", "net_h", "hedge_minus_unhedged", "hmu_se", "net_u_same_sd", "net_h_sd", "carry", "fx_change", "local_bill_net", "rate_source"]].round(1).to_string())
print("max |annual log change| of national hour in USD:", {k: v for k, v in sorted(LOG["max_abs_annual_log_change_nat_hour_usd"].items(), key=lambda kv: -kv[1])[:10]})
print(NH_usd.loc[[1976, 1980, 1985, 1990, 1995, 2000, 2010, 2020, 2025], ["AR", "BR", "MX", "TR", "RU", "PL", "IL", "CN", "SA", "US", "JP"]].round(2).to_string())
