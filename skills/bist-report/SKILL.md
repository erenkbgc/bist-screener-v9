---
name: bist-report
description: report.sections sozlesmesine gore mobil-oncelikli HTML bulten uretir ve validation_gate ile orphan sayi/banned_claims taramasi yapar.
---

# bist-report

Yontemi tasir; hesap `report/render.py` (Jinja2 sablon: `templates/newsletter.html.j2`,
proje kokundeki `report/templates/newsletter.html.j2` ile ayni) ve
`report/validate.py` icindedir.

`validation_gate.rule`: HTML icindeki tum sayisal token'lar
`core/payload.py::build_report_payload` ciktisinda bulunmalidir; aksi halde
gonderim iptal edilir.

## Kullanim
```
python scripts/validate.py --as-of-date 2026-09-10 --html-file /path/to/report.html
```
