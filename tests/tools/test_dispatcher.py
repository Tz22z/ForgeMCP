import hashlib
from pathlib import Path

from forgemcp.context.index import RepositoryIndex
from forgemcp.context.symbols import SymbolExtractor
from forgemcp.core.budget import BudgetLedger
from forgemcp.core.events import EventJournal
from forgemcp.core.models import BudgetSpec, ToolCall
from forgemcp.tools.dispatcher import ToolDispatcher
from forgemcp.tools.observations import ObservationStore
from forgemcp.tools.policy import ToolPolicy
from forgemcp.tools.toolset import RepositoryTools


def dispatcher(tmp_path: Path, approved_tools: frozenset[str] = frozenset()) -> ToolDispatcher:
    policy = ToolPolicy(tmp_path, approved_tools=approved_tools)
    index = RepositoryIndex(
        tmp_path,
        database=tmp_path / ".forgemcp" / "index.sqlite3",
        extractor=SymbolExtractor(prefer_tree_sitter=False),
    )
    index.refresh()
    return ToolDispatcher(
        RepositoryTools(policy),
        policy,
        BudgetLedger(BudgetSpec()),
        EventJournal(tmp_path / ".forgemcp" / "events.jsonl", "test"),
        ObservationStore(tmp_path / ".forgemcp" / "observations", max_chars=100),
        index,
    )


def test_dispatch_validates_arguments(tmp_path: Path) -> None:
    result = dispatcher(tmp_path).dispatch(
        ToolCall(id="1", name="read_file", arguments={"path": "missing.py", "surprise": True})
    )
    assert not result.ok
    assert "ValidationError" in (result.error or "")


def test_dispatch_edit_invalidates_and_refreshes_index(tmp_path: Path) -> None:
    (tmp_path / "value.py").write_text("VALUE = 1\n")
    active = dispatcher(tmp_path)
    active.index.refresh()
    result = active.dispatch(
        ToolCall(
            id="2",
            name="replace_text",
            arguments={"path": "value.py", "old": "1", "new": "2"},
        )
    )
    assert result.ok
    assert result.metadata["index_reparsed"] == 1
    assert (tmp_path / "value.py").read_text() == "VALUE = 2\n"


def test_dispatch_rejects_unknown_tool(tmp_path: Path) -> None:
    result = dispatcher(tmp_path).dispatch(ToolCall(id="3", name="shell", arguments={"cmd": "rm"}))
    assert not result.ok
    assert "unknown tool" in (result.error or "")


def test_observation_is_truncated_with_reference(tmp_path: Path) -> None:
    (tmp_path / "long.py").write_text("x = 1\n" * 100)
    result = dispatcher(tmp_path).dispatch(
        ToolCall(id="4", name="read_file", arguments={"path": "long.py"})
    )
    assert result.ok
    assert result.truncated
    assert result.reference is not None


def test_delete_requires_approval_and_exact_content_hash(tmp_path: Path) -> None:
    target = tmp_path / "obsolete.py"
    target.write_text("OLD = True\n")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    call = ToolCall(
        id="5",
        name="delete_file",
        arguments={"path": "obsolete.py", "expected_sha256": digest},
    )

    denied = dispatcher(tmp_path).dispatch(call)
    assert not denied.ok
    assert "ApprovalRequired" in (denied.error or "")
    assert target.exists()

    approved = dispatcher(tmp_path, frozenset({"delete_file"})).dispatch(call)
    assert approved.ok
    assert not target.exists()
