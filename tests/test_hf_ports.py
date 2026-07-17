from shared.hf_import.ports import find_free_port


def test_find_free_port_in_range():
    port = find_free_port(18080, 18090)
    assert 18080 <= port <= 18090
