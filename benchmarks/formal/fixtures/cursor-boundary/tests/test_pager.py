import pytest
from pager import paginate


def test_non_final_page_returns_cursor() -> None:
    assert paginate([1, 2, 3, 4, 5], page_size=2).next_cursor == 2


def test_partial_final_page_has_no_cursor() -> None:
    assert paginate([1, 2, 3, 4, 5], cursor=4, page_size=2).next_cursor is None


def test_invalid_cursor_is_rejected() -> None:
    with pytest.raises(ValueError):
        paginate([1], cursor=-1)
