"""Brazil (B3) prototype panel from CVM dados abertos + B3 COTAHIST.

Round 5 data-expansion prototype (no return backtest). Builds the four value_sn
legs (bm, ep, sp, ey) for a small sample of Brazilian stocks at month-ends, using
the same definitions as core/pit_panel.py::value_ratios:

  bm = parent equity / mcap (equity > 0)        BPP 2.03 - 2.03.09
  ep = TTM parent net income / mcap             DRE 3.11.01 (fallback 3.11)
  sp = TTM revenue / mcap                       DRE 3.01
  ey = TTM EBIT / EV, EV = mcap + debt - cash   DRE 3.05; BPP 2.01.04+2.02.01; BPA 1.01.01+1.01.02

Point in time: a statement is usable from its CVM receipt date (DT_RECEB in the
itr/dfp index file), not the period end. TTM = YTD_P + FY(y-1) - YTD(P-4),
nominal BRL (Brazil does not apply IAS 29). Market cap = ON shares x ON close +
PN shares x PN close, shares net of treasury from composicao_capital.

Sources:
  CVM  https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{ITR,DFP}/DADOS/  (Cloudflare
       blocks some IPs; falls back to the web.archive.org id_ copy of the same file)
  B3   https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP

Usage: python scripts/fetch_cvm_brazil.py --year 2024 --out scratch/cvm/panel_2024.csv
"""
from __future__ import annotations

import argparse
import io
import time
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (research data client)"}
CVM = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/{doc}/DADOS/{doc_l}_cia_aberta_{year}.zip"
ARCHIVE = "https://web.archive.org/web/2026id_/{url}"
COTAHIST = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"
CACHE = Path(__file__).resolve().parents[1] / "scratch" / "cvm"
SLEEP = 2.0

# CD_CVM -> ticker root (ON = root+3, PN = root+4). Non-financial sample.
SAMPLE = {9512: "PETR", 4170: "VALE", 5410: "WEGE", 23264: "ABEV", 8133: "LREN",
          13986: "SUZB", 3980: "GGBR", 20087: "EMBR", 5258: "RADL", 2453: "CMIG"}
SECTOR = {"PETR": "energy", "VALE": "materials", "WEGE": "industrials", "ABEV": "staples",
          "LREN": "discretionary", "SUZB": "materials", "GGBR": "materials",
          "EMBR": "industrials", "RADL": "staples", "CMIG": "utilities"}


def _get(url: str) -> bytes:
    for u in (url, ARCHIVE.format(url=url)):
        time.sleep(SLEEP)
        try:
            r = requests.get(u, headers=UA, timeout=300)
        except requests.RequestException:
            continue
        if r.status_code == 200 and r.content[:2] == b"PK":
            return r.content
    raise RuntimeError(f"download failed: {url}")


def fetch_zip(url: str) -> zipfile.ZipFile:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / url.rsplit("/", 1)[1]
    if not path.exists():
        path.write_bytes(_get(url))
    return zipfile.ZipFile(path)


def _csv(z: zipfile.ZipFile, name: str) -> pd.DataFrame:
    return pd.read_csv(z.open(name), sep=";", encoding="latin1", dtype={"CD_CONTA": str})


def load_cvm(doc: str, year: int, codes) -> dict[str, pd.DataFrame]:
    z = fetch_zip(CVM.format(doc=doc, doc_l=doc.lower(), year=year))
    p = f"{doc.lower()}_cia_aberta"
    out = {k: _csv(z, f"{p}_{k}_con_{year}.csv") for k in ("BPA", "BPP", "DRE")}
    out["idx"] = _csv(z, f"{p}_{year}.csv")
    out["cap"] = _csv(z, f"{p}_composicao_capital_{year}.csv")
    cnpj = set(out["idx"].loc[out["idx"].CD_CVM.isin(codes), "CNPJ_CIA"])
    for k in ("BPA", "BPP", "DRE"):
        out[k] = out[k][out[k].CD_CVM.isin(codes)]
    out["cap"] = out["cap"][out["cap"].CNPJ_CIA.isin(cnpj)]
    out["idx"] = out["idx"][out["idx"].CD_CVM.isin(codes)]
    return out


def statement_rows(parts: list[dict]) -> pd.DataFrame:
    """One row per (CD_CVM, period end) with YTD income items, balance items,
    shares, and the first receipt date. Uses only the current-period columns
    (ORDEM_EXERC == ULTIMO) so comparatives restated later do not leak back."""
    recs = []
    for d in parts:
        idx = d["idx"].copy()
        idx["DT_RECEB"] = pd.to_datetime(idx["DT_RECEB"])
        first = idx.groupby(["CD_CVM", "DT_REFER"])["DT_RECEB"].min()
        cnpj2cvm = dict(zip(idx.CNPJ_CIA, idx.CD_CVM))
        cur = {k: d[k][d[k].ORDEM_EXERC.str.upper().str.startswith("ÚLTIMO")] for k in ("BPA", "BPP", "DRE")}
        dre = cur["DRE"].copy()
        dre = dre[pd.to_datetime(dre.DT_INI_EXERC).dt.month.eq(1)
                  & pd.to_datetime(dre.DT_INI_EXERC).dt.day.eq(1)]  # YTD rows only
        cap = d["cap"].assign(CD_CVM=d["cap"].CNPJ_CIA.map(cnpj2cvm))
        for (code, ref), rec in first.items():
            def val(df, conta):
                s = df[(df.CD_CVM == code) & (df.DT_REFER == ref) & (df.CD_CONTA == conta)].VL_CONTA
                if s.empty:
                    return np.nan
                scale = 1000.0 if str(df.loc[s.index[0], "ESCALA_MOEDA"]).upper() == "MIL" else 1.0
                return float(s.iloc[-1]) * scale
            ni = val(dre, "3.11.01")
            c = cap[(cap.CD_CVM == code) & (cap.DT_REFER == ref)]
            recs.append({
                "cd_cvm": code, "period_end": pd.Timestamp(ref), "filed": rec,
                "ytd_revenue": val(dre, "3.01"), "ytd_op_profit": val(dre, "3.05"),
                "ytd_net_income": ni if np.isfinite(ni) else val(dre, "3.11"),
                "equity": val(cur["BPP"], "2.03") - np.nan_to_num(val(cur["BPP"], "2.03.09")),
                "fin_debt": np.nansum([val(cur["BPP"], "2.01.04"), val(cur["BPP"], "2.02.01")]),
                "cash": np.nansum([val(cur["BPA"], "1.01.01"), val(cur["BPA"], "1.01.02")]),
                "sh_on": float((c.QT_ACAO_ORDIN_CAP_INTEGR - c.QT_ACAO_ORDIN_TESOURO).iloc[-1]) if len(c) else np.nan,
                "sh_pn": float((c.QT_ACAO_PREF_CAP_INTEGR - c.QT_ACAO_PREF_TESOURO).iloc[-1]) if len(c) else np.nan,
            })
    return pd.DataFrame(recs).sort_values(["cd_cvm", "period_end"]).drop_duplicates(["cd_cvm", "period_end"], keep="last")


def add_ttm(st: pd.DataFrame) -> pd.DataFrame:
    """TTM_P = YTD_P + FY(y-1) - YTD(P-4); Q4 TTM = annual YTD. NaN if a piece is missing."""
    st = st.copy()
    for item in ("revenue", "op_profit", "net_income"):
        col = f"ytd_{item}"
        out = []
        for _, r in st.iterrows():
            pe = r.period_end
            if pe.month == 12:
                out.append(r[col]); continue
            g = st[st.cd_cvm == r.cd_cvm].set_index("period_end")[col]
            fy, prev = pd.Timestamp(pe.year - 1, 12, 31), pe - pd.DateOffset(years=1)
            prev = pd.Timestamp(prev.year, prev.month, prev.days_in_month)
            out.append(r[col] + g.get(fy, np.nan) - g.get(prev, np.nan))
        st[f"ttm_{item}"] = out
    return st


def parse_cotahist(raw: bytes, roots) -> pd.DataFrame:
    """B3 COTAHIST fixed width: TIPREG 0:2, DATA 2:10, CODBDI 10:12, CODNEG 12:24,
    TPMERC 24:27, PREULT 108:121 (2 implied decimals). Lot market (TPMERC 010) only."""
    want = {f"{r}{k}" for r in roots for k in ("3", "4")}
    rows = []
    for line in raw.decode("latin1").splitlines():
        if line[:2] != "01" or line[24:27] != "010":
            continue
        tk = line[12:24].strip()
        if tk in want:
            rows.append((pd.Timestamp(line[2:10]), tk, int(line[108:121]) / 100.0))
    return pd.DataFrame(rows, columns=["date", "ticker", "close"])


def value_legs(last: dict, mcap: float) -> dict[str, float]:
    """Mirror of core/pit_panel.py::value_ratios on the CVM row."""
    eq, ni, op = last.get("equity"), last.get("ttm_net_income"), last.get("ttm_op_profit")
    rev, fd, cash = last.get("ttm_revenue"), last.get("fin_debt"), last.get("cash")
    ev = mcap + fd - cash if np.isfinite(fd) and np.isfinite(cash) else np.nan
    return {
        "bm": eq / mcap if eq is not None and np.isfinite(eq) and eq > 0 else np.nan,
        "ep": ni / mcap if ni is not None and np.isfinite(ni) else np.nan,
        "sp": rev / mcap if rev is not None and np.isfinite(rev) and rev else np.nan,
        "ey": op / ev if op is not None and np.isfinite(op) and np.isfinite(ev) and ev > 0 else np.nan,
    }


def build_panel(st: pd.DataFrame, px: pd.DataFrame, month_ends) -> pd.DataFrame:
    wide = px.pivot_table(index="date", columns="ticker", values="close")
    out = []
    for me in month_ends:
        hist = wide[wide.index <= me]
        if hist.empty:
            continue
        last_px = hist.ffill().iloc[-1]
        for code, root in SAMPLE.items():
            avail = st[(st.cd_cvm == code) & (st.filed <= me)]
            if avail.empty:
                continue
            last = avail.iloc[-1].to_dict()
            on, pn = last_px.get(f"{root}3", np.nan), last_px.get(f"{root}4", np.nan)
            mcap = np.nansum([last["sh_on"] * on if np.isfinite(on) else np.nan,
                              last["sh_pn"] * pn if np.isfinite(pn) and last["sh_pn"] > 0 else np.nan])
            if not mcap > 0:
                continue
            # composicao_capital has no unit column; some filers report shares in
            # thousands (VALE, ABEV, CMIG ...). Equity/mcap > 50 is implausible -> x1000.
            sh_k = bool(np.isfinite(last["equity"]) and last["equity"] / mcap > 50)
            if sh_k:
                mcap *= 1000.0
            out.append({"date": me, "ticker": root, "sector": SECTOR[root], "cd_cvm": code,
                        "period_end": last["period_end"], "filed": last["filed"], "mcap": mcap, "shares_x1000": sh_k,
                        **value_legs(last, mcap)})
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--out", default=str(CACHE / "panel_sample.csv"))
    a = ap.parse_args()
    codes = list(SAMPLE)
    parts = [load_cvm("DFP", a.year - 2, codes), load_cvm("DFP", a.year - 1, codes),
             load_cvm("ITR", a.year - 1, codes), load_cvm("ITR", a.year, codes)]
    st = add_ttm(statement_rows(parts))
    z = fetch_zip(COTAHIST.format(year=a.year))
    px = parse_cotahist(z.read(z.namelist()[0]), SAMPLE.values())
    me = pd.date_range(f"{a.year}-01-01", f"{a.year}-12-31", freq="ME")
    panel = build_panel(st, px, me)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(a.out, index=False)
    print(panel[panel.date == panel.date.max()].round({'bm': 4, 'ep': 4, 'sp': 4, 'ey': 4}).to_string(index=False))
    print(f"rows={len(panel)} tickers={panel.ticker.nunique()} -> {a.out}")


if __name__ == "__main__":
    main()
