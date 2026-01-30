from __future__ import annotations

import json
from pathlib import Path

from forgemcp.evaluation.harness import load_manifest


def test_formal_manifest_has_external_graders_and_fixed_fixtures() -> None:
    repository = Path(__file__).resolve().parents[2]
    manifest_path = repository / "benchmarks" / "formal" / "manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = load_manifest(manifest_path)

    assert raw["name"] == "ForgeMCP formal-8 baseline vs hybrid"
    assert len(cases) == 8
    assert len({case.instance_id for case in cases}) == 8
    for case in cases:
        assert case.fixture.is_dir()
        assert case.grader.is_dir()
        assert case.grader not in case.fixture.parents
        assert (case.fixture / ".forgemcp.toml").is_file()
        assert (case.fixture / "tests").is_dir()
        assert (case.fixture / "docs" / "incident-archive.md").is_file()
