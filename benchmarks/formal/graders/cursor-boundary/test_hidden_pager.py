from pager import paginate


def test_exact_final_page_has_no_phantom_cursor() -> None:
    page = paginate(["a", "b", "c", "d"], cursor=2, page_size=2)
    assert page.items == ["c", "d"]
    assert page.next_cursor is None


def test_empty_page_beyond_end_has_no_cursor() -> None:
    page = paginate(["a"], cursor=3, page_size=2)
    assert page.items == []
    assert page.next_cursor is None
