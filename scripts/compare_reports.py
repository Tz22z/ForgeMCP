"""Compare two ForgeMCP aggregate evaluation reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from forgemcp.evaluation.compare import compare


def main(baseline_path: Path, candidate_path: Path) -> None:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    if baseline["attempted"] != candidate["attempted"]:
        raise ValueError("reports have different attempted counts")
    print(json.dumps(compare(baseline, candidate), indent=2, sort_keys=True))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: compare_reports.py BASELINE.json CANDIDATE.json")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
