import pandas as pd
import pytest

from core import delisted


def _rows(dates, adj, raw, vol, cap):
    return [{"HGDG_TARIH": pd.Timestamp(d).strftime("%d-%m-%Y"), "HGDG_KAPANIS": a, "HG_KAPANIS": r,
             "HGDG_HACIM": v, "SERMAYE": c} for d, a, r, v, c in zip(dates, adj, raw, vol, cap)]


def test_daily_frame_cuts_suspension_tail():
    rows = _rows(["2020-01-02", "2020-01-03", "2020-01-06"], [1, 2, 2], [1, 2, 2], [10, 10, 0], [5, 5, 5])
    d = delisted.daily_frame(rows)
    assert d.index.max() == pd.Timestamp("2020-01-03")
    assert delisted.last_trade(d) == pd.Timestamp("2020-01-03")


def test_price_frames_tl_volume_round_trips():
    rows = _rows(["2020-01-02"], [3.0], [6.0], [120.0], [5])
    raw, adj = delisted.price_frames(delisted.daily_frame(rows))
    assert raw["Close"].iloc[0] * raw["Volume"].iloc[0] == pytest.approx(120.0)
    assert adj["Close"].iloc[0] == 3.0


def test_share_events_from_capital_changes():
    rows = _rows(["2020-01-02", "2020-01-03", "2020-01-06"], [1, 1, 1], [1, 1, 1], [1, 1, 1], [100, 100, 150])
    ev = delisted.share_events("X", delisted.daily_frame(rows))
    assert len(ev) == 1
    assert ev["bonus_pct"].iloc[0] == pytest.approx(50.0)
    assert ev["rights_pct"].iloc[0] == 0.0


def test_classify_exit_window_and_pattern():
    kap = pd.DataFrame({"stock_code": ["A", "A", "B"],
                        "published_at": pd.to_datetime(["2019-06-01", "2015-01-01", "2019-06-01"]),
                        "subject": ["Devrolma İşlemlerine İlişkin Bildirim", "Birleşme", "Özel Durum"],
                        "summary": [None, None, "Genel kurul"]})
    last = pd.Timestamp("2020-01-15")
    assert delisted.classify_exit(kap, "A", last) == "corporate"
    assert delisted.classify_exit(kap, "B", last) == "other"
    # pencere disindaki birlesme sayilmaz
    assert delisted.classify_exit(kap[kap["published_at"] < "2016-01-01"], "A", last) == "other"


def test_exit_return_specs():
    assert delisted.exit_return("S1", "other", "X") == -0.30
    assert delisted.exit_return("S1", "corporate", "X") == 0.0
    assert delisted.exit_return("S4", "other", "AKFEN") == 0.0
    assert delisted.exit_return("S1", "other", "AKFEN") == -0.30
    assert delisted.exit_return("S5", "corporate", "X") == -1.0


def test_apply_exits_mid_month():
    me = pd.to_datetime(["2020-03-31", "2020-04-30", "2020-05-31"])
    f = pd.DataFrame({"ticker": "X", "date": me, "fwd_ret_1m": [0.1, 0.05, None], "fwd_ret_6m": [None] * 3})
    adj_at = pd.Series([10.0, 11.0, 11.55], index=me)
    out = delisted.apply_exits(f, {"X": (pd.Timestamp("2020-05-18"), 11.55)}, {"X": adj_at}, {"X": -0.30})
    assert list(out["date"]) == list(me[:2])  # mayis sonu satiri cikistan sonra
    assert out["fwd_ret_1m"].iloc[0] == pytest.approx(0.1)  # nisan: cikis yok
    assert out["fwd_ret_1m"].iloc[1] == pytest.approx(1.05 * 0.7 - 1)
    assert out["fwd_ret_6m"].iloc[0] == pytest.approx(1.155 * 0.7 - 1)


def test_apply_exits_on_month_end_and_other_tickers_untouched():
    me = pd.to_datetime(["2020-04-30", "2020-05-31"])
    f = pd.DataFrame({"ticker": ["X", "X", "Y"], "date": list(me) + [me[1]],
                      "fwd_ret_1m": [0.2, None, 0.3], "fwd_ret_6m": [None] * 3})
    adj_at = pd.Series([10.0, 12.0], index=me)
    out = delisted.apply_exits(f, {"X": (pd.Timestamp("2020-05-31"), 12.0)}, {"X": adj_at}, {"X": -1.0})
    x = out[out["ticker"] == "X"].set_index("date")["fwd_ret_1m"]
    assert x.loc[me[0]] == pytest.approx(0.2)
    assert x.loc[me[1]] == pytest.approx(-1.0)
    assert out.loc[out["ticker"] == "Y", "fwd_ret_1m"].iloc[0] == 0.3
