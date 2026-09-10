"""regime_monitor: makro/rejim durumunu izler, kritik sapmalarda akisi durdurur.

Spec: architecture.hard_stop_gates -> "regime_monitor kritik sapma bildirirse akis durur"
Spec: regime_monitor.rules
"""
from __future__ import annotations

from datetime import datetime, timezone

from core import db
from macro_mcp import server as macro_mcp

CRITICAL = "critical"
WARNING = "warning"
OK = "ok"


class RegimeHaltError(Exception):
    """Kosuyu iptal etmeyi gerektiren bir rejim durumu (makro veri cekilemedi vb.)."""


def _previous_regime_row(as_of_date: str):
    rows = db.query(
        "SELECT * FROM regime_log WHERE as_of_date < ? ORDER BY as_of_date DESC LIMIT 1",
        (as_of_date,),
    )
    return rows[0] if rows else None


def _avg_vbts_60d(as_of_date: str) -> float | None:
    rows = db.query(
        "SELECT vbts_stock_count FROM regime_log WHERE as_of_date < ? ORDER BY as_of_date DESC LIMIT 60",
        (as_of_date,),
    )
    if not rows:
        return None
    vals = [r["vbts_stock_count"] for r in rows if r["vbts_stock_count"] is not None]
    return sum(vals) / len(vals) if vals else None


def check_market_regime(as_of_date: str) -> dict:
    try:
        snapshot = macro_mcp.get_macro_snapshot(as_of_date)
    except Exception as exc:  # noqa: BLE001 - makro veri cekilemedi kurali
        raise RegimeHaltError(f"makro veri cekilemedi: {exc}") from exc

    if not snapshot:
        raise RegimeHaltError("makro veri cekilemedi (bos yanit)")

    prev = _previous_regime_row(as_of_date)
    alerts: list[dict] = []
    severity = OK

    ban_active = bool(snapshot.get("short_selling_ban_active"))
    ban_changed = prev is not None and bool(prev["short_selling_ban_active"]) != ban_active
    if ban_changed:
        alerts.append({
            "condition": "short_selling_ban_active degisti",
            "action": "Rapora rejim degisikligi uyarisi ekle, kisa vade kovasini 5 islem gunu askiya al",
        })
        severity = max(severity, WARNING, key=lambda s: [OK, WARNING, CRITICAL].index(s))

    # canli veri modunda vbts_stock_count icin ucretsiz bir kaynak dogrulanamadi
    # (bkz. core/live_data.py::live_macro_snapshot) ve deger None gelebilir;
    # .get(..., 0) yalnizca ANAHTAR YOKSA devreye girer, None DEGERi icin de
    # acikca 0'a duser (spike hesabi sessizce crash etmesin diye).
    vbts_count = snapshot.get("vbts_stock_count") or 0
    avg60 = _avg_vbts_60d(as_of_date)
    vbts_spike = avg60 is not None and avg60 > 0 and vbts_count > 2 * avg60
    if vbts_spike:
        alerts.append({
            "condition": "vbts_stock_count 60 gunluk ortalamanin 2 katini asti",
            "action": "Kisa vade kovasi top_n degerini yariya indir",
        })
        severity = WARNING if severity == OK else severity

    bond_shift_bps = None
    if prev is not None and prev["bond_2y_pct"] is not None:
        bond_shift_bps = (snapshot["bond_2y_pct"] - prev["bond_2y_pct"]) * 100
    bond_shock = bond_shift_bps is not None and abs(bond_shift_bps) > 300
    if bond_shock:
        alerts.append({
            "condition": "bond_2y_pct son kosuya gore 300 baz puandan fazla degisti",
            "action": "Hurdle, beta_adjusted_hurdle ve gordon_growth_reference'i yeniden hesapla",
        })
        severity = WARNING if severity == OK else severity

    regime_change_flag = ban_changed or vbts_spike or bond_shock

    conn = db.get_connection()
    try:
        conn.execute(
            """INSERT INTO regime_log
               (as_of_date, short_selling_ban_active, ban_end_date, vbts_stock_count,
                policy_rate_pct, bond_2y_pct, cpi_yoy_pct, usdtry_spot, xu100_level,
                regime_change_flag, real_rate_regime, inflation_trend, fx_regime)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
               ON CONFLICT(as_of_date) DO UPDATE SET
                 short_selling_ban_active=excluded.short_selling_ban_active,
                 vbts_stock_count=excluded.vbts_stock_count,
                 policy_rate_pct=excluded.policy_rate_pct,
                 bond_2y_pct=excluded.bond_2y_pct,
                 cpi_yoy_pct=excluded.cpi_yoy_pct,
                 usdtry_spot=excluded.usdtry_spot,
                 xu100_level=excluded.xu100_level,
                 regime_change_flag=excluded.regime_change_flag""",
            (
                as_of_date, int(ban_active), None, vbts_count,
                snapshot.get("policy_rate_pct"), snapshot.get("bond_2y_pct"),
                snapshot.get("cpi_yoy_pct"), snapshot.get("usdtry_spot"),
                snapshot.get("xu100_level"), int(regime_change_flag),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "as_of_date": as_of_date,
        "snapshot": snapshot,
        "regime_change_flag": regime_change_flag,
        "alerts": alerts,
        "severity": severity,
        "short_term_bucket_suspended": ban_changed,
        "short_term_top_n_halved": vbts_spike,
        "hurdle_recalc_required": bond_shock,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
