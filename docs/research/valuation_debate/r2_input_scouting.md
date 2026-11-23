# Round 2 input from the web scouting team (docs/scouting/SUMMARY.md on branch agent/scouting)

Candidate ideas the scouts ranked highest. Proposers may adopt, adapt or reject them; the critic should check them like any other proposal.

1. IAS 29 net monetary position gain/loss stripping from E/P (`ep_ex_nmpgl`): remove the monetary gain/loss line from earnings before computing E/P, since it is an inflation-accounting artefact rather than operating profit. Turkey-specific; directly targets the E/P leg of value_sn.
2. Operating cash-flow yield (CFO/P) replacing S/P in value_sn.
3. Insider net buying from SPK II-15.1 disclosures in kap_archive.parquet (larger build; probably not this round).

Already tested and failed, do not re-propose: free-float filter FF1 (branch agent/freefloat, FAIL), and round 1 S1, M2, FV1 (debate/r1_results.md, all FAIL). Lesson from round 1: methods highly correlated with R0 (rho > 0.9) had no power; methods that changed more lost return.
