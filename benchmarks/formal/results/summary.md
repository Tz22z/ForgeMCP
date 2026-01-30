# ForgeMCP formal-8 baseline vs hybrid report

Eight-case, API-backed paired benchmark covering boundary conditions, cross-file invalidation, idempotency, configuration precedence, and mutable state.

- Model: `gpt-5.2-2025-12-11`
- Trials: 3 paired trials x 8 cases
- Manifest SHA-256: `4c74e04fa3a659d835302e137e918135aec90776daa9e99701b827eb06d4422d`
- Benchmark inputs SHA-256: `dc409849e1de0f3f3f6baafea53901d96a08e9378ef858d86ccbd9cf78879bd1`
- Runtime source SHA-256: `69c4195323a1b2f97b7c400fda79112f65b67a3dba694afe8b48f67e3bbc1b61`
- Pricing: $1.75/M input tokens and $14/M output tokens

## Aggregate results

| Metric | Baseline | Hybrid | Hybrid change |
| --- | ---: | ---: | ---: |
| Solve rate | 17/24 (70.8%) | 17/24 (70.8%) | +0.0 pp |
| Average tool calls | 9.42 | 7.79 | -17.3% |
| Average model calls | 10.12 | 8.50 | -16.0% |
| Average input tokens | 22258 | 16521 | -25.8% |
| Average repeated-read ratio | 30.2% | 25.6% | -4.6 pp |
| Estimated total cost | $1.1037 | $0.8606 | -22.0% |
| Cost per solve | $0.0649 | $0.0506 | -22.0% |
| Protected-file violations | 0 | 0 | +0 |
| Hidden grader passes | 24/24 | 24/24 | +0 |
| Non-success terminal states | 7 | 7 | +0 |

## Paired trials

| Trial | Baseline solved | Hybrid solved | Baseline cost | Hybrid cost |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 7/8 | 7/8 | $0.3344 | $0.2782 |
| 2 | 5/8 | 4/8 | $0.3999 | $0.3325 |
| 3 | 5/8 | 6/8 | $0.3695 | $0.2499 |

## Interpretation

Both strategies achieved the same aggregate solve rate.

Relative to baseline, hybrid changed average tool calls by -17.3%, model calls by -16.0%, input tokens by -25.8%, and estimated total cost by -22.0%.

## Limitations

- This is an eight-case synthetic integration benchmark, not SWE-bench.
- Three paired trials provide regression evidence, not a precise population estimate.
- The cases are Python-only and deliberately small enough for controlled paid reruns.
- The benchmark isolates context selection; it does not estimate performance across all repository tasks.
