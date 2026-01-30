# Live small benchmark

This is a four-instance, API-backed integration benchmark for comparing ForgeMCP's
`baseline` and `hybrid` context strategies under the same model and budgets. Each
fixture contains a lexical distractor, while the hidden grader stays outside the agent
workspace.

This suite is intentionally small. It validates the current harness and exposes
regressions cheaply; it is not SWE-bench and must not be used to substantiate the
historical 120-instance résumé numbers.

Run both arms with a pinned model snapshot and current explicit token prices:

```bash
forge evaluate benchmarks/live-small/manifest.json \
  --strategy baseline \
  --model gpt-5.2-2025-12-11 \
  --input-price-per-million 1.75 \
  --output-price-per-million 14 \
  --output benchmarks/live-small/results/baseline.json

forge evaluate benchmarks/live-small/manifest.json \
  --strategy hybrid \
  --model gpt-5.2-2025-12-11 \
  --input-price-per-million 1.75 \
  --output-price-per-million 14 \
  --output benchmarks/live-small/results/hybrid.json
```

Alternate the starting arm across repeated trials if latency is a reported metric.

Aggregate paired trials with:

```bash
python scripts/summarize_trials.py \
  --manifest benchmarks/live-small/manifest.json \
  --baseline benchmarks/live-small/results/baseline-trial-{1,2,3}.json \
  --hybrid benchmarks/live-small/results/hybrid-trial-{1,2,3}.json \
  --input-price-per-million 1.75 \
  --output-price-per-million 14 \
  --output-json benchmarks/live-small/results/summary.json \
  --output-markdown benchmarks/live-small/results/summary.md
```
