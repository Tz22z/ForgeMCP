# Formal eight-case benchmark

This suite extends `live-small` to eight independent defects and uses the same
controlled protocol for both arms. It covers four boundary/state cases and four
cross-file or mutable-state cases. Every fixture has passing visible tests, a failing
external grader before repair, and a lexical distractor that competes for the fixed
1,000-token context budget.

The benchmark is synthetic and Python-only. “Formal” means its manifest, exact model
snapshot, budgets, graders, trial count, pricing, raw reports, and hashes are checked in;
it does not mean the suite is a substitute for SWE-bench.

Run three paired trials, alternating the starting arm:

```bash
forge evaluate benchmarks/formal/manifest.json \
  --strategy baseline --model gpt-5.2-2025-12-11 \
  --input-price-per-million 1.75 --output-price-per-million 14 \
  --output benchmarks/formal/results/baseline-trial-1.json

forge evaluate benchmarks/formal/manifest.json \
  --strategy hybrid --model gpt-5.2-2025-12-11 \
  --input-price-per-million 1.75 --output-price-per-million 14 \
  --output benchmarks/formal/results/hybrid-trial-1.json
```

Repeat for trials 2 and 3, then aggregate the six raw reports:

```bash
python scripts/summarize_trials.py \
  --manifest benchmarks/formal/manifest.json \
  --baseline benchmarks/formal/results/baseline-trial-{1,2,3}.json \
  --hybrid benchmarks/formal/results/hybrid-trial-{1,2,3}.json \
  --input-price-per-million 1.75 --output-price-per-million 14 \
  --output-json benchmarks/formal/results/summary.json \
  --output-markdown benchmarks/formal/results/summary.md
```
