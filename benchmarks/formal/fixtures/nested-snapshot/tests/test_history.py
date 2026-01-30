import pytest
from history import SnapshotHistory


def test_scalar_value_is_restored() -> None:
    history = SnapshotHistory({"title": "before"})
    history.save()
    history.state["title"] = "after"
    assert history.restore() == {"title": "before"}


def test_restore_without_snapshot_is_rejected() -> None:
    with pytest.raises(LookupError):
        SnapshotHistory({}).restore()
