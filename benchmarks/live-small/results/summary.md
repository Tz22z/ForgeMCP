# ForgeMCP live-small baseline vs hybrid report

Four-case API-backed integration pilot with lexical distractors and external graders.

- Model: `gpt-5.2-2025-12-11`
- Trials: 3 paired trials x 4 cases
- Manifest SHA-256: `862a194f75c5c512d8a604a4229e96cd1f09d4102d6e0c2d784b2b773d971517`
- Benchmark inputs SHA-256: `0c05d33fcc2228480a45f18f6276cb36e706b679d7a1bc5ff3f6667da4958e55`
- Runtime source SHA-256: `69c4195323a1b2f97b7c400fda79112f65b67a3dba694afe8b48f67e3bbc1b61`
- Pricing: $1.75/M input tokens and $14/M output tokens

## Aggregate results

| Metric | Baseline | Hybrid | Hybrid change |
| --- | ---: | ---: | ---: |
| Solve rate | 12/12 (100.0%) | 11/12 (91.7%) | -8.3 pp |
| Average tool calls | 9.33 | 7.17 | -23.2% |
| Average model calls | 10.33 | 8.17 | -21.0% |
| Average input tokens | 27293 | 15028 | -44.9% |
| Average repeated-read ratio | 0.0% | 0.0% | +0.0 pp |
| Estimated total cost | $0.6593 | $0.4007 | -39.2% |
| Cost per solve | $0.0549 | $0.0364 | -33.7% |
| Protected-file violations | 0 | 1 | +1 |
| Hidden grader passes | 12/12 | 12/12 | +0 |
| Non-success terminal states | 0 | 0 | +0 |

## Paired trials

| Trial | Baseline solved | Hybrid solved | Baseline cost | Hybrid cost |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 4/4 | 3/4 | $0.1951 | $0.1485 |
| 2 | 4/4 | 4/4 | $0.2134 | $0.1406 |
| 3 | 4/4 | 4/4 | $0.2509 | $0.1116 |

## Interpretation

Hybrid's aggregate solve rate was 8.3 percentage points lower than baseline.

Relative to baseline, hybrid changed average tool calls by -23.2%, model calls by -21.0%, input tokens by -44.9%, and estimated total cost by -39.2%.

The anti-tampering rule rejected 1 run(s) that changed protected visible tests, regardless of hidden-grader outcome.

## Limitations

- This is a four-case synthetic integration benchmark, not SWE-bench.
- Three trials are enough for regression evidence, not a precise population estimate.
- One hybrid run changed a protected test and was correctly rejected.
- Repeated-read ratio stayed at zero and does not support a repeated-read claim.
