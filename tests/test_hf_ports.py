import pytest

from shared.hf_import.ports import find_free_port


def test_find_free_port_in_range():
    port = find_free_port(18080, 18090)
    assert 18080 <= port <= 18090


def test_find_free_port_raises_on_empty_range():
    with pytest.raises(RuntimeError, match="No free port in 1–0"):
        find_free_port(1, 0)
