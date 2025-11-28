from pathlib import Path

from forgemcp.core.events import EventJournal, redact


def test_journal_round_trip(tmp_path: Path) -> None:
    journal = EventJournal(tmp_path / "events.jsonl", "run-1")
    journal.append("tool.completed", {"output": "ok"})
    event = journal.read_all()[0]
    assert event.run_id == "run-1"
    assert event.sequence == 1


def test_journal_redacts_secrets(tmp_path: Path) -> None:
    journal = EventJournal(tmp_path / "events.jsonl", "run-1")
    journal.append("model.request", {"authorization": "Bearer sk-secretsecret123"})
    assert "sk-secret" not in (tmp_path / "events.jsonl").read_text()


def test_redact_api_key_assignment() -> None:
    assert redact("api_key='abc123'") == "api_key='[REDACTED]'"
