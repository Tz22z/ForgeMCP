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
6. counts a solve only when the agent reaches `succeeded`, the grader passes, and
   protected tests are unchanged.

This blocks two easy sources of false success: weakening visible tests and learning or
modifying hidden assertions. Graders import `pytest` in Python isolated mode before the
workspace is added to `sys.path`, so a generated top-level `pytest.py` cannot shadow the
real test runner.

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

## Current formal benchmark

`benchmarks/formal/manifest.json` fixes eight synthetic Python cases and external
graders. Three paired trials with `gpt-5.2-2025-12-11` produced 24 attempts per arm.
Baseline and hybrid each reached 17/24 strict solves (70.8%); hybrid reduced average
tool calls by 17.3%, input tokens by 25.8%, and estimated cost per solve by 22.0%.
Repeated-read ratio fell from 30.2% to 25.6% (4.6 percentage points).

All 48 patches passed their external graders, but 14 runs exhausted the 12-model-call
budget before reaching the runtime's `succeeded` state and therefore failed strict
scoring. This distinction is preserved in the raw reports instead of being folded into
the headline solve rate. See `benchmarks/formal/results/summary.md` for trial-level
results, hashes, and limitations.

## Historical result caveat

`benchmarks/reconstructed-swebench-verified-120.summary.json` records the recovered
headline numbers: 54/120 baseline solves and 85/120 hybrid solves, yielding 45% and
70.83% (reported as 71%). Raw per-instance records and the precise historical model ID
were not recovered. Treat that file as historical provenance, not as a reproduced
scientific artifact or a current résumé claim. Current claims should use reports emitted
by the checked-in harness.
