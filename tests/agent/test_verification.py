from forgemcp.agent.verification import parse_test_observation
from forgemcp.tools.toolset import RawObservation


def test_parse_pytest_summary() -> None:
    report = parse_test_observation(
        RawObservation(
            "FAILED tests/test_a.py::test_a\n1 failed, 4 passed, 1 skipped in 0.15s",
            {"command": ["pytest"], "exit_code": 1, "elapsed_seconds": 0.2},
        )
    )
    assert report.failed == 1
    assert report.passed == 4
    assert report.skipped == 1
    assert not report.successful
