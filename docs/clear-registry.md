# Clear Biased Registry

All entries in `research/results/registry.json` were computed with lookahead bias
(signal at bar T entering at bar T's close). The fix was applied 2026-04-12 in
`strategies/adapters/vectorbt_adapter.py`. These results are invalid — clear before rerunning.

```bash
echo "[]" > research/results/registry.json
```
