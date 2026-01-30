from history import SnapshotHistory


def test_nested_dictionary_and_list_are_independent() -> None:
    history = SnapshotHistory({"profile": {"name": "Ada"}, "labels": ["stable"]})
    history.save()

    history.state["profile"]["name"] = "Grace"
    history.state["labels"].append("mutated")

    restored = history.restore()
    assert restored == {"profile": {"name": "Ada"}, "labels": ["stable"]}
