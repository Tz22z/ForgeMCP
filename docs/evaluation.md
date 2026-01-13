# Evaluation protocol

## Question

Does the hybrid execution and context runtime solve more repository issues at lower
cost than a baseline tool loop when model capability and resource limits are fixed?

## Controlled variables

Hold these fields identical across both arms:

- exact model ID and provider settings;
- instance list and base commits;
- available tool names and schemas;
- model/tool/token/time budgets;
- test command and container limits;
- retry policy and concurrency; and
- token prices used for reporting.

The independent variable is `context_strategy`: `baseline` or `hybrid`. If studying the
verified loop separately, introduce a second explicit ablation rather than changing two
mechanisms at once.

## Scoring

Each manifest case has a visible fixture and a grader directory outside the copied agent
workspace. The harness:

1. copies the fixture into a disposable workspace;
2. hashes visible test files;
3. runs the selected agent arm;
4. hashes visible tests again;
5. runs the external grader with the workspace on `PYTHONPATH`; and
6. counts a solve only when the grader passes and protected tests are unchanged.

This blocks two easy sources of false success: weakening visible tests and learning or
modifying hidden assertions.

## Primary metrics

| Metric | Definition |
| --- | --- |
| Solve rate | External-grader passes / attempted instances |
| First-run solve rate | Solves without evaluator-level retry |
| Cost per solve | Total configured token cost / solved instances |
| Repeated-read ratio | Reads of an unchanged file version after its first read / all reads |
| Average tool calls | Tool calls / attempted instances |

Also preserve per-instance status, model/tool calls, input/output tokens, changed files,
grader exit code, and protected-file status. Aggregate-only reports are insufficient for
error analysis.

## Manifest shape

```json
{
  "cases": [
    {
      "instance_id": "project__issue-1",
      "fixture": "fixtures/project__issue-1",
      "grader": "graders/project__issue-1",
      "issue": {
        "title": "Cache entry survives deletion",
        "body": "...",
        "acceptance_criteria": ["..."]
      },
      "test_command": ["python", "-m", "pytest", "-q"]
    }
  ]
}
```

Fixture and grader paths are resolved relative to the manifest. Do not put grader files
inside a fixture.

## Running both arms

```bash
forge evaluate benchmark.json --strategy baseline --model MODEL_ID \
  --input-price-per-million INPUT_PRICE \
  --output-price-per-million OUTPUT_PRICE \
  --output artifacts/baseline.json

forge evaluate benchmark.json --strategy hybrid --model MODEL_ID \
  --input-price-per-million INPUT_PRICE \
  --output-price-per-million OUTPUT_PRICE \
  --output artifacts/hybrid.json
```

Run arms in interleaved or randomized order when provider load may influence latency.
Record exact package versions, image digest, model ID, date, and manifest hash.

## Historical result caveat

`benchmarks/reconstructed-swebench-verified-120.summary.json` records the recovered
headline numbers: 54/120 baseline solves and 85/120 hybrid solves, yielding 45% and
70.83% (reported as 71%). Raw per-instance records and the precise historical model ID
were not recovered. Treat that file as provenance for a résumé claim, not as a newly
reproducible scientific artifact. New benchmark claims should be based on reports emitted
by the current harness.

