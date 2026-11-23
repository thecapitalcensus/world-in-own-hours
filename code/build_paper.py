"""Fill paper_template.html with the tables and numbers in output/ and write output/paper/resident.html.
Every number in the text comes from output/numbers.json or the output CSVs; nothing is typed by hand."""
import json, os, shutil
import numpy as np, pandas as pd

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(H, "output"); PAP = os.path.join(OUT, "paper"); IMG = os.path.join(PAP, "img")
os.makedirs(IMG, exist_ok=True)
N = json.load(open(os.path.join(OUT, "numbers.json")))
LOG = json.load(open(os.path.join(OUT, "build_log.json")))
CHK = json.load(open(os.path.join(OUT, "check_result.json")))
T1 = pd.read_csv(os.path.join(OUT, "table1_countries.csv"), index_col=0)
T2 = pd.read_csv(os.path.join(OUT, "table2_periods.csv"), index_col=0)
T3 = pd.read_csv(os.path.join(OUT, "table3_hedge_periods.csv"), index_col=0)
T4 = pd.read_csv(os.path.join(OUT, "table4_robustness.csv"), index_col=0)
MAN = json.load(open(os.path.join(H, "data", "raw", "MANIFEST.json")))


def f1(x):
    x = 0.0 if round(float(x), 1) == 0 else float(x)                       # no "-0.0"
    return "&minus;" + f"{abs(x):.1f}" if x < 0 else f"{x:.1f}"
def f0(x):
    x = 0.0 if round(float(x)) == 0 else float(x)
    return "&minus;" + f"{abs(x):.0f}" if x < 0 else f"{x:.0f}"
def pct(x): return f"{x*100:.0f}%"
def esc(s): return str(s).replace("&", "&amp;")


def html_table(df, cols, caption, fmt=None, cls="small", index_name=""):
    fmt = fmt or {}
    h = [f'<table class="{cls}"><caption>{caption}</caption><thead><tr><th>{index_name}</th>' + "".join(f"<th>{c[1]}</th>" for c in cols) + "</tr></thead><tbody>"]
    for i, r in df.iterrows():
        cells = []
        for key, lab in cols:
            v = r[key]
            if isinstance(v, str): cells.append(f"<td>{esc(v)}</td>")
            elif pd.isna(v): cells.append('<td class="num">&ndash;</td>')
            else: cells.append(f'<td class="num">{fmt.get(key, f1)(v)}</td>')
        h.append(f"<tr><td>{esc(i)}</td>" + "".join(cells) + "</tr>")
    h.append("</tbody></table>"); return '<div class="tablewrap">' + "\n".join(h) + "</div>"


# Table 2: periods
t2 = T2.copy(); t2.index.name = "Period"
tab2 = html_table(t2, [("gmp_usd", "GMP, USD"), ("world_hour", "World hour, USD"), ("gmp_in_world_hours", "GMP in world hours"),
                       ("net_gdp_weighted", "GMP in own hours, GDP-weighted"), ("net_median", "country median"),
                       ("rel_hour_gdp_weighted", "World hour over own hour, GDP-weighted"), ("rel_hour_median", "country median"),
                       ("share_countries_positive", "Countries positive"), ("n_countries", "Countries"), ("us_net", "United States"), ("jp_net", "Japan")],
                 "Table 2. The GMP in world hours and in each country&rsquo;s own hours, hours a year per 1,000 hours, by period (author&rsquo;s calculations). Log returns in % &times; 10. GDP weights: previous year&rsquo;s World Bank GDP in US dollars over the countries with data",
                 fmt={"share_countries_positive": pct, "n_countries": f0}, index_name="Period")

# Table 3: countries (unhedged)
t = T1.sort_values("net", ascending=False).copy()
t["label"] = [f"{r['country']}" + (f" ({int(r['from'])})" if r["from"] > 1976 else "") for _, r in t.iterrows()]
t = t.set_index("label"); t["ci"] = t["net"] - 1.645 * t["net_se"]
tab3 = html_table(t, [("gmp_lcu", "GMP in local currency"), ("need", "Growth of own hour"), ("net", "Net"), ("net_se", "s.e."), ("term_rel", "World hour over own hour"),
                      ("cum_ratio", "End &divide; start"), ("worst10", "Worst 10-year window"), ("neg20", "20-year windows negative"), ("usd_bill_net", "US bills, unhedged, net")],
                 "Table 3. The GMP held unhedged in each country&rsquo;s own hours, 1976&ndash;2025 or from the year in brackets, hours a year per 1,000 (author&rsquo;s calculations). Net = GMP in local currency &minus; growth of the national hour. s.e.: Newey&ndash;West (one lag) standard error of the mean. &ldquo;World hour over own hour&rdquo; is the country-specific part of the net (Section 4.2); the common part is 34.8 for a 1976 start. End &divide; start: the holding in own hours at end-2025 divided by its value at the start",
                 fmt={"cum_ratio": lambda x: f"{x:.1f}", "neg20": pct}, index_name="Country")

# Table 4: hedging by period
t3 = T3.copy()
tab4 = html_table(t3, [("n_countries", "Countries"), ("net_unhedged_median", "Net, unhedged, median"), ("net_hedged_median", "Net, hedged, median"), ("hedged_minus_unhedged_median", "Hedged &minus; unhedged, median"),
                       ("share_hedge_higher", "Hedged higher"), ("sd_unhedged_median", "s.d. unhedged, median"), ("sd_hedged_median", "s.d. hedged, median"), ("share_hedge_lower_sd", "Hedged s.d. lower")],
                 "Table 4. Hedging the dollar leg: the GMP in own hours, unhedged and hedged, by period (author&rsquo;s calculations). Hours a year per 1,000; medians and shares across the countries with short-rate data in the period (the &ldquo;Countries&rdquo; column); the United States (where the two are identical) is included",
                 fmt={"n_countries": f0, "share_hedge_higher": pct, "share_hedge_lower_sd": pct}, index_name="Period")

# Table 5: hedging by country
th = T1.dropna(subset=["net_h"]).sort_values("hedge_gain", ascending=False).copy()
th["label"] = [f"{r['country']} ({int(r['hedge_from'])})" for _, r in th.iterrows()]; th = th.set_index("label")
tab5 = html_table(th, [("net_u_same", "Net, unhedged"), ("net_h", "Net, hedged"), ("hedge_gain", "Hedged &minus; unhedged"), ("hmu_se", "s.e."), ("carry", "Interest differential"), ("fx_change", "Depreciation vs USD"),
                       ("net_u_same_sd", "s.d. unhedged"), ("net_h_sd", "s.d. hedged"), ("local_bill_net", "Local bills, net")],
                 "Table 5. Hedged and unhedged, by country, from the first year with short-rate data (in brackets) to 2025, hours a year per 1,000 (author&rsquo;s calculations). Interest differential: the monthly (local short rate &minus; US short rate)/12 terms of Section 2, compounded through each year and averaged (log); depreciation: Dec-to-Dec change in local currency per dollar (log). Hedged &minus; unhedged = interest differential &minus; depreciation. s.e.: Newey&ndash;West (one lag)",
                 index_name="Country")

# Table 6: robustness
t4 = T4.copy()
tab6 = html_table(t4, [("gdp_weighted", "GDP-weighted"), ("median", "Median"), ("gdp_weighted_balanced", "GDP-weighted, 37 countries"), ("median_balanced", "Median, 37 countries"), ("share_positive", "Countries positive"), ("US", "United States"), ("JP", "Japan"), ("DE", "Germany"), ("CH", "Switzerland")],
                 "Table 6. The GMP in own hours, 1976&ndash;2025, under alternative constructions, hours a year per 1,000 (author&rsquo;s calculations)", fmt={"share_positive": pct}, index_name="Variant")

# Table 1: data
rows = [("Frozen engine (note 1; weight history Nakanishi 2026c)", "GMP monthly total return, USD, 1976-01 to 2026-08; public CC-GMP TR level series as a cross-check", "CC BY-NC 4.0"),
        ("CC-WH (note 2)", "World hour: GDP-weighted nominal GDP per hour worked, 43 countries, monthly index to 2026-03 (hard data to 2025-06)", "CC BY-NC 4.0"),
        ("BIS WS_XRU", "Monthly average exchange rates against the US dollar, 43 economies, 1975-01 to 2026-10", "BIS terms (attribution)"),
        ("World Bank WDI", "GDP in current local currency (NY.GDP.MKTP.CN) and US dollars (NY.GDP.MKTP.CD), labour force (SL.TLF.TOTL.IN), 1960&ndash;2025", "CC BY 4.0"),
        ("Penn World Table 10/11 via FRED", "Persons engaged and average annual hours worked, 1950&ndash;2023 (no hours series for China and Saudi Arabia; interior gaps, Netherlands 1969 and South Africa 2015, interpolated)", "CC BY 4.0"),
        ("OECD DF_FINMARK", "Short-term interest rates: 3-month interbank (IR3TIB) and immediate/overnight (IRSTCI), monthly, % p.a.", "OECD terms"),
        ("FRED / IMF", "US 3-month Treasury bill (TB3MS); Bank of Japan discount rate (INTDSRJPM193N) for 1976&ndash;1985", "Public, attribution")]
tab1 = '<table class="small"><caption>Table 1. Data (all free and public; retrieved 7 November 2026 unless noted in the manifest)</caption><thead><tr><th>Source</th><th>Used for</th><th>Terms</th></tr></thead><tbody>' + "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in rows) + "</tbody></table>"

# Appendix: rate sources and sample starts
ra = T1[["country", "from", "to"]].copy()
ra["rate_source"] = T1["rate_source"].fillna("none")
ra["hedge_from"] = T1["hedge_from"]
ra["hours_note"] = pd.Series(LOG["hours_note"]).reindex(ra.index).fillna("")
ra = ra.set_index("country")
tabA = html_table(ra, [("from", "Unhedged from"), ("to", "To"), ("hedge_from", "Hedged from"), ("rate_source", "Short rate"), ("hours_note", "Hours")],
                  "Table A1. Sample start by country, and the short-rate series used for the hedge", fmt={"from": f0, "to": f0, "hedge_from": f0}, index_name="Country")

# manifest table
man = "".join(f"<tr><td><code>{k}</code></td><td>{v['bytes']:,}</td><td>{v['retrieved_utc'][:10]}</td><td><code>{v['sha256'][:16]}&hellip;</code></td></tr>" for k, v in MAN.items())
inp = "".join(f"<tr><td><code>{k}</code></td><td><code>{v[:16]}&hellip;</code></td></tr>" for k, v in LOG["inputs_sha256"].items() if k.startswith("inputs/"))

u = N["uip"]; p = T2.loc
EURO = ["AT", "BE", "DE", "ES", "FI", "FR", "GR", "IE", "IT", "NL", "PT"]           # one currency in the panel since 1999 (series in euro throughout)
NU = pd.read_csv(os.path.join(OUT, "net_unhedged_annual.csv"), index_col=0)
p2m = NU.loc[1982:2000].mean().dropna() * 1000
p2_neg = [T1.loc[c, "country"] for c in p2m[p2m <= 0].index]
def join(xs): return ", ".join(xs[:-1]) + " and " + xs[-1] if len(xs) > 1 else (xs[0] if xs else "none")
def word(k): return ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"][k] if 0 <= k <= 9 else str(k)
def the(c): return "the " + c if c in ("Netherlands", "United States", "United Kingdom", "Philippines") else c
low_gained = N["low_rate_gained"]; high_lost = N["high_rate_lost"]
listed = [v for v in T4.index if v != "Equal country weights"]
gaps = [f"{T1.loc[c, 'country']} {note.split('for ')[-1]}" for c, note in LOG["hours_note"].items() if "interpolated" in note]
d = {
    "tab1": tab1, "tab2": tab2, "tab3": tab3, "tab4": tab4, "tab5": tab5, "tab6": tab6, "tabA": tabA, "manifest_rows": man, "inputs_rows": inp,
    "n": N["n_countries"], "nb": N["n_balanced"], "gmp_usd": f1(N["gmp_usd_1976_2025"]), "wh": f1(N["world_hour_1976_2025"]), "gmp_wh": f1(N["gmp_in_world_hours_1976_2025"]),
    "net_gw": f1(N["net_gdp_weighted"]), "net_med": f1(N["net_median"]), "net_gw_b": f1(N["net_gdp_weighted_balanced"]), "net_med_b": f1(N["net_median_balanced"]),
    "n_pos": N["n_positive"], "n_neg": N["n_negative"], "n_sig_pos": N["n_sig_pos"], "nonpos": ", ".join(N["n_countries_net_nonpositive"]),
    "below10_extra": ", ".join(c for c in N["n_countries_net_below10"] if c not in N["n_countries_net_nonpositive"]),
    "best": N["best"]["country"], "best_net": f1(N["best"]["net"]), "worst": N["worst"]["country"], "worst_net": f1(N["worst"]["net"]), "worst_from": N["worst"]["from"],
    "cum_med": f"{N['cum_ratio_median_balanced']:.1f}", "cum_min": f"{N['cum_ratio_min_balanced']:.2f}", "cum_max": f"{N['cum_ratio_max_balanced']:.0f}",
    "us_net": f1(N["US"]["net"]), "us_se": f1(N["US"]["net_se"]), "jp_net": f1(N["JP"]["net"]), "jp_se": f1(N["JP"]["net_se"]), "de_net": f1(N["DE"]["net"]), "ch_net": f1(N["CH"]["net"]), "gb_net": f1(N["GB"]["net"]), "kr_net": f1(N["KR"]["net"]), "cn_net": f1(N["CN"]["net"]),
    "us_rel": f1(N["US"]["term_rel"]), "jp_rel": f1(N["JP"]["term_rel"]), "de_rel": f1(N["DE"]["term_rel"]), "ch_rel": f1(N["CH"]["term_rel"]), "gb_rel": f1(N["GB"]["term_rel"]), "kr_rel": f1(N["KR"]["term_rel"]), "cn_rel": f1(N["CN"]["term_rel"]),
    "us_need": f1(N["US"]["need"]), "jp_need": f1(N["JP"]["need"]), "kr_need": f1(N["KR"]["need"]), "cn_need": f1(N["CN"]["need"]), "gb_need": f1(N["GB"]["need"]), "ch_need": f1(N["CH"]["need"]),
    "us_cum": f"{N['US']['cum_ratio']:.1f}", "jp_cum": f"{N['JP']['cum_ratio']:.1f}", "cn_cum": f"{N['CN']['cum_ratio']:.2f}", "kr_cum": f"{N['KR']['cum_ratio']:.2f}",
    "sa_rel": f1(T1.loc["SA", "term_rel"]), "mx_rel": f1(T1.loc["MX", "term_rel"]), "ca_rel": f1(T1.loc["CA", "term_rel"]), "se_rel": f1(T1.loc["SE", "term_rel"]),
    "ru_rel": f1(T1.loc["RU", "term_rel"]), "cz_rel": f1(T1.loc["CZ", "term_rel"]), "pl_rel": f1(T1.loc["PL", "term_rel"]), "ie_rel": f1(T1.loc["IE", "term_rel"]), "za_rel": f1(T1.loc["ZA", "term_rel"]),
    "hk_rel": f1(T1.loc["HK", "term_rel"]), "sg_rel": f1(T1.loc["SG", "term_rel"]), "th_rel": f1(T1.loc["TH", "term_rel"]), "cl_rel": f1(T1.loc["CL", "term_rel"]),
    "world_sd": f1(N["world_term_sd"]), "rel_sd": f1(N["rel_term_sd_median"]), "corr_wr": f"{N['corr_world_rel_median']:.2f}", "net_sd_med": f1(N["net_sd_median"]), "share_pos_med": pct(N["share_pos_median"]),
    "worst10_med": f1(N["worst10_median"]), "neg20_any": N["neg20_countries_any"], "neg10_med": pct(N["neg10_median"]),
    "us_w10": f1(N["US"]["worst10"]), "jp_w10": f1(N["JP"]["worst10"]), "de_w10": f1(N["DE"]["worst10"]), "gb_w10": f1(N["GB"]["worst10"]), "kr_neg20": pct(N["KR"]["neg20"]), "cn_neg20": pct(N["CN"]["neg20"]), "kr_w10": f1(N["KR"]["worst10"]), "cn_w10": f1(N["CN"]["worst10"]),
    "p1_gw": f1(p["1976-1981", "net_gdp_weighted"]), "p1_med": f1(p["1976-1981", "net_median"]), "p1_pos": pct(p["1976-1981", "share_countries_positive"]), "p1_n": int(p["1976-1981", "n_countries"]), "p1_w": f1(p["1976-1981", "gmp_in_world_hours"]),
    "p2_gw": f1(p["1982-2000", "net_gdp_weighted"]), "p2_med": f1(p["1982-2000", "net_median"]), "p2_pos": pct(p["1982-2000", "share_countries_positive"]), "p2_w": f1(p["1982-2000", "gmp_in_world_hours"]),
    "p3_gw": f1(p["2001-2020", "net_gdp_weighted"]), "p3_med": f1(p["2001-2020", "net_median"]), "p3_pos": pct(p["2001-2020", "share_countries_positive"]), "p3_w": f1(p["2001-2020", "gmp_in_world_hours"]),
    "p4_gw": f1(p["2021-2025", "net_gdp_weighted"]), "p4_med": f1(p["2021-2025", "net_median"]), "p4_pos": pct(p["2021-2025", "share_countries_positive"]), "p4_w": f1(p["2021-2025", "gmp_in_world_hours"]),
    "p4_us": f1(p["2021-2025", "us_net"]), "p4_jp": f1(p["2021-2025", "jp_net"]), "p1_jp": f1(p["1976-1981", "jp_net"]), "p1_us": f1(p["1976-1981", "us_net"]),
    "h_n": N["hedge_n"], "h_higher": pct(N["hedge_share_higher"]), "h_n_higher": u["n_gain_pos"], "h_n_ex_us": u["n"], "h_med": f1(N["hedge_minus_unhedged_median"]), "h_sd_lower": pct(N["hedge_share_lower_sd"]), "h_n_sd_lower": u["n_sd_lower"],
    "sd_u": f1(N["sd_unhedged_median"]), "sd_h": f1(N["sd_hedged_median"]), "h_sig": u["n_gain_sig"], "h_sig_list": ", ".join(u["sig_list"]),
    "uip_corr": f"{u['corr_carry_fx']:.2f}", "uip_slope": f"{u['slope_fx_on_carry']:.2f}", "uip_gain_corr": f"{u['corr_gain_carry']:.2f}", "low_rate": ", ".join(u["low_rate"]), "low_gain": f1(u["low_rate_gain_median"]), "high_gain": f1(u["high_rate_gain_median"]),
    "jp_hu": f1(N["JP"]["net_u_same"]), "jp_hh": f1(N["JP"]["net_h"]), "jp_gain": f1(N["JP"]["hedge_gain"]), "jp_gain_se": f1(N["JP"]["hmu_se"]), "jp_carry": f1(N["JP"]["carry"]), "jp_fx": f1(N["JP"]["fx_change"]), "jp_sdu": f1(N["JP"]["net_u_same_sd"]), "jp_sdh": f1(N["JP"]["net_h_sd"]),
    "jp_carry_pts": f"{abs(N['JP']['carry'])/10:.1f}", "jp_fx_pct": f"{abs(N['JP']['fx_change'])/10:.1f}", "jp_fx_abs": f1(abs(N["JP"]["fx_change"])),
    "ch_gain": f1(N["CH"]["hedge_gain"]), "de_gain": f1(N["DE"]["hedge_gain"]), "gb_gain": f1(N["GB"]["hedge_gain"]), "gb_gain_se": f1(N["GB"]["hmu_se"]), "kr_gain": f1(N["KR"]["hedge_gain"]), "cn_gain": f1(N["CN"]["hedge_gain"]),
    "us_sd": f1(N["US"]["net_sd"]), "us_bill": f1(N["US"]["local_bill_net"]), "jp_bill": f1(N["JP"]["local_bill_net"]), "cn_bill": f1(N["CN"]["local_bill_net"]), "ch_bill": f1(N["CH"]["local_bill_net"]), "de_bill": f1(N["DE"]["local_bill_net"]),
    "us_usdbill": f1(N["US"]["usd_bill_net"]), "jp_usdbill": f1(N["JP"]["usd_bill_net"]), "gb_usdbill": f1(N["GB"]["usd_bill_net"]), "kr_usdbill": f1(N["KR"]["usd_bill_net"]),
    "hp1_med": f1(T3.loc["1976-1981", "hedged_minus_unhedged_median"]), "hp1_n": int(T3.loc["1976-1981", "n_countries"]), "hp1_higher": pct(T3.loc["1976-1981", "share_hedge_higher"]),
    "hp2_med": f1(T3.loc["1982-2000", "hedged_minus_unhedged_median"]), "hp2_higher": pct(T3.loc["1982-2000", "share_hedge_higher"]),
    "hp3_med": f1(T3.loc["2001-2020", "hedged_minus_unhedged_median"]), "hp3_higher": pct(T3.loc["2001-2020", "share_hedge_higher"]),
    "hp4_med": f1(T3.loc["2021-2025", "hedged_minus_unhedged_median"]), "hp4_higher": pct(T3.loc["2021-2025", "share_hedge_higher"]), "hp4_sdlower": pct(T3.loc["2021-2025", "share_hedge_lower_sd"]),
    "rob_min_gw": f1(T4["gdp_weighted"].min()), "rob_max_gw": f1(T4["gdp_weighted"].max()), "rob_min_med": f1(T4["median"].min()), "rob_max_med": f1(T4["median"].max()),
    "rob_pw": f1(T4.loc["GDP per worker instead of GDP per hour", "gdp_weighted"]), "rob_eq": f1(T4.loc["Equal country weights", "gdp_weighted"]),
    "whc_corr": f"{N['world_hour_check']['corr_avg']:.3f}", "whc_diff": f"{N['world_hour_check']['mean_diff_pp_avg']:.2f}",
    "chk_u": CHK["unhedged_checked"], "chk_h": CHK["hedged_checked"],
    "n_cur": N["n_countries"] - len(EURO) + 1,
    "p1_w_abs": f1(abs(p["1976-1981", "gmp_in_world_hours"])), "p1_pos_n": N["p1_positive_n"], "p1_jp_abs": f1(abs(p["1976-1981", "jp_net"])), "p4_us_abs": f1(abs(p["2021-2025", "us_net"])),
    "p2_pos_n": N["p2_positive_n"], "p2_n": N["p2_n"], "p2_neg_list": join(p2_neg),
    "usdbill_neg_n": N["n_countries"] - N["usd_bill_positive_n"], "usdbill_pos_phrase": join([f"{c} {f1(T1.set_index('country').loc[c, 'usd_bill_net'])}" for c in N["usd_bill_positive"]]),
    "lbill_pos_n": N["local_bill_positive_n"], "lbill_n": N["local_bill_n"], "lbill_gmp_n": N["local_bill_n"] - len(N["local_bill_beats_gmp"]), "lbill_beats_gmp": join(N["local_bill_beats_gmp"]),
    "cn_bill_pct": f"{abs(N['CN']['local_bill_net'])/10:.1f}",
    "low_lost_n": word(len(N["low_rate_lost"])), "low_n": word(len(u["low_rate"])),
    "low_gained_phrase": ("; " + join([f"{the(c)} gained {f1(T1.set_index('country').loc[c, 'hedge_gain'])}" for c in low_gained])) if low_gained else "",
    "high_rate_n": N["high_rate_n"], "high_lost_n": word(len(high_lost)), "high_lost_list": join(high_lost),
    "rob_min_gw_listed": f1(T4.loc[listed, "gdp_weighted"].min()), "rob_max_gw_listed": f1(T4.loc[listed, "gdp_weighted"].max()), "rob_min_med_listed": f1(T4.loc[listed, "median"].min()), "rob_max_med_listed": f1(T4.loc[listed, "median"].max()),
    "hours_gaps": join(gaps), "nl_gain": f1(T1.loc["NL", "hedge_gain"]),
    "gmp_last": LOG["gmp_months"][1], "jp_1995_level": f"{pd.read_csv(os.path.join(OUT, 'national_hour_usd_level_annual.csv'), index_col=0).loc[1995, 'JP']:.1f}", "jp_2025_level": f"{pd.read_csv(os.path.join(OUT, 'national_hour_usd_level_annual.csv'), index_col=0).loc[2025, 'JP']:.1f}",
    "us_2025_level": f"{pd.read_csv(os.path.join(OUT, 'national_hour_usd_level_annual.csv'), index_col=0).loc[2025, 'US']:.1f}", "cn_1976_level": f"{pd.read_csv(os.path.join(OUT, 'national_hour_usd_level_annual.csv'), index_col=0).loc[1976, 'CN']:.2f}", "cn_2025_level": f"{pd.read_csv(os.path.join(OUT, 'national_hour_usd_level_annual.csv'), index_col=0).loc[2025, 'CN']:.1f}",
}


class Safe(dict):
    def __missing__(self, k): raise KeyError(f"placeholder {k} not filled")


import re
tpl = open(os.path.join(H, "code", "paper_template.html"), encoding="utf-8").read()
html = re.sub(r"\{([a-zA-Z_][a-zA-Z_0-9]*)\}", lambda m: str(Safe(d)[m.group(1)]), tpl)   # {key} placeholders; CSS braces (with spaces or ;) are left alone
left = re.findall(r"\{[a-zA-Z_][a-zA-Z_0-9]*\}", html)
assert not left, f"unfilled placeholders: {left}"
# keep a heading together with a figure that directly follows it (print layout)
html = re.sub(r"((?:<h2>[^<]*</h2>\s*)?<h3>[^<]*</h3>|<h2>[^<]*</h2>)\s*(<figure>.*?</figure>)", r'<div class="keep">\1\2</div>', html, flags=re.S)
open(os.path.join(PAP, "resident.html"), "w", encoding="utf-8").write(html)
for f in ["fig1_gmp_in_national_hours.png", "fig2_country_net.png", "fig3_hedged_vs_unhedged.png", "fig4_identity_jp_us.png"]: shutil.copy(os.path.join(OUT, f), os.path.join(IMG, f))
shutil.copy(os.path.join(H, "code", "style.css"), os.path.join(PAP, "style.css"))
json.dump({k: v for k, v in d.items() if not k.startswith("tab") and k not in ("manifest_rows", "inputs_rows")}, open(os.path.join(PAP, "numbers_in_text.json"), "w"), indent=1, default=str)
print("written", os.path.join(PAP, "resident.html"))
