# Incoming Candidates

Strategy candidates received from QuantResearcher, ready for production backtesting.

## Rules

- Files here must be valid per `docs/HANDOFF_SPEC.md` before any work begins.
- Run `candidate_validator.py` on every file before adding to a trial.
- Do not edit candidate files — they are researcher artifacts. Open questions go back to researcher.
- After a trial completes, move the candidate to `../trials/` (keep original JSON as provenance).

## Validation

```bash
python research/candidate_validator.py research/incoming/<candidate_id>.json
```

Returns exit code 0 on pass, 1 on failure with field-by-field report.

## Source

Candidates originate from `QuantResearcher/research/candidates/`. Transfer is currently manual.