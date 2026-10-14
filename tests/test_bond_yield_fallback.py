"""doviz.com/tahvil yedek ayristiricisi (borsapy 0.11.0 eski tablo id'sini ariyor)."""
from core.live_data import parse_dovizcom_tr_bonds

_ROW = ('<tr><td><a href="https://www.doviz.com/tahvil/{slug}"><div>{name}</div></a></td>'
        '<td>{y}</td><td>%0,30</td></tr>')


def _page(table_id, rows):
    return f'<table id="{table_id}"><tbody>{"".join(rows)}</tbody></table>'


def test_parses_new_bonds_table_tr_only():
    html = _page("bonds", [
        _ROW.format(slug="tr-2-yillik-tahvil", name="TR 2 Yillik", y="39,70"),
        _ROW.format(slug="tr-10-yillik-tahvil", name="TR 10 Yillik", y="35,44"),
        _ROW.format(slug="abd-2-yillik-tahvil", name="ABD 2 Yillik", y="4,81"),
    ])
    assert parse_dovizcom_tr_bonds(html) == {"2Y": 39.70, "10Y": 35.44}


def test_parses_old_table_id_and_rejects_implausible():
    html = _page("commodities", [
        _ROW.format(slug="tr-2-yillik-tahvil", name="TR 2", y="0,00"),
        _ROW.format(slug="tr-10-yillik-tahvil", name="TR 10", y="-"),
    ])
    assert parse_dovizcom_tr_bonds(html) == {}


def test_missing_table_returns_empty():
    assert parse_dovizcom_tr_bonds("<html></html>") == {}
