# Phase 0 Validation Harness

Developer-only tool for validating stability of `S0/S1/S2` crawler behavior before adding DB schema/resume logic.

## Scope
- Runs repeated **headless** crawls over a small corpus
- Optionally reruns **flagged** sites in **headful** mode
- Produces JSONL raw outputs + JSON/Markdown summaries + screenshots
- Stays isolated from production app flow

## Run
From `backend/`:

```bash
/usr/bin/python3 validation/phase0_validate.py \
  --sites validation/phase0_corpus.txt \
  --outdir ../phase0_out \
  --repeats 3 \
  --with-policy
```

Optional headful follow-up for flagged sites:

```bash
/usr/bin/python3 validation/phase0_validate.py \
  --sites validation/phase0_corpus.txt \
  --outdir ../phase0_out \
  --repeats 3 \
  --with-policy \
  --headful-rerun-flagged
```

## Outputs
- `results_repeat_<n>.jsonl`
- `phase0_summary.json`
- `phase0_summary.md`
- `artifacts/repeat_<n>/<site>/S0.png|S1.png|S2.png`
- `headful_flagged.jsonl` and `artifacts/headful_review/<site>/...` (if enabled)

## Notes
- Stability checks use semantic action buckets for `S1` and `S2`.
- `policy.found` and `policy.discovery_method` are included in categorical stability checks.
- Flagging is split into `requires_human_sites`, `unstable_sites`, and union `flagged_sites`.
