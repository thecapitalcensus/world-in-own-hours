"""Download the public inputs for note 5 into data/raw/ and record URL, UTC time and SHA-256 in data/raw/MANIFEST.json.

Inputs (all free and public):
  BIS WS_XRU      monthly average US-dollar exchange rates, 43 economies, 1975-01 onward
  OECD DF_FINMARK IR3TIB (3-month interbank) and IRSTCI (immediate / overnight) rates, monthly, % p.a.
  FRED            TB3MS (US 3-month Treasury bill), INTDSRJPM193N (Bank of Japan discount rate, IMF)

The frozen-engine and world-hour files, the Penn World Table copies (via FRED) and the World Bank tables are copied
from the earlier notes' public repositories into inputs/ and are listed in build_log.json by the build script.

Run: python3 code/fetch.py
"""
import hashlib, json, os, subprocess, sys, time

H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(H, "data", "raw"); os.makedirs(RAW, exist_ok=True)

CC2 = "AR+AT+AU+BE+BR+CA+CH+CL+CN+CO+CZ+DE+DK+ES+FI+FR+GB+GR+HK+HU+ID+IE+IL+IN+IT+JP+KR+MX+MY+NL+NO+NZ+PH+PL+PT+RU+SA+SE+SG+TH+TR+US+ZA"
CC3 = "ARG+AUT+AUS+BEL+BRA+CAN+CHE+CHL+CHN+COL+CZE+DEU+DNK+ESP+FIN+FRA+GBR+GRC+HKG+HUN+IDN+IRL+ISR+IND+ITA+JPN+KOR+MEX+MYS+NLD+NOR+NZL+PHL+POL+PRT+RUS+SAU+SWE+SGP+THA+TUR+USA+ZAF"

FILES = {
    "bis_xru_m.csv": f"https://stats.bis.org/api/v1/data/WS_XRU/M.{CC2}..A?format=csv&startPeriod=1975-01",
    "oecd_IR3TIB.csv": f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/{CC3}.M.IR3TIB.PA.....?startPeriod=1960-01&format=csvfilewithlabels",
    "oecd_IRSTCI.csv": f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_STES@DF_FINMARK,4.0/{CC3}.M.IRSTCI.PA.....?startPeriod=1960-01&format=csvfilewithlabels",
    "fred_TB3MS.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=TB3MS",
    "fred_INTDSRJPM193N.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=INTDSRJPM193N",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


def main(refresh=True):
    man = {}
    for name, url in FILES.items():
        p = os.path.join(RAW, name)
        if refresh or not os.path.exists(p):
            rc = subprocess.run(["curl", "-sSL", "--retry", "3", "-A", "capital-census-note5/1.0", "-o", p, url]).returncode
            if rc != 0 or os.path.getsize(p) < 100: sys.exit(f"download failed: {name}")
            t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        else:
            t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(p)))
        man[name] = {"url": url, "retrieved_utc": t, "bytes": os.path.getsize(p), "sha256": sha(p)}
        print(f"{name:28s} {man[name]['bytes']:>10,d} bytes  {man[name]['sha256'][:16]}")
    json.dump(man, open(os.path.join(RAW, "MANIFEST.json"), "w"), indent=1)


if __name__ == "__main__":
    main(refresh="--refresh" in sys.argv)   # default: download only what is missing; --refresh re-downloads everything
