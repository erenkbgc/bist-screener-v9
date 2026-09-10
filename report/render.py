"""report/render.py: report.sections sozlesmesine gore HTML bulteni uretir.

deterministic_math kurali: Bu dosya HICBIR hesap yapmaz, yalnizca zaten
hesaplanmis (core/ motorlarindan gelen) degerleri sablona yerlestirir.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.payload import format_number

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

DISCLAIMER_TEXT_TR = (
    "Bu bulten ve dashboard kisisel kullanim icin otomatik olarak uretilmistir. "
    "Yatirim danismanligi degildir, alim satim tavsiyesi icermez. Skorlama agirliklari "
    "ve esikleri (0.55/0.30/0.15, Piotroski esigi, equity risk premium) denenmemis "
    "baslangic varsayimlaridir, gecmis veriyle kalibre edilmemistir. Gecmis tahmin "
    "izleme ozeti bir backtest degildir, canli takiptir; ortusen zaman ufuklari "
    "nedeniyle bagimsiz gozlem sayisi dusuktur. Hedef fiyatlar sektor ici goreli "
    "degerleme ve teknik hesaplamalardan turetilmistir. Gordon buyume referansi "
    "deneysel bir modeldir ve ana karara girmez. Veriler ucuncu taraf kaynaklardan "
    "alinmistir ve hatali olabilir."
)


def _fmt(value):
    """Sablondaki HER sayisal alan bu filtre ile yazilir; core/payload.py::format_number
    ile AYNI kurali kullanir, boylece HTML'deki sayi ile payload'daki kaynak sayi
    HER ZAMAN ayni string temsiline sahip olur (validation_gate bunu dogrular)."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return format_number(value)
    return value


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["fmt"] = _fmt
    return env


def render_newsletter(context: dict) -> str:
    template = _env().get_template("newsletter.html.j2")
    context = dict(context)
    context.setdefault("disclaimer_text", DISCLAIMER_TEXT_TR)
    return template.render(**context)
