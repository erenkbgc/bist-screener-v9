# Shadow record wiring (for the manager to apply; not applied by shadow agent)

Script: `scripts/shadow_record.py` (branch agent/r5-shadow). Reads decisions.jsonl, data/forward_record/prices/,
bist_history.db universe_snapshot. Writes data/forward/shadow_record.csv + data/forward/shadow_report.json.
Never fails the live run's logic; it only needs the files the run already commits.

## Workflow change (.github/workflows/daily-screener.yml: new step right after the `python run.py` step, line 82)

```yaml
      - name: Shadow forward record (paper only)
        run: python scripts/shadow_record.py || echo "shadow_record failed (non-blocking)"
```

and add `data/forward/` to the existing commit step (line 124):
`git add data/bist_history.db data/reports/ data/forward_record/ data/forward/ config/weights_optimized.json`

Notes
- Idempotent: running daily is fine; picks are written once per decision month, returns filled when the
  next decision's entry close exists in the price store.
- Prices: the store keeps only tickers in recorded decisions' holdings+universe, which covers every pick.
- Counting starts with the 2026-12 decision (docs/research/shadow_record_preregistration.md).
